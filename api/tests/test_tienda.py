"""Smoke tests del circuito completo: reservas, checkout, auth y admin."""

import base64
import contextlib
import hashlib
import hmac
import io
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.config import get_settings
from app.models import Item, ItemStatus, Order, OrderStatus, Release, User
from app.services.metrics import redsys_payment_result_total
from app.services.reservations import confirm_sale, release_expired, reserve_items


def _counter(result: str) -> float:
    return redsys_payment_result_total.labels(result=result)._value.get()


def _sign_as_redsys(params: dict) -> tuple[str, str]:
    """Firma unos parámetros de respuesta exactamente como lo haría Redsys,
    para poder simular su notificación server-to-server en los tests."""
    secret_key = get_settings().redsys_secret_key
    key = base64.b64decode(secret_key)
    order_id = params["Ds_Order"]
    data = order_id.encode("utf-8")
    data += b"\x00" * (-len(data) % 8)
    from app.services.redsys import TripleDES
    from cryptography.hazmat.primitives.ciphers import Cipher, modes

    cipher = Cipher(TripleDES(key), modes.CBC(b"\x00" * 8))
    encryptor = cipher.encryptor()
    derived_key = encryptor.update(data) + encryptor.finalize()

    params_b64 = base64.b64encode(json.dumps(params).encode("utf-8")).decode("ascii")
    digest = hmac.new(derived_key, params_b64.encode("ascii"), hashlib.sha256).digest()
    signature = base64.b64encode(digest).decode("ascii").replace("+", "-").replace("/", "_")
    return params_b64, signature


def _seed(db):
    r = Release(artista="Los Ganglios", titulo="Peruguay", formato="LP")
    db.add(r)
    db.flush()
    i1 = Item(release_id=r.id, precio=Decimal("22.00"), codi_discogs=3844817287)
    i2 = Item(release_id=r.id, precio=Decimal("18.00"))
    db.add_all([i1, i2])
    db.commit()
    return r, i1, i2


def _login(client, email):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert client.post("/auth/magic-link", json={"email": email}).status_code == 202
    token = re.search(r"token=([\w\-]+)", buf.getvalue()).group(1)
    resp = client.post(f"/auth/magic-link/verify?token={token}")
    assert resp.status_code == 200
    return resp.json()["access_token"], token


def test_reserva_atomica_todo_o_nada(db):
    _, i1, i2 = _seed(db)
    cart_a, cart_b = uuid.uuid4(), uuid.uuid4()
    assert reserve_items(db, [i1.id], cart_a) == []
    # segunda persona: i1 ya no está; i2 no debe quedar reservado (rollback)
    assert reserve_items(db, [i1.id, i2.id], cart_b) == [i1.id]
    db.refresh(i2)
    assert i2.status == ItemStatus.disponible
    assert confirm_sale(db, [i1.id], cart_a) == []
    db.refresh(i1)
    assert i1.status == ItemStatus.vendido


