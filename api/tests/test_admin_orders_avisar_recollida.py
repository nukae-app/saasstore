"""Tests del pas d'avisar el client que ja pot recollir una comanda a la
botiga (POST /admin/orders/{id}/avisar-recollida)."""

import contextlib
import io
import re
from decimal import Decimal

from sqlalchemy import select

from app.models import Order, OrderItem, OrderStatus, Release, User


def _login(client, email):
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


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _seed_order(db, status=OrderStatus.pagado, metodo_envio="recogida_tienda") -> Order:
    order = Order(
        contact_email="client@example.com", status=status, total=Decimal("20.00"),
        shipping_method=metodo_envio, payment_method="tienda",
    )
    db.add(order)
    db.commit()
    return order


def test_avisar_recollida_ok(db, client):
    admin_token = _admin_token(client, db)
    order = _seed_order(db)

    resp = client.post(f"/admin/orders/{order.id}/avisar-recollida", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert resp.json()["avisada_recollida_at"] is not None

    db.refresh(order)
    assert order.pickup_notified_at is not None


def test_avisar_recollida_falla_si_es_enviament(db, client):
    admin_token = _admin_token(client, db)
    order = _seed_order(db, metodo_envio="envio")

    resp = client.post(f"/admin/orders/{order.id}/avisar-recollida", headers=_auth(admin_token))
    assert resp.status_code == 422


def test_avisar_recollida_falla_si_no_pagada(db, client):
    admin_token = _admin_token(client, db)
    order = _seed_order(db, status=OrderStatus.pendiente_pago)

    resp = client.post(f"/admin/orders/{order.id}/avisar-recollida", headers=_auth(admin_token))
    assert resp.status_code == 409


def test_avisar_recollida_falla_si_pendent_arribada(db, client):
    admin_token = _admin_token(client, db)
    order = _seed_order(db)
    r = Release(artista="Artista", title="Àlbum", formato="LP")
    db.add(r)
    db.flush()
    db.add(OrderItem(order_id=order.id, item_id=None, release_id=r.id, price=Decimal("20.00")))
    db.commit()

    resp = client.post(f"/admin/orders/{order.id}/avisar-recollida", headers=_auth(admin_token))
    assert resp.status_code == 409
