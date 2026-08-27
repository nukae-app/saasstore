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
    r = Release(artista=artista, title=titulo, formato=formato)
    db.add(r)
    db.commit()
    return r


def _seed_item(db, release, precio="20.00", coste="10.00") -> Item:
    item = Item(
        release_id=release.id,
        price=Decimal(precio),
        acquisition_cost=Decimal(coste),
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
    user.role = "admin"
    db.commit()
    return access


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _seed_tipus_iva(db, *, nom="General", pct="21.00", rebu=False) -> TipusIva:
    tipus = TipusIva(name=nom, percentage=Decimal(pct), is_rebu=rebu, active=True)
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
        json={"name": "Discos SL", "type": "distribuidor", "contact": "info@discos.com"},
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    prov = resp.json()
    assert prov["name"] == "Discos SL"
    prov_id = prov["id"]

    resp = client.get("/admin/proveedores", headers=_auth(admin))
    assert resp.status_code == 200
    assert any(p["id"] == prov_id for p in resp.json())


def test_proveedor_nombre_unico(db, client):
    admin = _admin_token(client, db)
    payload = {"name": "Mismo Nombre"}
    client.post("/admin/proveedores", json=payload, headers=_auth(admin))
    resp = client.post("/admin/proveedores", json=payload, headers=_auth(admin))
    assert resp.status_code == 409


def test_crear_proveedor_amb_fitxa_completa(db, client):
    admin = _admin_token(client, db)
    resp = client.post(
        "/admin/proveedores",
        json={
            "name": "Discos Completo SL", "type": "distribuidor",
            "nif": "B12345678", "email": "contacto@discos.com", "phone": "934567890",
            "address": "Carrer Pujades 113, 08005 Barcelona",
            "supplier_iban": "ES9121000418450200051332",
            "payment_method": "transferencia", "payment_days": 30,
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    prov = resp.json()
    assert prov["nif"] == "B12345678"
    assert prov["address"] == "Carrer Pujades 113, 08005 Barcelona"
    assert prov["supplier_iban"] == "ES9121000418450200051332"


def test_get_proveedor(db, client):
    admin = _admin_token(client, db)
    prov_id = client.post("/admin/proveedores", json={"name": "ProvX"}, headers=_auth(admin)).json()["id"]
    resp = client.get(f"/admin/proveedores/{prov_id}", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json()["name"] == "ProvX"


def test_update_proveedor(db, client):
    admin = _admin_token(client, db)
    prov_id = client.post("/admin/proveedores", json={"name": "ProvY"}, headers=_auth(admin)).json()["id"]
    resp = client.patch(
        f"/admin/proveedores/{prov_id}",
        json={"name": "ProvY", "nif": "B99999999", "address": "Carrer Nou 1"},
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["nif"] == "B99999999"
    assert body["address"] == "Carrer Nou 1"


def test_update_proveedor_nombre_duplicat_falla(db, client):
    admin = _admin_token(client, db)
    client.post("/admin/proveedores", json={"name": "Prov A"}, headers=_auth(admin))
    prov_b_id = client.post("/admin/proveedores", json={"name": "Prov B"}, headers=_auth(admin)).json()["id"]
    resp = client.patch(f"/admin/proveedores/{prov_b_id}", json={"name": "Prov A"}, headers=_auth(admin))
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Compras a particular — entrada instantània (no passa per Comanda)
# ---------------------------------------------------------------------------

def test_compra_a_particular_crea_items(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db, artista="Second Hand", titulo="Rarity")

    payload = {
        "individual_name": "Joan Puig",
        "date": "2026-06-05T17:30:00",
        "items": [
            {"release_id": str(r.id), "price": "35.00", "acquisition_cost": "20.00"},
        ],
    }
    resp = client.post("/admin/compras/particular", json=payload, headers=_auth(admin))
    assert resp.status_code == 201
    compra_id = uuid.UUID(resp.json()["id"])

    db.expire_all()
    compra = db.get(Compra, compra_id)
    assert compra.individual_name == "Joan Puig"
    assert compra.proveedor_id is None

    item = db.scalars(select(Item).where(Item.compra_id == compra_id)).first()
    assert item.acquisition_cost == Decimal("20.00")
    assert item.status == ItemStatus.disponible
    assert item.entry_date == compra.date


def test_compra_particular_registra_sortida_caixa_si_sessio_oberta(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db, artista="Second Hand", titulo="Rarity")

    sess_resp = client.post(
        "/admin/caja/apertura",
        json={"opened_at": "2026-06-05T09:00:00", "opening_float": "100.00"},
        headers=_auth(admin),
    )
    assert sess_resp.status_code == 201

    payload = {
        "individual_name": "Joan Puig",
        "date": "2026-06-05T17:30:00",
        "items": [{"release_id": str(r.id), "price": "35.00", "acquisition_cost": "20.00"}],
    }
    resp = client.post("/admin/compras/particular", json=payload, headers=_auth(admin))
    assert resp.status_code == 201

    movs = client.get("/admin/caja/movimientos", headers=_auth(admin)).json()
    assert len(movs) == 1
    assert movs[0]["type"] == "salida"
    assert movs[0]["amount"] == "20.00"
    assert "Joan Puig" in movs[0]["concept"]


def test_compra_particular_sense_sessio_caixa_no_falla(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db)
    payload = {
        "individual_name": "Algú",
        "date": "2026-06-01T10:00:00",
        "items": [{"release_id": str(r.id), "price": "10.00", "acquisition_cost": "5.00"}],
    }
    resp = client.post("/admin/compras/particular", json=payload, headers=_auth(admin))
    assert resp.status_code == 201


def test_compra_particular_sin_nombre_falla(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db)
    payload = {
        "date": "2026-06-01T10:00:00",
        "items": [{"release_id": str(r.id), "price": "10.00", "acquisition_cost": "5.00"}],
    }
    resp = client.post("/admin/compras/particular", json=payload, headers=_auth(admin))
    assert resp.status_code == 422


def test_compra_particular_release_inexistente_falla(db, client):
    admin = _admin_token(client, db)
    payload = {
        "individual_name": "Algú",
        "date": "2026-06-01T10:00:00",
        "items": [{"release_id": str(uuid.uuid4()), "price": "10.00", "acquisition_cost": "5.00"}],
    }
    resp = client.post("/admin/compras/particular", json=payload, headers=_auth(admin))
    assert resp.status_code == 404


def test_compra_particular_sin_items_falla(db, client):
    admin = _admin_token(client, db)
    payload = {"individual_name": "Alguien", "date": "2026-06-01T10:00:00", "items": []}
    resp = client.post("/admin/compras/particular", json=payload, headers=_auth(admin))
    assert resp.status_code == 422


def test_detalle_compra(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db, artista="The Band", titulo="The Record")
    payload = {
        "individual_name": "ProveX Particular",
        "date": "2026-06-01T10:00:00",
        "items": [{"release_id": str(r.id), "price": "18.00", "acquisition_cost": "9.00"}],
    }
    compra_id = client.post("/admin/compras/particular", json=payload, headers=_auth(admin)).json()["id"]

    resp = client.get(f"/admin/compras/{compra_id}", headers=_auth(admin))
    assert resp.status_code == 200
    data = resp.json()
    assert data["delivery_note_number"] is None
    assert len(data["items"]) == 1
    assert data["items"][0]["artista"] == "The Band"
    assert data["items"][0]["acquisition_cost"] == "9.00"


# ---------------------------------------------------------------------------
# Cerca i dashboard de compres/comandes
# ---------------------------------------------------------------------------

def test_list_compras_filtra_per_text_i_dates(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db)

    client.post("/admin/compras/particular", json={
        "individual_name": "Joan Puig", "date": "2026-01-10T10:00:00",
        "items": [{"release_id": str(r.id), "price": "20.00", "acquisition_cost": "10.00"}],
    }, headers=_auth(admin))
    client.post("/admin/compras/particular", json={
        "individual_name": "Maria Serra", "date": "2026-06-10T10:00:00",
        "items": [{"release_id": str(r.id), "price": "20.00", "acquisition_cost": "10.00"}],
    }, headers=_auth(admin))

    per_nom = client.get("/admin/compras?q=puig", headers=_auth(admin)).json()
    assert len(per_nom) == 1
    assert per_nom[0]["individual_name"] == "Joan Puig"

    per_data = client.get(
        "/admin/compras?desde=2026-05-01T00:00:00Z&hasta=2026-12-31T23:59:59Z",
        headers=_auth(admin),
    ).json()
    assert len(per_data) == 1
    assert per_data[0]["individual_name"] == "Maria Serra"

    sense_filtre = client.get("/admin/compras", headers=_auth(admin)).json()
    assert len(sense_filtre) == 2


def test_list_comandas_filtra_per_text_i_estat(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db)
    prov = Proveedor(name="Distri Vinil")
    db.add(prov)
    db.commit()

    client.post("/admin/comandas", json={
        "proveedor_id": str(prov.id), "date": "2026-06-01T10:00:00",
        "lineas": [{"release_id": str(r.id), "quantity": 2}],
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
    prov = Proveedor(name="Distri Vinil")
    db.add(prov)
    db.commit()

    comanda_id = client.post("/admin/comandas", json={
        "proveedor_id": str(prov.id), "date": "2026-06-01T10:00:00",
        "lineas": [{"release_id": str(r.id), "quantity": 1}],
    }, headers=_auth(admin)).json()["id"]
    linia_id = client.get(f"/admin/comandas/{comanda_id}", headers=_auth(admin)).json()["lineas"][0]["id"]
    client.patch(f"/admin/comandas/{comanda_id}/marcar-enviada", headers=_auth(admin))
    resp = client.post(f"/admin/comandas/{comanda_id}/recepcio", json={
        "date": "2026-06-10T09:00:00",
        "items": [{"comanda_linea_id": linia_id, "price": "20.00", "acquisition_cost": "12.00", "condition": "nou"}],
    }, headers=_auth(admin))
    compra_id = uuid.UUID(resp.json()["compra_id"])

    db.expire_all()
    compra = db.get(Compra, compra_id)
    item = db.scalars(select(Item).where(Item.compra_id == compra_id)).first()
    assert item.entry_date == compra.date


def test_compras_stats_totals_i_top_proveidors(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db)
    prov = Proveedor(name="Distri Vinil")
    db.add(prov)
    db.commit()

    # Comanda + recepció -> Compra a proveïdor dins d'aquest mes
    comanda_id = client.post("/admin/comandas", json={
        "proveedor_id": str(prov.id), "date": "2026-06-01T10:00:00",
        "lineas": [{"release_id": str(r.id), "quantity": 1}],
    }, headers=_auth(admin)).json()["id"]
    linia_id = client.get(f"/admin/comandas/{comanda_id}", headers=_auth(admin)).json()["lineas"][0]["id"]
    client.patch(f"/admin/comandas/{comanda_id}/marcar-enviada", headers=_auth(admin))
    from datetime import datetime, timezone
    ara = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
    client.post(f"/admin/comandas/{comanda_id}/recepcio", json={
        "date": ara.isoformat(),
        "items": [{"comanda_linea_id": linia_id, "price": "20.00", "acquisition_cost": "12.00", "condition": "nou"}],
    }, headers=_auth(admin))

    # Compra a particular dins d'aquest mes
    client.post("/admin/compras/particular", json={
        "individual_name": "Joan Puig", "date": ara.isoformat(),
        "items": [{"release_id": str(r.id), "price": "20.00", "acquisition_cost": "8.00"}],
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
            "channel": "mostrador",
            "sale_price": "25.00",
            "date": "2026-06-11T16:00:00",
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["channel"] == "mostrador"
    assert data["coste_adquisicion"] == "12.00"

    db.refresh(item)
    assert item.status == ItemStatus.retirado


def test_venta_mostrador_nou_descuenta_cantidad(db, client):
    from app.models import CondicionItem

    admin = _admin_token(client, db)
    r = _seed_release(db)
    item = Item(release_id=r.id, price=Decimal("20.00"), condition=CondicionItem.nou, quantity=5)
    db.add(item)
    db.commit()

    resp = client.post(
        "/admin/ventas-externas",
        json={
            "item_id": str(item.id), "channel": "mostrador", "sale_price": "40.00",
            "date": "2026-06-11T16:00:00", "quantity": 2,
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 201

    db.refresh(item)
    assert item.quantity == 3
    assert item.status == ItemStatus.disponible  # nou no usa status para regular la venta


def test_venta_mostrador_nou_sin_stock_suficiente_falla(db, client):
    from app.models import CondicionItem

    admin = _admin_token(client, db)
    r = _seed_release(db)
    item = Item(release_id=r.id, price=Decimal("20.00"), condition=CondicionItem.nou, quantity=1)
    db.add(item)
    db.commit()

    resp = client.post(
        "/admin/ventas-externas",
        json={
            "item_id": str(item.id), "channel": "mostrador", "sale_price": "40.00",
            "date": "2026-06-11T16:00:00", "quantity": 2,
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 409
    db.refresh(item)
    assert item.quantity == 1


def test_venta_discogs(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db)
    item = _seed_item(db, r, precio="18.00")

    resp = client.post(
        "/admin/ventas-externas",
        json={
            "item_id": str(item.id),
            "channel": "discogs",
            "sale_price": "18.00",
            "date": "2026-06-11T12:00:00",
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
            "channel": "mostrador",
            "sale_price": "20.00",
            "date": "2026-06-11T16:00:00",
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
            "channel": "mostrador",
            "sale_price": "20.00",
            "date": "2026-06-11T16:00:00",
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
            "channel": "mostrador",
            "sale_price": "20.00",
            "date": "2026-06-11T16:00:00",
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
        "channel": "mostrador",
        "sale_price": "20.00",
        "date": "2026-06-11T16:00:00",
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
                {"item_id": str(i1.id), "sale_price": "20.00"},
                {"item_id": str(i2.id), "sale_price": "15.00"},
            ],
            "channel": "mostrador",
            "payment_method": "efectivo",
            "date": "2026-06-11T16:00:00",
            "client_name": "Client Prova",
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data) == 2
    assert {d["item_id"] for d in data} == {str(i1.id), str(i2.id)}
    assert all(d["client_name"] == "Client Prova" for d in data)

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
                {"item_id": str(i1.id), "sale_price": "20.00"},
                {"item_id": str(i2.id), "sale_price": "15.00"},
            ],
            "channel": "mostrador", "payment_method": "efectivo", "date": "2026-06-11T16:00:00",
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    lote = resp.json()
    assert lote[0]["ticket_id"] == lote[1]["ticket_id"]

    resp_solt = client.post(
        "/admin/ventas-externas",
        json={"item_id": str(i3.id), "channel": "mostrador", "payment_method": "efectivo",
              "sale_price": "9.00", "date": "2026-06-11T16:05:00"},
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

    cliente = User(email="marta@example.com", name="Marta")
    db.add(cliente)
    db.commit()

    resp = client.post(
        "/admin/ventas-externas/lote",
        json={
            "lineas": [
                {"item_id": str(i1.id), "sale_price": "20.00"},
                {"item_id": str(i2.id), "sale_price": "15.00"},
            ],
            "channel": "mostrador", "payment_method": "efectivo", "date": "2026-06-11T16:00:00",
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
                {"item_id": str(i1.id), "sale_price": "18.00"},
                {"item_id": str(i2.id), "sale_price": "22.00"},
            ],
            "date": "2026-06-11T16:00:00",
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    assert {float(d["sale_price"]) for d in resp.json()} == {18.0, 22.0}


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
                {"item_id": str(i1.id), "sale_price": "20.00"},
                {"item_id": str(i2.id), "sale_price": "15.00"},
            ],
            "date": "2026-06-11T16:00:00",
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
            "description": "Samarreta Ultra-Local Records (talla M)",
            "tipus_iva_id": tipus.id,
            "channel": "mostrador",
            "sale_price": "18.00",
            "date": "2026-06-11T16:00:00",
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["item_id"] is None
    assert data["description"] == "Samarreta Ultra-Local Records (talla M)"
    assert data["tipus_iva_id"] == tipus.id
    assert Decimal(data["vat_amount"]) == Decimal("3.12")  # 18 * 21/121, arrodonit


def test_venta_articulo_manual_sense_descripcion_falla(db, client):
    admin = _admin_token(client, db)
    tipus = _seed_tipus_iva(db)
    resp = client.post(
        "/admin/ventas-externas",
        json={"tipus_iva_id": tipus.id, "channel": "mostrador", "sale_price": "18.00", "date": "2026-06-11T16:00:00"},
        headers=_auth(admin),
    )
    assert resp.status_code == 422


def test_venta_articulo_manual_sense_tipus_iva_falla(db, client):
    admin = _admin_token(client, db)
    resp = client.post(
        "/admin/ventas-externas",
        json={"description": "Llibre", "channel": "mostrador", "sale_price": "18.00", "date": "2026-06-11T16:00:00"},
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
            "description": "Disc vintage sense fitxa al catàleg",
            "tipus_iva_id": rebu.id,
            "channel": "mostrador",
            "sale_price": "18.00",
            "date": "2026-06-11T16:00:00",
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
                {"item_id": str(item.id), "sale_price": "20.00"},
                {"description": "Vinyl. La biblia del col·leccionista", "tipus_iva_id": tipus_llibre.id, "sale_price": "25.00"},
            ],
            "date": "2026-06-11T16:00:00",
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data) == 2
    manual = next(d for d in data if d["item_id"] is None)
    assert manual["description"] == "Vinyl. La biblia del col·leccionista"
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

    client.post("/admin/ventas-externas", json={"item_id": str(i1.id), "channel": "mostrador", "sale_price": "20.00", "date": "2026-06-11T10:00:00"}, headers=_auth(admin))
    client.post("/admin/ventas-externas", json={"item_id": str(i2.id), "channel": "discogs", "sale_price": "15.00", "date": "2026-06-11T11:00:00"}, headers=_auth(admin))

    todas = client.get("/admin/ventas-externas", headers=_auth(admin)).json()
    assert len(todas) == 2

    solo_discogs = client.get("/admin/ventas-externas?canal=discogs", headers=_auth(admin)).json()
    assert len(solo_discogs) == 1
    assert solo_discogs[0]["channel"] == "discogs"