def test_checkout_completo_con_pago_redsys_y_cancelacion(db, client):
    _, i1, i2 = _seed(db)
    cat = client.get("/catalog").json()
    assert cat["total"] == 1

    assert client.post("/cart/items", json={"item_id": str(i2.id)}).status_code == 201
    assert client.post("/checkout/start").status_code == 200
    conf = client.post(
        "/checkout/confirm",
        json={"email_contacto": "client@example.com", "metodo_envio": "recogida_tienda"},
    )
    assert conf.status_code == 201
    order_id = conf.json()["id"]
    assert conf.json()["status"] == "pendiente_pago"
    db.expire_all()
    # el pedido existe pero todavía no se ha vendido: el pago está pendiente
    assert db.get(Item, i2.id).status == ItemStatus.reservado

    pay = client.post(f"/checkout/{order_id}/pay/redsys/start")
    assert pay.status_code == 200
    form = pay.json()
    assert form["Ds_MerchantParameters"] and form["Ds_Signature"]
    ds_order = json.loads(base64.b64decode(form["Ds_MerchantParameters"]))["DS_MERCHANT_ORDER"]

    # Redsys autoriza el cobro y llama a nuestra notificación
    params_b64, signature = _sign_as_redsys({
        "Ds_Order": ds_order, "Ds_Response": "0000", "Ds_AuthorisationCode": "123456",
    })
    with contextlib.redirect_stdout(io.StringIO()):
        notify = client.post(
            "/checkout/pay/redsys/notify",
            data={"Ds_SignatureVersion": "HMAC_SHA256_V1", "Ds_MerchantParameters": params_b64, "Ds_Signature": signature},
        )
    assert notify.status_code == 200
    db.expire_all()
    assert db.get(Order, uuid.UUID(order_id)).status == OrderStatus.pagado
    assert db.get(Item, i2.id).status == ItemStatus.vendido
    assert _counter("autorizado") >= 1

    # Redsys puede reintentar la notificación: la segunda vez no debe recontar como autorizado
    antes = _counter("already_processed")
    with contextlib.redirect_stdout(io.StringIO()):
        retry = client.post(
            "/checkout/pay/redsys/notify",
            data={"Ds_SignatureVersion": "HMAC_SHA256_V1", "Ds_MerchantParameters": params_b64, "Ds_Signature": signature},
        )
    assert retry.status_code == 200 and retry.json()["status"] == "ya procesado"
    assert _counter("already_processed") == antes + 1

    # el admin debe poder ver la referencia del cobro Redsys sin ir al portal del banco
    access0, _ = _login(client, "admin_view@example.com")
    user0 = db.scalar(select(User).where(User.email == "admin_view@example.com"))
    user0.rol = "admin"
    db.commit()
    admin_access0, _ = _login(client, "admin_view@example.com")
    detail = client.get(f"/admin/orders/{order_id}", headers={"Authorization": f"Bearer {admin_access0}"})
    assert detail.status_code == 200
    payments = detail.json()["payments"]
    assert len(payments) == 1
    assert payments[0]["ds_order"] == ds_order
    assert payments[0]["estado"] == "autorizado"
    assert payments[0]["ds_authorisation_code"] == "123456"

    # sin copias disponibles, el release desaparece del catálogo público
    # (i1 sigue disponible, así que aún sale; lo retiramos para comprobarlo)
    db.get(Item, i1.id).status = ItemStatus.retirado
    db.commit()
    assert client.get("/catalog").json()["total"] == 0

    # un admin cancela el pedido -> el ejemplar vuelve a la venta
    access, _ = _login(client, "admin@example.com")
    user = db.scalar(select(User).where(User.email == "admin@example.com"))
    user.rol = "admin"
    db.commit()
    admin_access, _ = _login(client, "admin@example.com")
    orders = client.get("/admin/orders", headers={"Authorization": f"Bearer {admin_access}"})
    assert orders.status_code == 200 and len(orders.json()) == 1
    oid = orders.json()[0]["id"]
    assert (
        client.patch(
            f"/admin/orders/{oid}/status",
            json={"status": "cancelado"},
            headers={"Authorization": f"Bearer {admin_access}"},
        ).status_code
        == 200
    )
    db.expire_all()
    assert db.get(Item, i2.id).status == ItemStatus.disponible


def test_checkout_pago_denegado_libera_el_ejemplar(db, client):
    _, _, i2 = _seed(db)
    assert client.post("/cart/items", json={"item_id": str(i2.id)}).status_code == 201
    assert client.post("/checkout/start").status_code == 200
    conf = client.post(
        "/checkout/confirm",
        json={"email_contacto": "client@example.com", "metodo_envio": "recogida_tienda"},
    )
    order_id = conf.json()["id"]

    pay = client.post(f"/checkout/{order_id}/pay/redsys/start")
    ds_order = json.loads(base64.b64decode(pay.json()["Ds_MerchantParameters"]))["DS_MERCHANT_ORDER"]

    params_b64, signature = _sign_as_redsys({"Ds_Order": ds_order, "Ds_Response": "0180"})  # denegado
    notify = client.post(
        "/checkout/pay/redsys/notify",
        data={"Ds_SignatureVersion": "HMAC_SHA256_V1", "Ds_MerchantParameters": params_b64, "Ds_Signature": signature},
    )
    assert notify.status_code == 200
    db.expire_all()
    assert db.get(Order, uuid.UUID(order_id)).status == OrderStatus.cancelado
    assert db.get(Item, i2.id).status == ItemStatus.disponible
    assert _counter("denegado") >= 1


def test_checkout_notify_pago_no_encontrado_cuenta_metrica(client, db):
    antes = _counter("payment_not_found")
    params_b64, signature = _sign_as_redsys({"Ds_Order": "9999999999", "Ds_Response": "0000"})
    notify = client.post(
        "/checkout/pay/redsys/notify",
        data={"Ds_SignatureVersion": "HMAC_SHA256_V1", "Ds_MerchantParameters": params_b64, "Ds_Signature": signature},
    )
    assert notify.status_code == 404
    assert _counter("payment_not_found") == antes + 1


