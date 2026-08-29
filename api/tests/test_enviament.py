"""Tests del cost d'enviament: trams de pes per país i càlcul al checkout."""

import contextlib
import io
import re
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Item, Order, PesFormat, Release, TramEnviament, User
from app.services.enviament import (
    DEFAULT_PES_G, PaisNoDisponible, PesNoConfigurat, compute_coste_enviament, paisos_disponibles,
    pes_total_g,
)


def _login(client, email: str) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert client.post("/auth/magic-link", json={"email": email}).status_code == 202
    token = re.search(r"token=([\w\-]+)", buf.getvalue()).group(1)
    resp = client.post(f"/auth/magic-link/verify?token={token}")
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _admin_token(client, db, email="admin@example.com") -> str:
    access = _login(client, email)
    user = db.scalar(select(User).where(User.email == email))
    user.role = "admin"
    db.commit()
    return access


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _seed_trams_es(db):
    db.add_all([
        TramEnviament(country="ES", max_weight_g=500, price=Decimal("3.50")),
        TramEnviament(country="ES", max_weight_g=1500, price=Decimal("5.50")),
        TramEnviament(country="ES", max_weight_g=3000, price=Decimal("8.00")),
    ])
    db.commit()


def _seed_release_item(db, pes_g=None, precio="20.00"):
    r = Release(artista="Los Ganglios", title="Peruguay", formato="LP", weight_g=pes_g)
    db.add(r)
    db.flush()
    item = Item(release_id=r.id, price=Decimal(precio))
    db.add(item)
    db.commit()
    return r, item


def _seed_release_item_sense_vertical_discos(db, pes_g=None, precio="20.00"):
    """Un release sense `formato` (mai s'assigna `RecordProduct`): equivalent
    a qualsevol altre vertical (floristeria, cafè...), a diferència de
    `_seed_release_item` que sempre és 'de discos' (formato='LP')."""
    r = Release(title="Ram de proves", weight_g=pes_g)
    db.add(r)
    db.flush()
    item = Item(release_id=r.id, price=Decimal(precio))
    db.add(item)
    db.commit()
    return r, item


# --- compute_coste_enviament ---

def test_recogida_tienda_es_sempre_gratis(db):
    _seed_trams_es(db)
    assert compute_coste_enviament(10_000, "recogida_tienda", None, db) == Decimal("0")


def test_tram_correcte_segons_pes(db):
    _seed_trams_es(db)
    assert compute_coste_enviament(300, "envio", "ES", db) == Decimal("3.50")
    assert compute_coste_enviament(500, "envio", "ES", db) == Decimal("3.50")  # límit inclusiu
    assert compute_coste_enviament(501, "envio", "ES", db) == Decimal("5.50")
    assert compute_coste_enviament(3000, "envio", "ES", db) == Decimal("8.00")


def test_pais_es_insensible_a_majuscules(db):
    _seed_trams_es(db)
    assert compute_coste_enviament(300, "envio", "es", db) == Decimal("3.50")


def test_pes_per_sobre_de_tots_els_trams_usa_el_mes_car(db):
    _seed_trams_es(db)
    assert compute_coste_enviament(10_000, "envio", "ES", db) == Decimal("8.00")


def test_tram_inactiu_no_es_fa_servir(db):
    db.add(TramEnviament(country="ES", max_weight_g=500, price=Decimal("3.50"), active=False))
    db.commit()
    with pytest.raises(PaisNoDisponible):
        compute_coste_enviament(300, "envio", "ES", db)


def test_cada_pais_usa_els_seus_propis_trams(db):
    _seed_trams_es(db)
    db.add_all([
        TramEnviament(country="FR", max_weight_g=500, price=Decimal("9.00")),
        TramEnviament(country="FR", max_weight_g=2000, price=Decimal("14.00")),
    ])
    db.commit()
    assert compute_coste_enviament(300, "envio", "FR", db) == Decimal("9.00")
    assert compute_coste_enviament(1000, "envio", "FR", db) == Decimal("14.00")
    # el tram d'ES no s'aplica a una comanda a FR
    assert compute_coste_enviament(300, "envio", "ES", db) == Decimal("3.50")


def test_pais_sense_cap_tram_es_rebutjat(db):
    _seed_trams_es(db)
    with pytest.raises(PaisNoDisponible):
        compute_coste_enviament(300, "envio", "US", db)
    with pytest.raises(PaisNoDisponible):
        compute_coste_enviament(300, "envio", None, db)


def test_sense_cap_tram_configurat_enlloc_es_rebutja(db):
    with pytest.raises(PaisNoDisponible):
        compute_coste_enviament(500, "envio", "ES", db)


def test_paisos_disponibles_reflecteix_els_trams_actius(db):
    assert paisos_disponibles(db) == []
    _seed_trams_es(db)
    db.add(TramEnviament(country="FR", max_weight_g=500, price=Decimal("9.00")))
    db.add(TramEnviament(country="IT", max_weight_g=500, price=Decimal("9.00"), active=False))
    db.commit()
    # IT no compta: el seu únic tram està inactiu
    assert paisos_disponibles(db) == ["ES", "FR"]


