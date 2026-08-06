"""Tests del módulo ERP: compras (entradas de stock) y ventas externas."""

import contextlib
import io
import re
import uuid
from decimal import Decimal

from sqlalchemy import select

from app.models import Compra, Item, ItemStatus, Proveedor, Release, TipusIva, User, VentaExterna
from app.services.reservations import reserve_items


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_release(db, artista="Artista", titulo="Álbum", formato="LP") -> Release:
    r = Release(artista=artista, titulo=titulo, formato=formato)
    db.add(r)
    db.commit()
    return r


def _seed_item(db, release, precio="20.00", coste="10.00") -> Item:
    item = Item(
        release_id=release.id,
        precio=Decimal(precio),
        coste_adquisicion=Decimal(coste),
    )
    db.add(item)
    db.commit()
    return item


def _login(client, email: str) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert client.post("/auth/magic-link", json={"email": email}).status_code == 202
    token = re.search(r"token=([\w\-]+)", buf.getvalue()).group(1)
    resp = client.post(f"/auth/magic-link/verify?token={token}")
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _admin_token(client, db) -> str:
    access = _login(client, "admin@example.com")
    user = db.scalar(select(User).where(User.email == "admin@example.com"))
    user.rol = "admin"
    db.commit()
    return access


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _seed_tipus_iva(db, *, nom="General", pct="21.00", rebu=False) -> TipusIva:
    tipus = TipusIva(nom=nom, percentatge=Decimal(pct), es_rebu=rebu, actiu=True)
    db.add(tipus)
    db.commit()
    return tipus


# ---------------------------------------------------------------------------
# Proveedores
# ---------------------------------------------------------------------------