def test_checkout_notify_con_firma_invalida_es_rechazada(db, client):
    _, _, i2 = _seed(db)
    assert client.post("/cart/items", json={"item_id": str(i2.id)}).status_code == 201
    assert client.post("/checkout/start").status_code == 200
    conf = client.post(
        "/checkout/confirm",
        json={"email_contacto": "client@example.com", "metodo_envio": "recogida_tienda"},
    )
    order_id = conf.json()["id"]
    pay = client.post(f"/checkout/{order_id}/pay/redsys/start")
    ds_order = json.loads(base64.b64decode(pay.json()["Ds_MerchantParameters"]))["DS_MERCHANT_ORDER"]

    params_b64, _ = _sign_as_redsys({"Ds_Order": ds_order, "Ds_Response": "0000"})
    notify = client.post(
        "/checkout/pay/redsys/notify",
        data={"Ds_SignatureVersion": "HMAC_SHA256_V1", "Ds_MerchantParameters": params_b64, "Ds_Signature": "firma-falsa"},
    )
    assert notify.status_code == 400
    db.expire_all()
    assert db.get(Item, i2.id).status == ItemStatus.reservado


def test_pago_en_tienda_solo_con_recogida(db, client):
    """Paga al recoger no tiene sentido si el pedido se envía por correo:
    nadie enviaría un disco sin haberlo cobrado antes."""
    _, _, i2 = _seed(db)
    assert client.post("/cart/items", json={"item_id": str(i2.id)}).status_code == 201
    assert client.post("/checkout/start").status_code == 200
    conf = client.post(
        "/checkout/confirm",
        json={"email_contacto": "client@example.com", "metodo_envio": "envio", "metodo_pago": "tienda"},
    )
    assert conf.status_code == 422


def test_pago_en_tienda_admin_marca_pagado(db, client):
    """Flujo alternativo a Redsys para poder seguir probando el checkout (o
    para clientes que prefieren pagar al recoger): el pedido se queda en
    pendiente_pago hasta que un admin lo marca como pagado, momento en el
    que se vende de verdad el ejemplar."""
    _, _, i2 = _seed(db)
    assert client.post("/cart/items", json={"item_id": str(i2.id)}).status_code == 201
    assert client.post("/checkout/start").status_code == 200
    conf = client.post(
        "/checkout/confirm",
        json={"email_contacto": "client@example.com", "metodo_envio": "recogida_tienda", "metodo_pago": "tienda"},
    )
    assert conf.status_code == 201
    assert conf.json()["status"] == "pendiente_pago"
    assert conf.json()["metodo_pago"] == "tienda"
    order_id = conf.json()["id"]
    db.expire_all()
    assert db.get(Item, i2.id).status == ItemStatus.reservado

    access, _ = _login(client, "admin2@example.com")
    user = db.scalar(select(User).where(User.email == "admin2@example.com"))
    user.rol = "admin"
    db.commit()
    admin_access, _ = _login(client, "admin2@example.com")

    with contextlib.redirect_stdout(io.StringIO()):
        resp = client.patch(
            f"/admin/orders/{order_id}/status",
            json={"status": "pagado"},
            headers={"Authorization": f"Bearer {admin_access}"},
        )
    assert resp.status_code == 200
    db.expire_all()
    assert db.get(Order, uuid.UUID(order_id)).status == OrderStatus.pagado
    assert db.get(Item, i2.id).status == ItemStatus.vendido


def _admin_headers(client, db, email="admin-caixa@example.com"):
    _login(client, email)
    user = db.scalar(select(User).where(User.email == email))
    user.rol = "admin"
    db.commit()
    admin_access, _ = _login(client, email)
    return {"Authorization": f"Bearer {admin_access}"}


