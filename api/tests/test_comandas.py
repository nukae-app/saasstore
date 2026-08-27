"""Tests del flux de comandes a proveïdor: comanda -> PDF/enviar -> recepció -> stock."""

import contextlib
import io
import re
import uuid
from decimal import Decimal

from sqlalchemy import select

from app.models import Comanda, EstadoComanda, Item, Proveedor, RecordProduct, Release, User
from app.routers import erp as erp_module


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


def _seed_release(db, artista="Artista", titulo="Àlbum") -> Release:
    r = Release(artista=artista, title=titulo, formato="LP")
    db.add(r)
    db.commit()
    return r


def _seed_proveedor(db, email="prov@example.com") -> Proveedor:
    p = Proveedor(name="DistroX", email=email)
    db.add(p)
    db.commit()
    return p


def test_crear_comanda(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = _seed_release(db)

    payload = {
        "proveedor_id": str(prov.id),
        "date": "2026-06-01T10:00:00",
        "lineas": [{"release_id": str(release.id), "quantity": 3, "estimated_unit_price": "12.00"}],
    }
    resp = client.post("/admin/comandas", json=payload, headers=_auth(admin))
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "esborrany"
    assert body["order_number"] == "2026-000001"
    assert len(body["lineas"]) == 1
    assert body["lineas"][0]["quantity"] == 3
    assert body["lineas"][0]["received_quantity"] == 0


def test_numeracio_comanda_es_correlativa_per_any(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = _seed_release(db)
    payload = {
        "proveedor_id": str(prov.id), "date": "2026-01-15T10:00:00",
        "lineas": [{"release_id": str(release.id), "quantity": 1}],
    }
    n1 = client.post("/admin/comandas", json=payload, headers=_auth(admin)).json()["order_number"]
    n2 = client.post("/admin/comandas", json=payload, headers=_auth(admin)).json()["order_number"]
    assert n1 == "2026-000001"
    assert n2 == "2026-000002"

    payload_altre_any = {**payload, "date": "2027-01-15T10:00:00"}
    n3 = client.post("/admin/comandas", json=payload_altre_any, headers=_auth(admin)).json()["order_number"]
    assert n3 == "2027-000001"


def test_comanda_release_inexistent_falla(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    payload = {
        "proveedor_id": str(prov.id), "date": "2026-06-01T10:00:00",
        "lineas": [{"release_id": str(uuid.uuid4()), "quantity": 1}],
    }
    resp = client.post("/admin/comandas", json=payload, headers=_auth(admin))
    assert resp.status_code == 404


def test_pdf_comanda(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = _seed_release(db)
    payload = {
        "proveedor_id": str(prov.id), "date": "2026-06-01T10:00:00",
        "lineas": [{"release_id": str(release.id), "quantity": 2, "estimated_unit_price": "10.00"}],
    }
    comanda_id = client.post("/admin/comandas", json=payload, headers=_auth(admin)).json()["id"]

    resp = client.get(f"/admin/comandas/{comanda_id}/pdf", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"


def test_marcar_enviada_manual(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = _seed_release(db)
    payload = {
        "proveedor_id": str(prov.id), "date": "2026-06-01T10:00:00",
        "lineas": [{"release_id": str(release.id), "quantity": 1}],
    }
    comanda_id = client.post("/admin/comandas", json=payload, headers=_auth(admin)).json()["id"]

    resp = client.patch(f"/admin/comandas/{comanda_id}/marcar-enviada", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json()["status"] == "enviada"


def test_enviar_comanda_per_email(db, client, monkeypatch):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db, email="prov@example.com")
    release = _seed_release(db)
    payload = {
        "proveedor_id": str(prov.id), "date": "2026-06-01T10:00:00",
        "lineas": [{"release_id": str(release.id), "quantity": 1, "estimated_unit_price": "10.00"}],
    }
    comanda_id = client.post("/admin/comandas", json=payload, headers=_auth(admin)).json()["id"]

    calls = []
    monkeypatch.setattr(erp_module.comandas, "send_email", lambda **kw: calls.append(kw))

    resp = client.post(f"/admin/comandas/{comanda_id}/enviar", headers=_auth(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "enviada"
    assert body["sent_at"] is not None
    assert len(calls) == 1
    assert calls[0]["to"] == "prov@example.com"
    assert calls[0]["attachment"][2] == "application/pdf"


def test_enviar_comanda_sense_email_proveidor_falla(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db, email=None)
    release = _seed_release(db)
    payload = {
        "proveedor_id": str(prov.id), "date": "2026-06-01T10:00:00",
        "lineas": [{"release_id": str(release.id), "quantity": 1}],
    }
    comanda_id = client.post("/admin/comandas", json=payload, headers=_auth(admin)).json()["id"]

    resp = client.post(f"/admin/comandas/{comanda_id}/enviar", headers=_auth(admin))
    assert resp.status_code == 422


def test_cancelar_comanda(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = _seed_release(db)
    payload = {
        "proveedor_id": str(prov.id), "date": "2026-06-01T10:00:00",
        "lineas": [{"release_id": str(release.id), "quantity": 1}],
    }
    comanda_id = client.post("/admin/comandas", json=payload, headers=_auth(admin)).json()["id"]

    resp = client.patch(f"/admin/comandas/{comanda_id}/cancelar", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelada"


def test_eliminar_comanda_no_esborrany_falla(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = _seed_release(db)
    payload = {
        "proveedor_id": str(prov.id), "date": "2026-06-01T10:00:00",
        "lineas": [{"release_id": str(release.id), "quantity": 1}],
    }
    comanda_id = client.post("/admin/comandas", json=payload, headers=_auth(admin)).json()["id"]
    client.patch(f"/admin/comandas/{comanda_id}/marcar-enviada", headers=_auth(admin))

    resp = client.delete(f"/admin/comandas/{comanda_id}", headers=_auth(admin))
    assert resp.status_code == 409


def test_recepcio_total_crea_compra_i_items(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = _seed_release(db)
    payload = {
        "proveedor_id": str(prov.id), "date": "2026-06-01T10:00:00",
        "lineas": [{"release_id": str(release.id), "quantity": 2, "estimated_unit_price": "10.00"}],
    }
    comanda_resp = client.post("/admin/comandas", json=payload, headers=_auth(admin)).json()
    comanda_id = comanda_resp["id"]
    linea_id = comanda_resp["lineas"][0]["id"]
    client.patch(f"/admin/comandas/{comanda_id}/marcar-enviada", headers=_auth(admin))

    recepcio_payload = {
        "date": "2026-06-10T10:00:00",
        "delivery_note_number": "ALB-1",
        "items": [
            {"comanda_linea_id": linea_id, "price": "20.00", "condition": "segona_ma", "acquisition_cost": "10.00"},
            {"comanda_linea_id": linea_id, "price": "22.00", "condition": "segona_ma", "acquisition_cost": "10.00"},
        ],
    }
    resp = client.post(f"/admin/comandas/{comanda_id}/recepcio", json=recepcio_payload, headers=_auth(admin))
    assert resp.status_code == 201
    body = resp.json()
    assert body["items_creados"] == 2
    assert body["comanda_status"] == "rebuda"

    db.expire_all()
    compra_id = uuid.UUID(body["compra_id"])
    items = db.scalars(select(Item).where(Item.compra_id == compra_id)).all()
    assert len(items) == 2
    assert all(i.release_id == release.id for i in items)

    comanda = db.get(Comanda, uuid.UUID(comanda_id))
    assert comanda.status == EstadoComanda.rebuda
    assert comanda.lineas[0].received_quantity == 2


def test_recepcio_nou_agrega_en_una_sola_linia_amb_cost_mitja(db, client):
    """Stock agregado: discos nous s'acumulen en UNA sola fila Item (en
    comptes d'una per unitat), i el coste_adquisicion passa a ser un cost
    mitjà ponderat entre recepcions successives."""
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = _seed_release(db)
    payload = {
        "proveedor_id": str(prov.id), "date": "2026-06-01T10:00:00",
        "lineas": [{"release_id": str(release.id), "quantity": 8, "estimated_unit_price": "10.00"}],
    }
    comanda_resp = client.post("/admin/comandas", json=payload, headers=_auth(admin)).json()
    comanda_id = comanda_resp["id"]
    linea_id = comanda_resp["lineas"][0]["id"]
    client.patch(f"/admin/comandas/{comanda_id}/marcar-enviada", headers=_auth(admin))

    # Primera recepció: 5 unitats a cost 10.00 (condicion="nou" per defecte).
    resp1 = client.post(
        f"/admin/comandas/{comanda_id}/recepcio",
        json={
            "date": "2026-06-10T10:00:00",
            "items": [{"comanda_linea_id": linea_id, "price": "20.00", "acquisition_cost": "10.00", "quantity": 5}],
        },
        headers=_auth(admin),
    )
    assert resp1.status_code == 201

    db.expire_all()
    items = db.scalars(select(Item).where(Item.release_id == release.id)).all()
    assert len(items) == 1
    assert items[0].quantity == 5
    assert items[0].acquisition_cost == Decimal("10.00")
    primera_compra_id = items[0].compra_id

    # Segona recepció, ALTRA compra: 3 unitats més a cost 14.00 -> mitjana ponderada.
    resp2 = client.post(
        f"/admin/comandas/{comanda_id}/recepcio",
        json={
            "date": "2026-06-15T10:00:00",
            "items": [{"comanda_linea_id": linea_id, "price": "22.00", "acquisition_cost": "14.00", "quantity": 3}],
        },
        headers=_auth(admin),
    )
    assert resp2.status_code == 201

    db.expire_all()
    items = db.scalars(select(Item).where(Item.release_id == release.id)).all()
    assert len(items) == 1  # sigue siendo UNA sola línea, no una por recepción
    item = items[0]
    assert item.quantity == 8
    assert item.acquisition_cost == Decimal("11.50")  # (5*10 + 3*14) / 8
    assert item.price == Decimal("22.00")  # el precio de venta se actualiza al de la última recepción
    assert item.compra_id != primera_compra_id  # apunta a la última compra que la tocó

    comanda = db.get(Comanda, uuid.UUID(comanda_id))
    assert comanda.status == EstadoComanda.rebuda


def test_recepcio_parcial_deixa_comanda_oberta(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = _seed_release(db)
    payload = {
        "proveedor_id": str(prov.id), "date": "2026-06-01T10:00:00",
        "lineas": [{"release_id": str(release.id), "quantity": 3, "estimated_unit_price": "10.00"}],
    }
    comanda_resp = client.post("/admin/comandas", json=payload, headers=_auth(admin)).json()
    comanda_id = comanda_resp["id"]
    linea_id = comanda_resp["lineas"][0]["id"]
    client.patch(f"/admin/comandas/{comanda_id}/marcar-enviada", headers=_auth(admin))

    recepcio_payload = {
        "date": "2026-06-10T10:00:00",
        "items": [{"comanda_linea_id": linea_id, "price": "20.00"}],
    }
    resp = client.post(f"/admin/comandas/{comanda_id}/recepcio", json=recepcio_payload, headers=_auth(admin))
    assert resp.status_code == 201
    assert resp.json()["comanda_status"] == "rebuda_parcial"

    # segona recepció completa la resta
    recepcio_payload_2 = {
        "date": "2026-06-12T10:00:00",
        "items": [
            {"comanda_linea_id": linea_id, "price": "20.00"},
            {"comanda_linea_id": linea_id, "price": "20.00"},
        ],
    }
    resp2 = client.post(f"/admin/comandas/{comanda_id}/recepcio", json=recepcio_payload_2, headers=_auth(admin))
    assert resp2.status_code == 201
    assert resp2.json()["comanda_status"] == "rebuda"


def test_recepcio_excedeix_quantitat_falla(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = _seed_release(db)
    payload = {
        "proveedor_id": str(prov.id), "date": "2026-06-01T10:00:00",
        "lineas": [{"release_id": str(release.id), "quantity": 1, "estimated_unit_price": "10.00"}],
    }
    comanda_resp = client.post("/admin/comandas", json=payload, headers=_auth(admin)).json()
    comanda_id = comanda_resp["id"]
    linea_id = comanda_resp["lineas"][0]["id"]
    client.patch(f"/admin/comandas/{comanda_id}/marcar-enviada", headers=_auth(admin))

    recepcio_payload = {
        "date": "2026-06-10T10:00:00",
        "items": [
            {"comanda_linea_id": linea_id, "price": "20.00"},
            {"comanda_linea_id": linea_id, "price": "20.00"},
        ],
    }
    resp = client.post(f"/admin/comandas/{comanda_id}/recepcio", json=recepcio_payload, headers=_auth(admin))
    assert resp.status_code == 422


def test_recepcio_comanda_esborrany_falla(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = _seed_release(db)
    payload = {
        "proveedor_id": str(prov.id), "date": "2026-06-01T10:00:00",
        "lineas": [{"release_id": str(release.id), "quantity": 1}],
    }
    comanda_resp = client.post("/admin/comandas", json=payload, headers=_auth(admin)).json()
    comanda_id = comanda_resp["id"]
    linea_id = comanda_resp["lineas"][0]["id"]

    recepcio_payload = {"date": "2026-06-10T10:00:00", "items": [{"comanda_linea_id": linea_id, "price": "20.00"}]}
    resp = client.post(f"/admin/comandas/{comanda_id}/recepcio", json=recepcio_payload, headers=_auth(admin))
    assert resp.status_code == 409


def test_eliminar_release_amb_linea_comanda_falla(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = _seed_release(db)
    payload = {
        "proveedor_id": str(prov.id), "date": "2026-06-01T10:00:00",
        "lineas": [{"release_id": str(release.id), "quantity": 1}],
    }
    client.post("/admin/comandas", json=payload, headers=_auth(admin))

    resp = client.delete(f"/admin/releases/{release.id}", headers=_auth(admin))
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Import CSV per afegir línies en bloc (resol però no crea la comanda)
# ---------------------------------------------------------------------------

def test_plantilla_comanda_csv(db, client):
    admin = _admin_token(client, db)
    resp = client.get("/admin/comandas/plantilla.csv", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.text.strip().split("\n")[0] == "discogs_release_id,cantidad,precio_unitario_estimado"


def test_resolver_csv_crea_releases_i_retorna_lineas(db, client, monkeypatch):
    admin = _admin_token(client, db)
    r_existent = _seed_release(db, artista="Ja existeix", titulo="Disc")
    r_existent.discogs_release_id = 111
    db.commit()

    def fake_get_release(token, discogs_release_id):
        assert discogs_release_id == 222
        return {
            "discogs_release_id": 222, "artista": "Nou Artista", "titulo": "Nou Disc",
            "sello": "Sello X", "anio": 1999, "genero": "Funk", "estilos": None,
            "pais": "US", "imagen_url": None, "tracklist": [], "credits": [],
        }
    monkeypatch.setattr(erp_module.comandas.discogs, "get_release", fake_get_release)

    csv_text = "discogs_release_id,cantidad,precio_unitario_estimado\n111,2,20.00\n222,1,30.00\n"
    resp = client.post(
        "/admin/comandas/resolver-csv",
        files={"file": ("import.csv", csv_text, "text/csv")},
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["errors"] == []
    assert len(body["lineas"]) == 2

    by_id = {l["release_id"]: l for l in body["lineas"]}
    assert by_id[str(r_existent.id)]["quantity"] == 2
    assert by_id[str(r_existent.id)]["estimated_unit_price"] == 20.0

    nou_release = db.scalar(select(Release).join(RecordProduct).where(RecordProduct.discogs_release_id == 222))
    assert nou_release is not None
    assert nou_release.artista == "Nou Artista"
    assert str(nou_release.id) in by_id


def test_resolver_csv_fila_invalida_es_reporta(db, client):
    admin = _admin_token(client, db)
    csv_text = "discogs_release_id,cantidad,precio_unitario_estimado\nabc,2,20.00\n"
    resp = client.post(
        "/admin/comandas/resolver-csv",
        files={"file": ("import.csv", csv_text, "text/csv")},
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["lineas"] == []
    assert len(body["errors"]) == 1


def test_resolver_csv_despres_es_pot_usar_per_crear_comanda(db, client, monkeypatch):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)

    def fake_get_release(token, discogs_release_id):
        return {
            "discogs_release_id": discogs_release_id, "artista": "X", "titulo": "Y",
            "sello": None, "anio": None, "genero": None, "estilos": None,
            "pais": None, "imagen_url": None, "tracklist": [], "credits": [],
        }
    monkeypatch.setattr(erp_module.comandas.discogs, "get_release", fake_get_release)

    csv_text = "discogs_release_id,cantidad,precio_unitario_estimado\n333,3,15.00\n"
    resolved = client.post(
        "/admin/comandas/resolver-csv",
        files={"file": ("import.csv", csv_text, "text/csv")},
        headers=_auth(admin),
    ).json()
    linea = resolved["lineas"][0]

    payload = {
        "proveedor_id": str(prov.id), "date": "2026-06-01T10:00:00",
        "lineas": [{"release_id": linea["release_id"], "quantity": linea["quantity"], "estimated_unit_price": linea["estimated_unit_price"]}],
    }
    resp = client.post("/admin/comandas", json=payload, headers=_auth(admin))
    assert resp.status_code == 201
    assert resp.json()["lineas"][0]["quantity"] == 3