def test_pes_total_usa_default_global_quan_ni_release_ni_format_tenen_pes(db):
    _, item_amb_pes = _seed_release_item(db, pes_g=600)
    _, item_sense_pes = _seed_release_item(db, pes_g=None)
    db.refresh(item_amb_pes)
    db.refresh(item_sense_pes)
    assert pes_total_g([item_amb_pes, item_sense_pes], db) == 600 + DEFAULT_PES_G


def test_pes_total_usa_pes_per_format_quan_release_no_en_te(db):
    db.add(PesFormat(formato="LP", pes_g=180))
    db.commit()
    _, item = _seed_release_item(db, pes_g=None)  # formato="LP" per defecte a _seed_release_item
    db.refresh(item)
    assert pes_total_g([item], db) == 180


def test_pes_propi_del_release_té_prioritat_sobre_el_del_format(db):
    db.add(PesFormat(formato="LP", pes_g=180))
    db.commit()
    _, item = _seed_release_item(db, pes_g=500)
    db.refresh(item)
    assert pes_total_g([item], db) == 500


def test_pes_total_llança_pesnoconfigurat_per_a_vertical_sense_format_i_sense_pes(db):
    """§17 del pla Core/Vertical: un release que no és de discos (sense
    `formato`, com floristeria) mai ha de caure silenciosament al pes d'un
    vinil (`DEFAULT_PES_G`) — ha de rebutjar-se explícitament."""
    _, item = _seed_release_item_sense_vertical_discos(db, pes_g=None)
    db.refresh(item)
    with pytest.raises(PesNoConfigurat):
        pes_total_g([item], db)


def test_pes_total_respecta_pes_propi_encara_que_no_hi_hagi_format(db):
    _, item = _seed_release_item_sense_vertical_discos(db, pes_g=250)
    db.refresh(item)
    assert pes_total_g([item], db) == 250


# --- CRUD /admin/pes-format ---