def test_marcar_pagado_tienda_efectivo_registra_moviment_caixa(db, client):
    """Cobrar en efectiu al TPV una comanda 'paga en recollir' ha de quadrar
    al tancament de caixa del dia, igual que una venda de mostrador normal
    (VentaExterna): com que l'Order no crea cap VentaExterna, cal un
    CajaMovimiento 'entrada' equivalent."""
    _, _, i2 = _seed(db)
    assert client.post("/cart/items", json={"item_id": str(i2.id)}).status_code == 201
    assert client.post("/checkout/start").status_code == 200
    conf = client.post(
        "/checkout/confirm",
        json={"email_contacto": "client@example.com", "metodo_envio": "recogida_tienda", "metodo_pago": "tienda"},
    )
    order_id = conf.json()["id"]

    with contextlib.redirect_stdout(io.StringIO()):
        headers = _admin_headers(client, db)
    assert client.post(
        "/admin/caja/apertura", json={"fecha_apertura": "2026-06-05T09:00:00", "fondo_inicial": "50.00"},
        headers=headers,
    ).status_code == 201

    resp = client.post(
        f"/admin/orders/{order_id}/marcar-pagado-tienda", json={"metodo_pago": "efectivo"}, headers=headers,
    )
    assert resp.status_code == 200
    db.expire_all()
    assert db.get(Order, uuid.UUID(order_id)).status == OrderStatus.pagado
    assert db.get(Item, i2.id).status == ItemStatus.vendido

    movs = client.get("/admin/caja/movimientos", headers=headers).json()
    assert len(movs) == 1
    assert movs[0]["tipo"] == "entrada"
    assert movs[0]["importe"] == str(conf.json()["total"])


def test_marcar_pagado_tienda_targeta_no_registra_moviment(db, client):
    """Pagar amb targeta no toca l'efectiu de caixa: no s'ha de crear cap
    CajaMovimiento (igual que una VentaExterna amb metodo_pago=tarjeta no
    compta cap a total_ventas_efectivo)."""
    _, _, i2 = _seed(db)
    assert client.post("/cart/items", json={"item_id": str(i2.id)}).status_code == 201
    assert client.post("/checkout/start").status_code == 200
    conf = client.post(
        "/checkout/confirm",
        json={"email_contacto": "client@example.com", "metodo_envio": "recogida_tienda", "metodo_pago": "tienda"},
    )
    order_id = conf.json()["id"]

    with contextlib.redirect_stdout(io.StringIO()):
        headers = _admin_headers(client, db, "admin-caixa2@example.com")
    assert client.post(
        "/admin/caja/apertura", json={"fecha_apertura": "2026-06-05T09:00:00", "fondo_inicial": "50.00"},
        headers=headers,
    ).status_code == 201

    resp = client.post(
        f"/admin/orders/{order_id}/marcar-pagado-tienda", json={"metodo_pago": "tarjeta"}, headers=headers,
    )
    assert resp.status_code == 200
    db.expire_all()
    assert db.get(Order, uuid.UUID(order_id)).status == OrderStatus.pagado

    movs = client.get("/admin/caja/movimientos", headers=headers).json()
    assert movs == []


def test_marcar_pagado_tienda_sense_sessio_caixa_no_falla(db, client):
    """Cobrar en efectiu sense cap sessió de caixa oberta no ha de fallar:
    l'Order es marca pagat igualment, només no hi ha res on apuntar
    l'entrada (mateix comportament que les compres a particulars)."""
    _, _, i2 = _seed(db)
    assert client.post("/cart/items", json={"item_id": str(i2.id)}).status_code == 201
    assert client.post("/checkout/start").status_code == 200
    conf = client.post(
        "/checkout/confirm",
        json={"email_contacto": "client@example.com", "metodo_envio": "recogida_tienda", "metodo_pago": "tienda"},
    )
    order_id = conf.json()["id"]

    with contextlib.redirect_stdout(io.StringIO()):
        headers = _admin_headers(client, db, "admin-caixa3@example.com")

    resp = client.post(
        f"/admin/orders/{order_id}/marcar-pagado-tienda", json={"metodo_pago": "efectivo"}, headers=headers,
    )
    assert resp.status_code == 200
    db.expire_all()
    assert db.get(Order, uuid.UUID(order_id)).status == OrderStatus.pagado


def test_marcar_pagado_tienda_rebutja_si_no_esta_pendent(db, client):
    _, _, i2 = _seed(db)
    assert client.post("/cart/items", json={"item_id": str(i2.id)}).status_code == 201
    assert client.post("/checkout/start").status_code == 200
    conf = client.post(
        "/checkout/confirm",
        json={"email_contacto": "client@example.com", "metodo_envio": "recogida_tienda"},
    )
    order_id = conf.json()["id"]
    assert conf.json()["metodo_pago"] == "redsys"

    with contextlib.redirect_stdout(io.StringIO()):
        headers = _admin_headers(client, db, "admin-caixa4@example.com")
    resp = client.post(
        f"/admin/orders/{order_id}/marcar-pagado-tienda", json={"metodo_pago": "efectivo"}, headers=headers,
    )
    assert resp.status_code == 409


