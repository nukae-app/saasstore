"""Tests de les alertes d'estoc mínim (Bloc B4, veure docs/PLAN_PARIDAD_HOLDED.md)."""

import contextlib
import io
import re
from decimal import Decimal

from sqlalchemy import select

from app.models import CondicionItem, Item, ItemStatus, Release, User


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


def test_stock_alerts_nomes_inclou_nou_per_sota_del_llindar(db, client):
    admin = _admin_token(client, db)
    r1 = _seed_release(db, "Artista Baix", "Poc estoc")
    r2 = _seed_release(db, "Artista OK", "Estoc suficient")
    r3 = _seed_release(db, "Artista Sense Alarma", "Sense alarma configurada")

    db.add_all([
        # Per sota del llindar (2 disponibles, alerta a 3): ha de sortir.
        Item(release_id=r1.id, price=Decimal("20.00"), condition=CondicionItem.nou, quantity=2, min_stock_alert=3),
        # Per sobre del llindar: no ha de sortir.
        Item(release_id=r2.id, price=Decimal("20.00"), condition=CondicionItem.nou, quantity=10, min_stock_alert=3),
        # Sense alarma configurada: no ha de sortir encara que quedi poc estoc.
        Item(release_id=r3.id, price=Decimal("20.00"), condition=CondicionItem.nou, quantity=1, min_stock_alert=None),
    ])
    db.commit()

    resp = client.get("/admin/catalog/stock-alerts", headers=_auth(admin))
    assert resp.status_code == 200
    data = resp.json()

    assert data["total"] == 1
    assert data["items"][0]["titulo"] == "Poc estoc"
    assert data["items"][0]["disponible"] == 2
    assert data["items"][0]["alerta_stock_minimo"] == 3


def test_stock_alerts_descompta_reserves(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db)
    # 5 unitats, 4 reservades -> 1 disponible, per sota del llindar de 2.
    db.add(Item(
        release_id=r.id, price=Decimal("20.00"), condition=CondicionItem.nou,
        quantity=5, reserved_quantity=4, min_stock_alert=2,
    ))
    db.commit()

    resp = client.get("/admin/catalog/stock-alerts", headers=_auth(admin))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["disponible"] == 1


def test_stock_alerts_ignora_segona_ma_i_no_disponibles(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db)
    db.add_all([
        # segona_ma: min_stock_alert no té sentit, mai ha de sortir encara que es forci.
        Item(release_id=r.id, price=Decimal("20.00"), condition=CondicionItem.segona_ma, min_stock_alert=5),
        # nou però retirat: no ha de sortir.
        Item(
            release_id=r.id, price=Decimal("20.00"), condition=CondicionItem.nou,
            quantity=1, min_stock_alert=5, status=ItemStatus.retirado,
        ),
    ])
    db.commit()

    resp = client.get("/admin/catalog/stock-alerts", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_crear_item_nou_amb_alerta_estoc(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db)

    resp = client.post("/admin/items", json={
        "release_id": str(r.id), "price": "20.00", "condition": "nou",
        "quantity": 5, "min_stock_alert": 2,
    }, headers=_auth(admin))
    assert resp.status_code == 201

    item = db.scalar(select(Item).where(Item.release_id == r.id))
    assert item.min_stock_alert == 2
