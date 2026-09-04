"""Tests de los endpoints admin del módulo de pricing: ofertas (con preview,
solapamiento y recompute) y cupones."""

import contextlib
import io
import re
from decimal import Decimal

from sqlalchemy import select

from app.models import CondicionItem, Item, Release, User


def _admin_token(client, db) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert client.post("/auth/magic-link", json={"email": "admin@example.com"}).status_code == 202
    token = re.search(r"token=([\w\-]+)", buf.getvalue()).group(1)
    resp = client.post(f"/auth/magic-link/verify?token={token}")
    access = resp.json()["access_token"]
    user = db.scalar(select(User).where(User.email == "admin@example.com"))
    user.role = "admin"
    db.commit()
    return access


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _seed_item(db, price="20.00", condition=CondicionItem.segona_ma) -> Item:
    release = Release(artista="Artista", title="Àlbum", formato="LP")
    db.add(release)
    db.flush()
    item = Item(release_id=release.id, price=Decimal(price), condition=condition)
    db.add(item)
    db.commit()
    return item


# ---------------------------------------------------------------------------
# Ofertas
# ---------------------------------------------------------------------------


def test_create_offer_aplica_precio(db, client):
    admin = _admin_token(client, db)
    item = _seed_item(db, price="20.00")

    resp = client.post(
        "/admin/offers",
        json={
            "name": "Rebaixes", "discount_type": "percentage", "discount_value": "20",
            "criteria": {"precio_max": "100"},
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["active"] is True

    db.expire_all()
    updated = db.get(Item, item.id)
    assert updated.price == Decimal("16.00")
    assert updated.list_price == Decimal("20.00")
    assert str(updated.active_offer_id) == body["id"]


def test_preview_offer_devuelve_conteo_y_muestra(db, client):
    admin = _admin_token(client, db)
    _seed_item(db, price="10.00")
    _seed_item(db, price="10.00")
    _seed_item(db, price="999.00")

    resp = client.post("/admin/offers/preview", json={"precio_max": "50"}, headers=_auth(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_items"] == 2
    assert len(body["sample"]) == 2


def test_detect_overlaps_avisa_de_oferta_existente(db, client):
    admin = _admin_token(client, db)
    _seed_item(db, price="10.00")
    existing = client.post(
        "/admin/offers",
        json={"name": "Existente", "discount_type": "percentage", "discount_value": "10", "criteria": {"precio_max": "50"}},
        headers=_auth(admin),
    ).json()

    resp = client.post("/admin/offers/overlaps", json={"precio_max": "50"}, headers=_auth(admin))
    assert resp.status_code == 200
    overlaps = resp.json()
    assert len(overlaps) == 1
    assert overlaps[0]["offer_id"] == existing["id"]
    assert overlaps[0]["overlapping_items"] == 1


def test_update_offer_desactivar_revierte_precio(db, client):
    admin = _admin_token(client, db)
    item = _seed_item(db, price="20.00")
    offer = client.post(
        "/admin/offers",
        json={"name": "Rebaixes", "discount_type": "percentage", "discount_value": "20", "criteria": {"precio_max": "100"}},
        headers=_auth(admin),
    ).json()
    db.expire_all()
    assert db.get(Item, item.id).price == Decimal("16.00")

    resp = client.put(
        f"/admin/offers/{offer['id']}",
        json={
            "name": "Rebaixes", "discount_type": "percentage", "discount_value": "20",
            "criteria": {"precio_max": "100"}, "active": False,
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    assert resp.json()["active"] is False

    db.expire_all()
    updated = db.get(Item, item.id)
    assert updated.price == Decimal("20.00")
    assert updated.list_price is None
    assert updated.active_offer_id is None


def test_delete_offer_revierte_precio(db, client):
    admin = _admin_token(client, db)
    item = _seed_item(db, price="20.00")
    offer = client.post(
        "/admin/offers",
        json={"name": "Rebaixes", "discount_type": "percentage", "discount_value": "20", "criteria": {"precio_max": "100"}},
        headers=_auth(admin),
    ).json()

    resp = client.delete(f"/admin/offers/{offer['id']}", headers=_auth(admin))
    assert resp.status_code == 204

    db.expire_all()
    updated = db.get(Item, item.id)
    assert updated.price == Decimal("20.00")
    assert updated.active_offer_id is None


def test_offer_item_manual_include(db, client):
    admin = _admin_token(client, db)
    # No matchea por criterio (precio muy alto), se incluye a mano.
    item = _seed_item(db, price="999.00")
    offer = client.post(
        "/admin/offers",
        json={"name": "Especial", "discount_type": "fixed_amount", "discount_value": "50", "criteria": {"precio_max": "10"}},
        headers=_auth(admin),
    ).json()

    resp = client.post(
        f"/admin/offers/{offer['id']}/items", json={"item_id": str(item.id), "mode": "include"}, headers=_auth(admin),
    )
    assert resp.status_code == 201

    db.expire_all()
    updated = db.get(Item, item.id)
    assert updated.price == Decimal("949.00")

    resp2 = client.delete(f"/admin/offers/{offer['id']}/items/{item.id}", headers=_auth(admin))
    assert resp2.status_code == 204

    db.expire_all()
    reverted = db.get(Item, item.id)
    assert reverted.active_offer_id is None
    assert reverted.price == Decimal("999.00")


def test_offer_discount_porcentaje_mayor_a_100_falla(db, client):
    admin = _admin_token(client, db)
    resp = client.post(
        "/admin/offers",
        json={"name": "Imposible", "discount_type": "percentage", "discount_value": "150"},
        headers=_auth(admin),
    )
    assert resp.status_code == 422


def test_recompute_endpoint(db, client):
    admin = _admin_token(client, db)
    resp = client.post("/admin/offers/recompute", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json() == {"applied": 0, "reverted": 0}


# ---------------------------------------------------------------------------
# Cupones
# ---------------------------------------------------------------------------


def test_create_coupon(db, client):
    admin = _admin_token(client, db)
    resp = client.post(
        "/admin/coupons",
        json={"code": "promo10", "discount_type": "percentage", "discount_value": "10"},
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    assert resp.json()["code"] == "PROMO10"  # normalizado a mayúsculas


def test_create_coupon_codigo_duplicado_falla(db, client):
    admin = _admin_token(client, db)
    client.post(
        "/admin/coupons", json={"code": "PROMO10", "discount_type": "percentage", "discount_value": "10"},
        headers=_auth(admin),
    )
    resp = client.post(
        "/admin/coupons", json={"code": "promo10", "discount_type": "fixed_amount", "discount_value": "5"},
        headers=_auth(admin),
    )
    assert resp.status_code == 409


def test_coupon_fixed_price_no_valido(db, client):
    admin = _admin_token(client, db)
    resp = client.post(
        "/admin/coupons", json={"code": "X", "discount_type": "fixed_price", "discount_value": "5"},
        headers=_auth(admin),
    )
    assert resp.status_code == 422


def test_update_and_delete_coupon(db, client):
    admin = _admin_token(client, db)
    coupon = client.post(
        "/admin/coupons", json={"code": "PROMO10", "discount_type": "percentage", "discount_value": "10"},
        headers=_auth(admin),
    ).json()

    resp = client.put(
        f"/admin/coupons/{coupon['id']}",
        json={"code": "PROMO10", "discount_type": "percentage", "discount_value": "15", "active": False},
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    assert resp.json()["discount_value"] == "15.00"
    assert resp.json()["active"] is False

    resp2 = client.delete(f"/admin/coupons/{coupon['id']}", headers=_auth(admin))
    assert resp2.status_code == 204
    assert client.get("/admin/coupons", headers=_auth(admin)).json() == []


def test_coupon_restrict_to_offer_inexistente_falla(db, client):
    admin = _admin_token(client, db)
    resp = client.post(
        "/admin/coupons",
        json={
            "code": "SOLO-OFERTA", "discount_type": "percentage", "discount_value": "10",
            "restrict_to_offer_id": "00000000-0000-0000-0000-000000000000",
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 422


def test_coupon_redemptions_vacio_inicialmente(db, client):
    admin = _admin_token(client, db)
    coupon = client.post(
        "/admin/coupons", json={"code": "PROMO10", "discount_type": "percentage", "discount_value": "10"},
        headers=_auth(admin),
    ).json()
    resp = client.get(f"/admin/coupons/{coupon['id']}/redemptions", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json() == []