def test_marcar_pagado_tienda_amb_preu_aplica_descompte(db, client):
    """El diàleg de cobrament permet canviar el preu (mateix comportament que
    vendre una reserva de PeticionCliente al TPV): en una comanda d'un sol
    disc, s'ha d'actualitzar l'OrderItem, el total de la comanda i l'import
    apuntat a caixa si es paga en efectiu."""
    _, _, i2 = _seed(db)
    assert client.post("/cart/items", json={"item_id": str(i2.id)}).status_code == 201
    assert client.post("/checkout/start").status_code == 200
    conf = client.post(
        "/checkout/confirm",
        json={"email_contacto": "client@example.com", "metodo_envio": "recogida_tienda", "metodo_pago": "tienda"},
    )
    order_id = conf.json()["id"]
    assert conf.json()["total"] == "18.00"

    with contextlib.redirect_stdout(io.StringIO()):
        headers = _admin_headers(client, db, "admin-descompte@example.com")
    assert client.post(
        "/admin/caja/apertura", json={"fecha_apertura": "2026-06-05T09:00:00", "fondo_inicial": "50.00"},
        headers=headers,
    ).status_code == 201

    resp = client.post(
        f"/admin/orders/{order_id}/marcar-pagado-tienda",
        json={"metodo_pago": "efectivo", "precio": "15.00"},
        headers=headers,
    )
    assert resp.status_code == 200
    db.expire_all()
    order = db.get(Order, uuid.UUID(order_id))
    assert order.status == OrderStatus.pagado
    assert order.total == Decimal("15.00")
    assert order.items[0].precio == Decimal("15.00")

    movs = client.get("/admin/caja/movimientos", headers=headers).json()
    assert movs[0]["importe"] == "15.00"


def test_marcar_pagado_tienda_amb_preu_en_comanda_multi_disc_falla(db, client):
    """No hi ha un únic preu unitari on aplicar el descompte si la comanda
    té més d'un disc: ha de rebutjar-se en comptes d'aplicar-lo a l'atzar
    a un dels dos."""
    _, i1, i2 = _seed(db)
    assert client.post("/cart/items", json={"item_id": str(i1.id)}).status_code == 201
    assert client.post("/cart/items", json={"item_id": str(i2.id)}).status_code == 201
    assert client.post("/checkout/start").status_code == 200
    conf = client.post(
        "/checkout/confirm",
        json={"email_contacto": "client@example.com", "metodo_envio": "recogida_tienda", "metodo_pago": "tienda"},
    )
    order_id = conf.json()["id"]

    with contextlib.redirect_stdout(io.StringIO()):
        headers = _admin_headers(client, db, "admin-descompte2@example.com")
    resp = client.post(
        f"/admin/orders/{order_id}/marcar-pagado-tienda",
        json={"metodo_pago": "efectivo", "precio": "30.00"},
        headers=headers,
    )
    assert resp.status_code == 422
    db.expire_all()
    assert db.get(Order, uuid.UUID(order_id)).status == OrderStatus.pendiente_pago


def test_pago_en_tienda_allarga_la_reserva_72h(db, client):
    """La reserva estàndard de carret (20 min) no dura prou perquè el client
    vingui a recollir i pagar en persona: confirm_checkout l'ha d'allargar,
    igual que fa erp.py per a una PeticionCliente 'recollida_paga_botiga'."""
    _, _, i2 = _seed(db)
    assert client.post("/cart/items", json={"item_id": str(i2.id)}).status_code == 201
    assert client.post("/checkout/start").status_code == 200
    conf = client.post(
        "/checkout/confirm",
        json={"email_contacto": "client@example.com", "metodo_envio": "recogida_tienda", "metodo_pago": "tienda"},
    )
    assert conf.status_code == 201
    db.expire_all()
    item = db.get(Item, i2.id)
    assert item.status == ItemStatus.reservado
    # SQLite (tests) guarda el datetime naive; normalitzem abans de comparar.
    reserved_until = item.reserved_until
    if reserved_until.tzinfo is None:
        reserved_until = reserved_until.replace(tzinfo=timezone.utc)
    # Molt més que els 20 min estàndard: comprovem que s'ha allargat de veritat.
    assert reserved_until > datetime.now(timezone.utc) + timedelta(hours=1)


