"""Tests del carrito/checkout para stock agregado (condicion='nou'): añadir
con cantidad, reserva vía StockHold en /checkout/start, OrderItem con
cantidad+condicion en /checkout/confirm, venta y cancelación."""

import contextlib
import io
import re
import uuid
from decimal import Decimal

from sqlalchemy import select

from app.models import CondicionItem, Item, Order, OrderItem, OrderStatus, Release, StockHold, User
from app.services.reservations import reserve_stock


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


def _seed_release_nou(db, cantidad=5, precio="20.00") -> tuple[Release, Item]:
    r = Release(artista="Artista", title="Àlbum", formato="LP")
    db.add(r)
    db.flush()
    item = Item(release_id=r.id, price=Decimal(precio), condition=CondicionItem.nou, quantity=cantidad)
    db.add(item)
    db.commit()
    return r, item


def test_afegir_al_carret_amb_cantidad(db, client):
    _, item = _seed_release_nou(db, cantidad=5)

    resp = client.post("/cart/items", json={"item_id": str(item.id), "quantity": 3})
    assert resp.status_code == 201
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["quantity"] == 3
    assert body["items"][0]["condition"] == "nou"
    assert Decimal(body["total"]) == Decimal("60.00")

    # añadir 2 más: se suma a la misma línea
    resp2 = client.post("/cart/items", json={"item_id": str(item.id), "quantity": 2})
    assert resp2.json()["items"][0]["quantity"] == 5


def test_afegir_al_carret_mes_cantidad_de_la_disponible_falla(db, client):
    _, item = _seed_release_nou(db, cantidad=2)
    resp = client.post("/cart/items", json={"item_id": str(item.id), "quantity": 3})
    assert resp.status_code == 409


def test_checkout_start_reserva_stockhold(db, client):
    _, item = _seed_release_nou(db, cantidad=5)
    client.post("/cart/items", json={"item_id": str(item.id), "quantity": 3})

    resp = client.post("/checkout/start")
    assert resp.status_code == 200

    db.expire_all()
    assert db.get(Item, item.id).reserved_quantity == 3
    hold = db.scalar(select(StockHold).where(StockHold.item_id == item.id))
    assert hold is not None
    assert hold.quantity == 3
    assert hold.cart_id is not None


def test_checkout_start_falla_si_no_hay_suficiente_y_no_reserva_nada(db, client):
    release, item1 = _seed_release_nou(db, cantidad=5)
    item2 = Item(release_id=release.id, price=Decimal("10.00"), condition=CondicionItem.nou, quantity=1)
    db.add(item2)
    db.commit()

    client.post("/cart/items", json={"item_id": str(item1.id), "quantity": 3})
    # reserva externa que deja item2 sin stock libre
    assert reserve_stock(db, item2.id, 1, cart_id=uuid.uuid4(), ttl_minutes=20) is not None
    client.post("/cart/items", json={"item_id": str(item2.id), "quantity": 1})

    resp = client.post("/checkout/start")
    assert resp.status_code == 409

    db.expire_all()
    assert db.get(Item, item1.id).reserved_quantity == 0  # revertido


def test_checkout_confirm_crea_orderitem_amb_cantidad_i_condicion(db, client):
    _, item = _seed_release_nou(db, cantidad=5, precio="20.00")
    client.post("/cart/items", json={"item_id": str(item.id), "quantity": 3})
    client.post("/checkout/start")

    resp = client.post(
        "/checkout/confirm",
        json={"contact_email": "client@example.com", "shipping_method": "recogida_tienda"},
    )
    assert resp.status_code == 201
    order_id = resp.json()["id"]

    db.expire_all()
    order_item = db.scalar(select(OrderItem).where(OrderItem.order_id == uuid.UUID(order_id)))
    assert order_item.quantity == 3
    assert order_item.condition == CondicionItem.nou
    assert order_item.price == Decimal("20.00")  # snapshot por unidad
    # el stock sigue reservado, no vendido, hasta que se pague de verdad
    assert db.get(Item, item.id).quantity == 5
    assert db.get(Item, item.id).reserved_quantity == 3


def test_pago_tienda_nou_vende_y_descuenta_cantidad(db, client):
    admin = _admin_token(client, db)
    _, item = _seed_release_nou(db, cantidad=5, precio="20.00")
    client.post("/cart/items", json={"item_id": str(item.id), "quantity": 3})
    client.post("/checkout/start")
    resp = client.post(
        "/checkout/confirm",
        json={"contact_email": "client@example.com", "shipping_method": "recogida_tienda", "payment_method": "tienda"},
    )
    order_id = resp.json()["id"]

    # el hold pasó de cart_id a order_id
    db.expire_all()
    hold = db.scalar(select(StockHold).where(StockHold.item_id == item.id))
    assert hold.order_id == uuid.UUID(order_id)
    assert hold.cart_id is None

    resp2 = client.patch(f"/admin/orders/{order_id}/status", json={"status": "pagado"}, headers=_auth(admin))
    assert resp2.status_code == 200

    db.expire_all()
    assert db.get(Item, item.id).quantity == 2
    assert db.get(Item, item.id).reserved_quantity == 0
    assert db.scalar(select(StockHold).where(StockHold.item_id == item.id)) is None


def test_cancelar_pedido_pagado_nou_repone_cantidad(db, client):
    admin = _admin_token(client, db)
    _, item = _seed_release_nou(db, cantidad=5, precio="20.00")
    client.post("/cart/items", json={"item_id": str(item.id), "quantity": 3})
    client.post("/checkout/start")
    resp = client.post(
        "/checkout/confirm",
        json={"contact_email": "client@example.com", "shipping_method": "recogida_tienda", "payment_method": "tienda"},
    )
    order_id = resp.json()["id"]
    client.patch(f"/admin/orders/{order_id}/status", json={"status": "pagado"}, headers=_auth(admin))

    db.expire_all()
    assert db.get(Item, item.id).quantity == 2

    resp2 = client.patch(f"/admin/orders/{order_id}/status", json={"status": "cancelado"}, headers=_auth(admin))
    assert resp2.status_code == 200

    db.expire_all()
    assert db.get(Item, item.id).quantity == 5  # repuesto
    assert db.get(Order, uuid.UUID(order_id)).status == OrderStatus.cancelado


def test_cancelar_pedido_pendiente_nou_libera_hold(db, client):
    admin = _admin_token(client, db)
    _, item = _seed_release_nou(db, cantidad=5, precio="20.00")
    client.post("/cart/items", json={"item_id": str(item.id), "quantity": 3})
    client.post("/checkout/start")
    resp = client.post(
        "/checkout/confirm",
        json={"contact_email": "client@example.com", "shipping_method": "recogida_tienda", "payment_method": "tienda"},
    )
    order_id = resp.json()["id"]

    resp2 = client.patch(f"/admin/orders/{order_id}/status", json={"status": "cancelado"}, headers=_auth(admin))
    assert resp2.status_code == 200

    db.expire_all()
    assert db.get(Item, item.id).quantity == 5
    assert db.get(Item, item.id).reserved_quantity == 0
    assert db.scalar(select(StockHold).where(StockHold.item_id == item.id)) is None