def test_crud_pes_format(db, client):
    admin = _admin_token(client, db)

    resp = client.post("/admin/pes-format", json={"formato": "LP", "pes_g": 350}, headers=_auth(admin))
    assert resp.status_code == 201
    pes_id = resp.json()["id"]

    resp = client.get("/admin/pes-format", headers=_auth(admin))
    assert resp.status_code == 200
    assert any(p["id"] == pes_id and p["formato"] == "LP" for p in resp.json())

    resp = client.patch(f"/admin/pes-format/{pes_id}", json={"pes_g": 400}, headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json()["pes_g"] == 400

    resp = client.delete(f"/admin/pes-format/{pes_id}", headers=_auth(admin))
    assert resp.status_code == 204
    assert db.get(PesFormat, pes_id) is None


def test_no_es_pot_duplicar_format(db, client):
    admin = _admin_token(client, db)
    assert client.post("/admin/pes-format", json={"formato": "LP", "pes_g": 350}, headers=_auth(admin)).status_code == 201
    resp = client.post("/admin/pes-format", json={"formato": "LP", "pes_g": 400}, headers=_auth(admin))
    assert resp.status_code == 409


# --- CRUD /admin/trams-enviament ---

def test_crud_trams_enviament(db, client):
    admin = _admin_token(client, db)

    resp = client.post(
        "/admin/trams-enviament",
        json={"max_weight_g": 500, "price": "3.50", "country": "ES"},
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    tram_id = resp.json()["id"]
    assert resp.json()["country"] == "ES"

    resp = client.get("/admin/trams-enviament", headers=_auth(admin))
    assert resp.status_code == 200
    assert any(t["id"] == tram_id for t in resp.json())

    resp = client.patch(
        f"/admin/trams-enviament/{tram_id}", json={"price": "4.00"}, headers=_auth(admin)
    )
    assert resp.status_code == 200
    assert resp.json()["price"] == "4.00"

    resp = client.delete(f"/admin/trams-enviament/{tram_id}", headers=_auth(admin))
    assert resp.status_code == 204
    assert db.get(TramEnviament, tram_id) is None


def test_crear_tram_normalitza_pais_a_majuscules(db, client):
    admin = _admin_token(client, db)
    resp = client.post(
        "/admin/trams-enviament",
        json={"max_weight_g": 500, "price": "9.00", "country": "fr"},
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    assert resp.json()["country"] == "FR"


def test_crear_tram_sense_pais_es_rebutjat(db, client):
    admin = _admin_token(client, db)
    resp = client.post(
        "/admin/trams-enviament", json={"max_weight_g": 500, "price": "9.00"}, headers=_auth(admin)
    )
    assert resp.status_code == 422


def test_list_trams_enviament_nomes_actius(db, client):
    admin = _admin_token(client, db)
    actiu = client.post(
        "/admin/trams-enviament", json={"max_weight_g": 500, "price": "3.50", "country": "ES"}, headers=_auth(admin)
    ).json()
    client.post(
        "/admin/trams-enviament",
        json={"max_weight_g": 1000, "price": "5.00", "country": "ES", "active": False},
        headers=_auth(admin),
    )

    resp = client.get("/admin/trams-enviament", params={"nomes_actius": True}, headers=_auth(admin))
    assert resp.status_code == 200
    ids = [t["id"] for t in resp.json()]
    assert actiu["id"] in ids
    assert all(t["active"] for t in resp.json())


# --- integració amb el checkout ---

def test_paisos_enviament_public(db, client):
    _seed_trams_es(db)
    db.add(TramEnviament(country="FR", max_weight_g=500, price=Decimal("9.00")))
    db.commit()
    resp = client.get("/checkout/paisos-enviament")
    assert resp.status_code == 200
    assert resp.json()["paisos"] == ["ES", "FR"]


def test_coste_envio_preview_abans_de_confirmar(db, client):
    _seed_trams_es(db)
    _, item = _seed_release_item(db, pes_g=300)
    assert client.post("/cart/items", json={"item_id": str(item.id)}).status_code == 201

    resp = client.get("/checkout/coste-envio", params={"metodo_envio": "envio", "pais": "ES"})
    assert resp.status_code == 200
    assert resp.json()["coste_envio"] == "3.50"

    resp = client.get("/checkout/coste-envio", params={"metodo_envio": "recogida_tienda"})
    assert resp.json()["coste_envio"] == "0"


def test_coste_envio_preview_rebutja_producte_sense_pes_ni_vertical_discos(db, client):
    _seed_trams_es(db)
    _, item = _seed_release_item_sense_vertical_discos(db, pes_g=None)
    assert client.post("/cart/items", json={"item_id": str(item.id)}).status_code == 201

    resp = client.get("/checkout/coste-envio", params={"metodo_envio": "envio", "pais": "ES"})
    assert resp.status_code == 422


def test_coste_envio_preview_pais_no_disponible(db, client):
    _seed_trams_es(db)
    _, item = _seed_release_item(db, pes_g=300)
    assert client.post("/cart/items", json={"item_id": str(item.id)}).status_code == 201

    resp = client.get("/checkout/coste-envio", params={"metodo_envio": "envio", "pais": "US"})
    assert resp.status_code == 422


def test_confirm_amb_envio_suma_coste_envio_al_total(db, client):
    _seed_trams_es(db)
    _, item = _seed_release_item(db, pes_g=300, precio="20.00")
    assert client.post("/cart/items", json={"item_id": str(item.id)}).status_code == 201
    assert client.post("/checkout/start").status_code == 200

    conf = client.post(
        "/checkout/confirm",
        json={
            "contact_email": "client@example.com",
            "shipping_method": "envio",
            "shipping_address": {
                "recipient_name": "Client Test",
                "address_line1": "Carrer Fals 1",
                "city": "Barcelona",
                "postal_code": "08005",
            },
        },
    )
    assert conf.status_code == 201
    assert conf.json()["shipping_cost"] == "3.50"
    assert conf.json()["total"] == "23.50"
    db.expire_all()
    order = db.get(Order, uuid.UUID(conf.json()["id"]))
    assert order.shipping_cost == Decimal("3.50")
    assert order.total == Decimal("23.50")


def test_confirm_amb_recogida_tienda_no_cobra_enviament(db, client):
    _seed_trams_es(db)
    _, item = _seed_release_item(db, pes_g=300, precio="20.00")
    assert client.post("/cart/items", json={"item_id": str(item.id)}).status_code == 201
    assert client.post("/checkout/start").status_code == 200

    conf = client.post(
        "/checkout/confirm",
        json={"contact_email": "client@example.com", "shipping_method": "recogida_tienda"},
    )
    assert conf.status_code == 201
    assert conf.json()["shipping_cost"] == "0.00"
    assert conf.json()["total"] == "20.00"


def test_confirm_amb_envio_a_pais_amb_trams_permes(db, client):
    _seed_trams_es(db)
    db.add(TramEnviament(country="FR", max_weight_g=500, price=Decimal("9.00")))
    db.commit()
    _, item = _seed_release_item(db, pes_g=300, precio="20.00")
    assert client.post("/cart/items", json={"item_id": str(item.id)}).status_code == 201
    assert client.post("/checkout/start").status_code == 200

    conf = client.post(
        "/checkout/confirm",
        json={
            "contact_email": "client@example.com",
            "shipping_method": "envio",
            "shipping_address": {
                "recipient_name": "Client Test",
                "address_line1": "Rue Fictive 1",
                "city": "Paris",
                "postal_code": "75001",
                "country": "FR",
            },
        },
    )
    assert conf.status_code == 201
    assert conf.json()["shipping_cost"] == "9.00"


def test_confirm_rebutja_pais_sense_trams(db, client):
    _seed_trams_es(db)
    _, item = _seed_release_item(db, pes_g=300, precio="20.00")
    assert client.post("/cart/items", json={"item_id": str(item.id)}).status_code == 201
    assert client.post("/checkout/start").status_code == 200

    conf = client.post(
        "/checkout/confirm",
        json={
            "contact_email": "client@example.com",
            "shipping_method": "envio",
            "shipping_address": {
                "recipient_name": "Client Test",
                "address_line1": "Main St 1",
                "city": "New York",
                "postal_code": "10001",
                "country": "US",
            },
        },
    )
    assert conf.status_code == 422