def test_pago_en_tienda_caduca_si_no_es_reclama(db, client):
    """Si ningú ve a recollir i pagar dins la finestra allargada, l'exemplar
    torna a la venda i la comanda es cancel·la (en comptes de quedar-se
    'pendiente_pago' òrfena per sempre, sense que ningú se n'assabenti)."""
    _, _, i2 = _seed(db)
    assert client.post("/cart/items", json={"item_id": str(i2.id)}).status_code == 201
    assert client.post("/checkout/start").status_code == 200
    conf = client.post(
        "/checkout/confirm",
        json={"email_contacto": "client@example.com", "metodo_envio": "recogida_tienda", "metodo_pago": "tienda"},
    )
    order_id = conf.json()["id"]

    item_db = db.get(Item, i2.id)
    item_db.reserved_until = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    release_expired(db)

    db.expire_all()
    assert db.get(Item, i2.id).status == ItemStatus.disponible
    assert db.get(Order, uuid.UUID(order_id)).status == OrderStatus.cancelado


def test_admin_orders_pendientes_tienda(db, client):
    """El TPV ('Reserves web') ha de poder trobar les comandes web amb
    'paga en recollir' encara no pagades, igual que ja fa amb les
    PeticionCliente reservades a /admin/peticiones/reserves-recollida."""
    _, _, i2 = _seed(db)
    assert client.post("/cart/items", json={"item_id": str(i2.id)}).status_code == 201
    assert client.post("/checkout/start").status_code == 200
    conf = client.post(
        "/checkout/confirm",
        json={"email_contacto": "client@example.com", "metodo_envio": "recogida_tienda", "metodo_pago": "tienda"},
    )
    order_id = conf.json()["id"]

    access, _ = _login(client, "admin3@example.com")
    user = db.scalar(select(User).where(User.email == "admin3@example.com"))
    user.rol = "admin"
    db.commit()
    admin_access, _ = _login(client, "admin3@example.com")

    resp = client.get("/admin/orders/pendientes-tienda", headers={"Authorization": f"Bearer {admin_access}"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["order_id"] == order_id
    assert body[0]["email"] == "client@example.com"
    assert body[0]["items"][0]["item_id"] == str(i2.id)

    # Un cop marcada com a pagada, ja no ha de sortir a la llista.
    with contextlib.redirect_stdout(io.StringIO()):
        assert client.patch(
            f"/admin/orders/{order_id}/status", json={"status": "pagado"},
            headers={"Authorization": f"Bearer {admin_access}"},
        ).status_code == 200
    resp2 = client.get("/admin/orders/pendientes-tienda", headers={"Authorization": f"Bearer {admin_access}"})
    assert resp2.json() == []


def test_confirm_sin_start_no_vende_ni_crea_pedido(db, client):
    """/checkout/confirm no debe crear un pedido si el ejemplar nunca se
    reservó (saltarse /checkout/start): sin esto, un cliente podía comprar
    un disco que otra persona tenía reservado, robándole la reserva."""
    _, i1, _ = _seed(db)
    assert client.post("/cart/items", json={"item_id": str(i1.id)}).status_code == 201
    conf = client.post(
        "/checkout/confirm",
        json={"email_contacto": "atacante@example.com", "metodo_envio": "recogida_tienda"},
    )
    assert conf.status_code == 409
    db.expire_all()
    assert db.get(Item, i1.id).status == ItemStatus.disponible


def test_confirm_no_puede_robar_reserva_ajena(db, client):
    """Un item en el carrito de un atacante, reservado mientras tanto por otro
    cliente legítimo (vía /start), no puede colarse por /confirm del atacante
    sin que él mismo haya reservado."""
    _, i1, _ = _seed(db)
    assert client.post("/cart/items", json={"item_id": str(i1.id)}).status_code == 201
    assert reserve_items(db, [i1.id], uuid.uuid4()) == []  # otro carrito lo reserva mientras tanto

    conf = client.post(
        "/checkout/confirm",
        json={"email_contacto": "atacante@example.com", "metodo_envio": "recogida_tienda"},
    )
    assert conf.status_code == 409
    db.expire_all()
    # sigue reservado para el legítimo, no vendido al atacante
    assert db.get(Item, i1.id).status == ItemStatus.reservado


def test_magic_link_y_sesion(db, client):
    access, token = _login(client, "fan@example.com")
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.json()["email"] == "fan@example.com"
    # el enlace es de un solo uso
    assert client.post(f"/auth/magic-link/verify?token={token}").status_code == 400
    # refresh rotatorio con la cookie httpOnly
    assert client.post("/auth/refresh").status_code == 200
    # un cliente normal no entra al admin
    assert (
        client.get("/admin/orders", headers={"Authorization": f"Bearer {access}"}).status_code == 403
    )