def test_crud_proveedor(db, client):
    admin = _admin_token(client, db)

    resp = client.post(
        "/admin/proveedores",
        json={"nombre": "Discos SL", "tipo": "distribuidor", "contacto": "info@discos.com"},
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    prov = resp.json()
    assert prov["nombre"] == "Discos SL"
    prov_id = prov["id"]

    resp = client.get("/admin/proveedores", headers=_auth(admin))
    assert resp.status_code == 200
    assert any(p["id"] == prov_id for p in resp.json())


def test_proveedor_nombre_unico(db, client):
    admin = _admin_token(client, db)
    payload = {"nombre": "Mismo Nombre"}
    client.post("/admin/proveedores", json=payload, headers=_auth(admin))
    resp = client.post("/admin/proveedores", json=payload, headers=_auth(admin))
    assert resp.status_code == 409


def test_crear_proveedor_amb_fitxa_completa(db, client):
    admin = _admin_token(client, db)
    resp = client.post(
        "/admin/proveedores",
        json={
            "nombre": "Discos Completo SL", "tipo": "distribuidor",
            "nif": "B12345678", "email": "contacto@discos.com", "telefon": "934567890",
            "direccion": "Carrer Pujades 113, 08005 Barcelona",
            "iban_proveidor": "ES9121000418450200051332",
            "metode_pagament": "transferencia", "dies_pagament": 30,
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    prov = resp.json()
    assert prov["nif"] == "B12345678"
    assert prov["direccion"] == "Carrer Pujades 113, 08005 Barcelona"
    assert prov["iban_proveidor"] == "ES9121000418450200051332"


def test_get_proveedor(db, client):
    admin = _admin_token(client, db)
    prov_id = client.post("/admin/proveedores", json={"nombre": "ProvX"}, headers=_auth(admin)).json()["id"]
    resp = client.get(f"/admin/proveedores/{prov_id}", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json()["nombre"] == "ProvX"


def test_update_proveedor(db, client):
    admin = _admin_token(client, db)
    prov_id = client.post("/admin/proveedores", json={"nombre": "ProvY"}, headers=_auth(admin)).json()["id"]
    resp = client.patch(
        f"/admin/proveedores/{prov_id}",
        json={"nombre": "ProvY", "nif": "B99999999", "direccion": "Carrer Nou 1"},
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["nif"] == "B99999999"
    assert body["direccion"] == "Carrer Nou 1"


def test_update_proveedor_nombre_duplicat_falla(db, client):
    admin = _admin_token(client, db)
    client.post("/admin/proveedores", json={"nombre": "Prov A"}, headers=_auth(admin))
    prov_b_id = client.post("/admin/proveedores", json={"nombre": "Prov B"}, headers=_auth(admin)).json()["id"]
    resp = client.patch(f"/admin/proveedores/{prov_b_id}", json={"nombre": "Prov A"}, headers=_auth(admin))
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Compras a particular — entrada instantània (no passa per Comanda)
# ---------------------------------------------------------------------------

def test_compra_a_particular_crea_items(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db, artista="Second Hand", titulo="Rarity")

    payload = {
        "nombre_particular": "Joan Puig",
        "fecha": "2026-06-05T17:30:00",
        "items": [
            {"release_id": str(r.id), "precio": "35.00", "coste_adquisicion": "20.00"},
        ],
    }
    resp = client.post("/admin/compras/particular", json=payload, headers=_auth(admin))
    assert resp.status_code == 201
    compra_id = uuid.UUID(resp.json()["id"])

    db.expire_all()
    compra = db.get(Compra, compra_id)
    assert compra.nombre_particular == "Joan Puig"
    assert compra.proveedor_id is None

    item = db.scalars(select(Item).where(Item.compra_id == compra_id)).first()
    assert item.coste_adquisicion == Decimal("20.00")
    assert item.status == ItemStatus.disponible
    assert item.fecha_entrada == compra.fecha


def test_compra_particular_registra_sortida_caixa_si_sessio_oberta(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db, artista="Second Hand", titulo="Rarity")

    sess_resp = client.post(
        "/admin/caja/apertura",
        json={"fecha_apertura": "2026-06-05T09:00:00", "fondo_inicial": "100.00"},
        headers=_auth(admin),
    )
    assert sess_resp.status_code == 201

    payload = {
        "nombre_particular": "Joan Puig",
        "fecha": "2026-06-05T17:30:00",
        "items": [{"release_id": str(r.id), "precio": "35.00", "coste_adquisicion": "20.00"}],
    }
    resp = client.post("/admin/compras/particular", json=payload, headers=_auth(admin))
    assert resp.status_code == 201

    movs = client.get("/admin/caja/movimientos", headers=_auth(admin)).json()
    assert len(movs) == 1
    assert movs[0]["tipo"] == "salida"
    assert movs[0]["importe"] == "20.00"
    assert "Joan Puig" in movs[0]["concepto"]


def test_compra_particular_sense_sessio_caixa_no_falla(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db)
    payload = {
        "nombre_particular": "Algú",
        "fecha": "2026-06-01T10:00:00",
        "items": [{"release_id": str(r.id), "precio": "10.00", "coste_adquisicion": "5.00"}],
    }
    resp = client.post("/admin/compras/particular", json=payload, headers=_auth(admin))
    assert resp.status_code == 201


def test_compra_particular_sin_nombre_falla(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db)
    payload = {
        "fecha": "2026-06-01T10:00:00",
        "items": [{"release_id": str(r.id), "precio": "10.00", "coste_adquisicion": "5.00"}],
    }
    resp = client.post("/admin/compras/particular", json=payload, headers=_auth(admin))
    assert resp.status_code == 422


def test_compra_particular_release_inexistente_falla(db, client):
    admin = _admin_token(client, db)
    payload = {
        "nombre_particular": "Algú",
        "fecha": "2026-06-01T10:00:00",
        "items": [{"release_id": str(uuid.uuid4()), "precio": "10.00", "coste_adquisicion": "5.00"}],
    }
    resp = client.post("/admin/compras/particular", json=payload, headers=_auth(admin))
    assert resp.status_code == 404


def test_compra_particular_sin_items_falla(db, client):
    admin = _admin_token(client, db)
    payload = {"nombre_particular": "Alguien", "fecha": "2026-06-01T10:00:00", "items": []}
    resp = client.post("/admin/compras/particular", json=payload, headers=_auth(admin))
    assert resp.status_code == 422


def test_detalle_compra(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db, artista="The Band", titulo="The Record")
    payload = {
        "nombre_particular": "ProveX Particular",
        "fecha": "2026-06-01T10:00:00",
        "items": [{"release_id": str(r.id), "precio": "18.00", "coste_adquisicion": "9.00"}],
    }
    compra_id = client.post("/admin/compras/particular", json=payload, headers=_auth(admin)).json()["id"]

    resp = client.get(f"/admin/compras/{compra_id}", headers=_auth(admin))
    assert resp.status_code == 200
    data = resp.json()
    assert data["num_albaran"] is None
    assert len(data["items"]) == 1
    assert data["items"][0]["artista"] == "The Band"
    assert data["items"][0]["coste_adquisicion"] == "9.00"


# ---------------------------------------------------------------------------
# Cerca i dashboard de compres/comandes
# ---------------------------------------------------------------------------

def test_list_compras_filtra_per_text_i_dates(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db)

    client.post("/admin/compras/particular", json={
        "nombre_particular": "Joan Puig", "fecha": "2026-01-10T10:00:00",
        "items": [{"release_id": str(r.id), "precio": "20.00", "coste_adquisicion": "10.00"}],
    }, headers=_auth(admin))
    client.post("/admin/compras/particular", json={
        "nombre_particular": "Maria Serra", "fecha": "2026-06-10T10:00:00",
        "items": [{"release_id": str(r.id), "precio": "20.00", "coste_adquisicion": "10.00"}],
    }, headers=_auth(admin))

    per_nom = client.get("/admin/compras?q=puig", headers=_auth(admin)).json()
    assert len(per_nom) == 1
    assert per_nom[0]["nombre_particular"] == "Joan Puig"

    per_data = client.get(
        "/admin/compras?desde=2026-05-01T00:00:00Z&hasta=2026-12-31T23:59:59Z",
        headers=_auth(admin),
    ).json()
    assert len(per_data) == 1
    assert per_data[0]["nombre_particular"] == "Maria Serra"

    sense_filtre = client.get("/admin/compras", headers=_auth(admin)).json()
    assert len(sense_filtre) == 2


def test_list_comandas_filtra_per_text_i_estat(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db)
    prov = Proveedor(nombre="Distri Vinil")
    db.add(prov)
    db.commit()

    client.post("/admin/comandas", json={
        "proveedor_id": str(prov.id), "fecha": "2026-06-01T10:00:00",
        "lineas": [{"release_id": str(r.id), "cantidad": 2}],
    }, headers=_auth(admin))

    per_text = client.get("/admin/comandas?q=distri", headers=_auth(admin)).json()
    assert len(per_text) == 1

    sense_match = client.get("/admin/comandas?q=inexistent", headers=_auth(admin)).json()
    assert len(sense_match) == 0

    per_estat = client.get("/admin/comandas?status=esborrany", headers=_auth(admin)).json()
    assert len(per_estat) == 1


def test_recepcio_comanda_omple_fecha_entrada_amb_fecha_de_compra(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db)
    prov = Proveedor(nombre="Distri Vinil")
    db.add(prov)
    db.commit()

    comanda_id = client.post("/admin/comandas", json={
        "proveedor_id": str(prov.id), "fecha": "2026-06-01T10:00:00",
        "lineas": [{"release_id": str(r.id), "cantidad": 1}],
    }, headers=_auth(admin)).json()["id"]
    linia_id = client.get(f"/admin/comandas/{comanda_id}", headers=_auth(admin)).json()["lineas"][0]["id"]
    client.patch(f"/admin/comandas/{comanda_id}/marcar-enviada", headers=_auth(admin))
    resp = client.post(f"/admin/comandas/{comanda_id}/recepcio", json={
        "fecha": "2026-06-10T09:00:00",
        "items": [{"comanda_linea_id": linia_id, "precio": "20.00", "coste_adquisicion": "12.00", "condicion": "nou"}],
    }, headers=_auth(admin))
    compra_id = uuid.UUID(resp.json()["compra_id"])

    db.expire_all()
    compra = db.get(Compra, compra_id)
    item = db.scalars(select(Item).where(Item.compra_id == compra_id)).first()
    assert item.fecha_entrada == compra.fecha


def test_compras_stats_totals_i_top_proveidors(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db)
    prov = Proveedor(nombre="Distri Vinil")
    db.add(prov)
    db.commit()

    # Comanda + recepció -> Compra a proveïdor dins d'aquest mes
    comanda_id = client.post("/admin/comandas", json={
        "proveedor_id": str(prov.id), "fecha": "2026-06-01T10:00:00",
        "lineas": [{"release_id": str(r.id), "cantidad": 1}],
    }, headers=_auth(admin)).json()["id"]
    linia_id = client.get(f"/admin/comandas/{comanda_id}", headers=_auth(admin)).json()["lineas"][0]["id"]
    client.patch(f"/admin/comandas/{comanda_id}/marcar-enviada", headers=_auth(admin))
    from datetime import datetime, timezone
    ara = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
    client.post(f"/admin/comandas/{comanda_id}/recepcio", json={
        "fecha": ara.isoformat(),
        "items": [{"comanda_linea_id": linia_id, "precio": "20.00", "coste_adquisicion": "12.00", "condicion": "nou"}],
    }, headers=_auth(admin))

    # Compra a particular dins d'aquest mes
    client.post("/admin/compras/particular", json={
        "nombre_particular": "Joan Puig", "fecha": ara.isoformat(),
        "items": [{"release_id": str(r.id), "precio": "20.00", "coste_adquisicion": "8.00"}],
    }, headers=_auth(admin))

    stats = client.get("/admin/compras/stats", headers=_auth(admin)).json()
    assert Decimal(stats["total_mes"]) == Decimal("20.00")
    assert Decimal(stats["total_mes_proveidor"]) == Decimal("12.00")
    assert Decimal(stats["total_mes_particular"]) == Decimal("8.00")
    assert stats["sense_facturar_count"] == 1
    assert Decimal(stats["sense_facturar_import"]) == Decimal("12.00")
    assert len(stats["top_proveidors"]) == 1
    assert stats["top_proveidors"][0]["nombre"] == "Distri Vinil"
    assert len(stats["serie_mensual"]) == 12


# ---------------------------------------------------------------------------
# Ventas externas: TPV + Discogs
# ---------------------------------------------------------------------------

def test_venta_mostrador(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db)
    item = _seed_item(db, r, precio="25.00", coste="12.00")

    resp = client.post(
        "/admin/ventas-externas",
        json={
            "item_id": str(item.id),
            "canal": "mostrador",
            "precio_venta": "25.00",
            "fecha": "2026-06-11T16:00:00",
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["canal"] == "mostrador"
    assert data["coste_adquisicion"] == "12.00"

    db.refresh(item)
    assert item.status == ItemStatus.retirado


def test_venta_mostrador_nou_descuenta_cantidad(db, client):
    from app.models import CondicionItem

    admin = _admin_token(client, db)
    r = _seed_release(db)
    item = Item(release_id=r.id, precio=Decimal("20.00"), condicion=CondicionItem.nou, cantidad=5)
    db.add(item)
    db.commit()

    resp = client.post(
        "/admin/ventas-externas",
        json={
            "item_id": str(item.id), "canal": "mostrador", "precio_venta": "40.00",
            "fecha": "2026-06-11T16:00:00", "cantidad": 2,
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 201

    db.refresh(item)
    assert item.cantidad == 3
    assert item.status == ItemStatus.disponible  # nou no usa status para regular la venta


def test_venta_mostrador_nou_sin_stock_suficiente_falla(db, client):
    from app.models import CondicionItem

    admin = _admin_token(client, db)
    r = _seed_release(db)
    item = Item(release_id=r.id, precio=Decimal("20.00"), condicion=CondicionItem.nou, cantidad=1)
    db.add(item)
    db.commit()

    resp = client.post(
        "/admin/ventas-externas",
        json={
            "item_id": str(item.id), "canal": "mostrador", "precio_venta": "40.00",
            "fecha": "2026-06-11T16:00:00", "cantidad": 2,
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 409
    db.refresh(item)
    assert item.cantidad == 1


def test_venta_discogs(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db)
    item = _seed_item(db, r, precio="18.00")

    resp = client.post(
        "/admin/ventas-externas",
        json={
            "item_id": str(item.id),
            "canal": "discogs",
            "precio_venta": "18.00",
            "fecha": "2026-06-11T12:00:00",
            "discogs_sale_id": 987654321,
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    assert resp.json()["discogs_sale_id"] == 987654321

    db.refresh(item)
    assert item.status == ItemStatus.retirado


def test_venta_item_reservado_falla(db, client):
    """Un item en el carrito de alguien no puede venderse en mostrador."""
    admin = _admin_token(client, db)
    r = _seed_release(db)
    item = _seed_item(db, r)
    reserve_items(db, [item.id], uuid.uuid4())

    resp = client.post(
        "/admin/ventas-externas",
        json={
            "item_id": str(item.id),
            "canal": "mostrador",
            "precio_venta": "20.00",
            "fecha": "2026-06-11T16:00:00",
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 409
    db.refresh(item)
    assert item.status == ItemStatus.reservado


def test_venta_item_ya_vendido_falla(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db)
    item = _seed_item(db, r)
    item.status = ItemStatus.vendido
    db.commit()

    resp = client.post(
        "/admin/ventas-externas",
        json={
            "item_id": str(item.id),
            "canal": "mostrador",
            "precio_venta": "20.00",
            "fecha": "2026-06-11T16:00:00",
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 409


def test_venta_item_inexistente_falla(db, client):
    admin = _admin_token(client, db)
    resp = client.post(
        "/admin/ventas-externas",
        json={
            "item_id": str(uuid.uuid4()),
            "canal": "mostrador",
            "precio_venta": "20.00",
            "fecha": "2026-06-11T16:00:00",
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 404


def test_venta_duplicada_falla(db, client):
    """Un mismo item no puede tener dos ventas externas."""
    admin = _admin_token(client, db)
    r = _seed_release(db)
    item = _seed_item(db, r)

    payload = {
        "item_id": str(item.id),
        "canal": "mostrador",
        "precio_venta": "20.00",
        "fecha": "2026-06-11T16:00:00",
    }
    assert client.post("/admin/ventas-externas", json=payload, headers=_auth(admin)).status_code == 201
    # El item ya está retirado, así que el segundo intento devuelve 409
    assert client.post("/admin/ventas-externas", json=payload, headers=_auth(admin)).status_code == 409


def test_venta_lote_varios_discos(db, client):
    """Cistella amb dos discos diferents: es venen tots dos en un sol lot."""
    admin = _admin_token(client, db)
    r1 = _seed_release(db, artista="Artista A", titulo="Disc A")
    r2 = _seed_release(db, artista="Artista B", titulo="Disc B")
    i1 = _seed_item(db, r1, precio="20.00", coste="10.00")
    i2 = _seed_item(db, r2, precio="15.00", coste="8.00")

    resp = client.post(
        "/admin/ventas-externas/lote",
        json={
            "lineas": [
                {"item_id": str(i1.id), "precio_venta": "20.00"},
                {"item_id": str(i2.id), "precio_venta": "15.00"},
            ],
            "canal": "mostrador",
            "metodo_pago": "efectivo",
            "fecha": "2026-06-11T16:00:00",
            "nombre_cliente": "Client Prova",
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data) == 2
    assert {d["item_id"] for d in data} == {str(i1.id), str(i2.id)}
    assert all(d["nombre_cliente"] == "Client Prova" for d in data)

    db.refresh(i1)
    db.refresh(i2)
    assert i1.status == ItemStatus.retirado
    assert i2.status == ItemStatus.retirado


def test_venta_lote_comparteix_ticket_id(db, client):
    """Les línies d'una mateixa cistella comparteixen ticket_id (per poder
    agrupar-les com un sol tiquet a Resum vendes), però cada venda suelta
    en té un de propi."""
    admin = _admin_token(client, db)
    r1 = _seed_release(db, artista="Artista A", titulo="Disc A")
    r2 = _seed_release(db, artista="Artista B", titulo="Disc B")
    i1 = _seed_item(db, r1, precio="20.00")
    i2 = _seed_item(db, r2, precio="15.00")
    i3 = _seed_item(db, _seed_release(db, artista="Artista C", titulo="Disc C"), precio="9.00")

    resp = client.post(
        "/admin/ventas-externas/lote",
        json={
            "lineas": [
                {"item_id": str(i1.id), "precio_venta": "20.00"},
                {"item_id": str(i2.id), "precio_venta": "15.00"},
            ],
            "canal": "mostrador", "metodo_pago": "efectivo", "fecha": "2026-06-11T16:00:00",
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    lote = resp.json()
    assert lote[0]["ticket_id"] == lote[1]["ticket_id"]

    resp_solt = client.post(
        "/admin/ventas-externas",
        json={"item_id": str(i3.id), "canal": "mostrador", "metodo_pago": "efectivo",
              "precio_venta": "9.00", "fecha": "2026-06-11T16:05:00"},
        headers=_auth(admin),
    )
    assert resp_solt.status_code == 201
    assert resp_solt.json()["ticket_id"] != lote[0]["ticket_id"]

    llistat = client.get("/admin/ventas-externas", headers=_auth(admin)).json()
    tickets = {v["item_id"]: v["ticket_id"] for v in llistat}
    assert tickets[str(i1.id)] == tickets[str(i2.id)]
    assert tickets[str(i3.id)] not in (tickets[str(i1.id)],)


def test_vincular_usuari_a_ticket(db, client):
    """Es pot lligar (o desvincular) un usuari registrat a totes les línies
    d'un tiquet ja cobrat, des de Resum vendes — no calia triar-lo al moment
    de la venda."""
    admin = _admin_token(client, db)
    r1 = _seed_release(db, artista="Artista A", titulo="Disc A")
    r2 = _seed_release(db, artista="Artista B", titulo="Disc B")
    i1 = _seed_item(db, r1, precio="20.00")
    i2 = _seed_item(db, r2, precio="15.00")

    cliente = User(email="marta@example.com", nombre="Marta")
    db.add(cliente)
    db.commit()

    resp = client.post(
        "/admin/ventas-externas/lote",
        json={
            "lineas": [
                {"item_id": str(i1.id), "precio_venta": "20.00"},
                {"item_id": str(i2.id), "precio_venta": "15.00"},
            ],
            "canal": "mostrador", "metodo_pago": "efectivo", "fecha": "2026-06-11T16:00:00",
        },
        headers=_auth(admin),
    )
    ticket_id = resp.json()[0]["ticket_id"]

    r = client.patch(
        f"/admin/ventas-externas/tickets/{ticket_id}/usuari",
        json={"user_id": str(cliente.id)},
        headers=_auth(admin),
    )
    assert r.status_code == 200
    assert all(v["user_id"] == str(cliente.id) for v in r.json())
    assert all(v["user_nom"] == "Marta" for v in r.json())

    # Es pot desvincular tornant a enviar user_id=None
    r2_resp = client.patch(
        f"/admin/ventas-externas/tickets/{ticket_id}/usuari",
        json={"user_id": None},
        headers=_auth(admin),
    )
    assert r2_resp.status_code == 200
    assert all(v["user_id"] is None for v in r2_resp.json())


def test_vincular_usuari_ticket_inexistent(db, client):
    admin = _admin_token(client, db)
    r = client.patch(
        f"/admin/ventas-externas/tickets/{uuid.uuid4()}/usuari",
        json={"user_id": None},
        headers=_auth(admin),
    )
    assert r.status_code == 404


def test_venta_lote_varies_copies_mateix_disc(db, client):
    """Cistella amb dues còpies físiques del mateix àlbum (mateix release,
    dos items), a preus diferents."""
    admin = _admin_token(client, db)
    r = _seed_release(db)
    i1 = _seed_item(db, r, precio="20.00")
    i2 = _seed_item(db, r, precio="22.00")

    resp = client.post(
        "/admin/ventas-externas/lote",
        json={
            "lineas": [
                {"item_id": str(i1.id), "precio_venta": "18.00"},
                {"item_id": str(i2.id), "precio_venta": "22.00"},
            ],
            "fecha": "2026-06-11T16:00:00",
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    assert {float(d["precio_venta"]) for d in resp.json()} == {18.0, 22.0}


def test_venta_lote_falla_atomicament_si_un_item_no_disponible(db, client):
    """Si un dels items del lot ja no està disponible, no s'ha de vendre CAP
    (ni cobrar-lo ni retirar-lo d'estoc): és tot o res."""
    admin = _admin_token(client, db)
    r = _seed_release(db)
    i1 = _seed_item(db, r, precio="20.00")
    i2 = _seed_item(db, r, precio="15.00")
    i2.status = ItemStatus.vendido
    db.commit()

    resp = client.post(
        "/admin/ventas-externas/lote",
        json={
            "lineas": [
                {"item_id": str(i1.id), "precio_venta": "20.00"},
                {"item_id": str(i2.id), "precio_venta": "15.00"},
            ],
            "fecha": "2026-06-11T16:00:00",
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 409

    db.refresh(i1)
    assert i1.status == ItemStatus.disponible
    assert client.get("/admin/ventas-externas", headers=_auth(admin)).json() == []


# ---------------------------------------------------------------------------
# Ventas externas: articles manuals (no venen del catàleg — llibres, samarretes...)
# ---------------------------------------------------------------------------

def test_venta_articulo_manual(db, client):
    admin = _admin_token(client, db)
    tipus = _seed_tipus_iva(db, nom="General", pct="21.00")

    resp = client.post(
        "/admin/ventas-externas",
        json={
            "descripcion": "Samarreta Ultra-Local Records (talla M)",
            "tipus_iva_id": tipus.id,
            "canal": "mostrador",
            "precio_venta": "18.00",
            "fecha": "2026-06-11T16:00:00",
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["item_id"] is None
    assert data["descripcion"] == "Samarreta Ultra-Local Records (talla M)"
    assert data["tipus_iva_id"] == tipus.id
    assert Decimal(data["iva_import"]) == Decimal("3.12")  # 18 * 21/121, arrodonit


def test_venta_articulo_manual_sense_descripcion_falla(db, client):
    admin = _admin_token(client, db)
    tipus = _seed_tipus_iva(db)
    resp = client.post(
        "/admin/ventas-externas",
        json={"tipus_iva_id": tipus.id, "canal": "mostrador", "precio_venta": "18.00", "fecha": "2026-06-11T16:00:00"},
        headers=_auth(admin),
    )
    assert resp.status_code == 422


def test_venta_articulo_manual_sense_tipus_iva_falla(db, client):
    admin = _admin_token(client, db)
    resp = client.post(
        "/admin/ventas-externas",
        json={"descripcion": "Llibre", "canal": "mostrador", "precio_venta": "18.00", "fecha": "2026-06-11T16:00:00"},
        headers=_auth(admin),
    )
    assert resp.status_code == 422


def test_venta_articulo_manual_amb_iva_rebu_falla(db, client):
    """REBU calcula l'IVA sobre el marge (venda - cost d'adquisició), que un
    article manual no té: no és una opció vàlida per a aquest cas."""
    admin = _admin_token(client, db)
    rebu = _seed_tipus_iva(db, nom="REBU", pct="21.00", rebu=True)
    resp = client.post(
        "/admin/ventas-externas",
        json={
            "descripcion": "Disc vintage sense fitxa al catàleg",
            "tipus_iva_id": rebu.id,
            "canal": "mostrador",
            "precio_venta": "18.00",
            "fecha": "2026-06-11T16:00:00",
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 422


def test_venta_lote_mixt_disc_i_article_manual(db, client):
    """Cistella amb un disc de catàleg i un article manual (llibre) a la
    vegada, cadascun amb el seu propi tipus d'IVA."""
    admin = _admin_token(client, db)
    tipus_general = _seed_tipus_iva(db, nom="General", pct="21.00")
    tipus_llibre = _seed_tipus_iva(db, nom="Llibres", pct="4.00")
    r = _seed_release(db)
    item = _seed_item(db, r, precio="20.00")

    resp = client.post(
        "/admin/ventas-externas/lote",
        json={
            "lineas": [
                {"item_id": str(item.id), "precio_venta": "20.00"},
                {"descripcion": "Vinyl. La biblia del col·leccionista", "tipus_iva_id": tipus_llibre.id, "precio_venta": "25.00"},
            ],
            "fecha": "2026-06-11T16:00:00",
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data) == 2
    manual = next(d for d in data if d["item_id"] is None)
    assert manual["descripcion"] == "Vinyl. La biblia del col·leccionista"
    assert manual["tipus_iva_id"] == tipus_llibre.id
    disc = next(d for d in data if d["item_id"] is not None)
    assert disc["item_id"] == str(item.id)

    db.refresh(item)
    assert item.status == ItemStatus.retirado


def test_listado_ventas_externas(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db)
    i1 = _seed_item(db, r, precio="20.00")
    i2 = _seed_item(db, r, precio="15.00")

    client.post("/admin/ventas-externas", json={"item_id": str(i1.id), "canal": "mostrador", "precio_venta": "20.00", "fecha": "2026-06-11T10:00:00"}, headers=_auth(admin))
    client.post("/admin/ventas-externas", json={"item_id": str(i2.id), "canal": "discogs", "precio_venta": "15.00", "fecha": "2026-06-11T11:00:00"}, headers=_auth(admin))

    todas = client.get("/admin/ventas-externas", headers=_auth(admin)).json()
    assert len(todas) == 2

    solo_discogs = client.get("/admin/ventas-externas?canal=discogs", headers=_auth(admin)).json()
    assert len(solo_discogs) == 1
    assert solo_discogs[0]["canal"] == "discogs"
