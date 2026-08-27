"""Tests de la sincronització de comandes del Marketplace de Discogs amb 'Vendes web'."""

import contextlib
import io
import re
from decimal import Decimal

from sqlalchemy import select

from app.models import CondicionItem, Item, ItemStatus, Order, OrderItem, OrderOrigen, OrderStatus, Release, User
from app.services import discogs_sync


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _seed_item(db, codi_discogs=None, precio="20.00") -> Item:
    release = Release(artista="Artista", title="Àlbum", formato="LP")
    db.add(release)
    db.commit()
    item = Item(release_id=release.id, price=Decimal(precio), codi_discogs=codi_discogs)
    db.add(item)
    db.commit()
    return item


def _fake_order(order_id="1-1", status="New Order", listing_id=None, buyer="discos_fan", total="20.00"):
    return {
        "id": order_id,
        "status": status,
        "buyer": {"username": buyer},
        "total": {"currency": "EUR", "value": float(total)},
        "items": [{"id": listing_id}] if listing_id else [],
        "shipping_address": "Carrer Fals 1, Barcelona",
    }


# ---------------------------------------------------------------------------
# sync_discogs_orders (pull)
# ---------------------------------------------------------------------------

def test_sync_crea_order_nova(db, monkeypatch):
    item = _seed_item(db, codi_discogs=999111)
    monkeypatch.setattr(discogs_sync, "fetch_open_discogs_orders", lambda token: [_fake_order(listing_id=999111)])

    resum = discogs_sync.sync_discogs_orders(db, "fake-token")
    assert resum["creats"] == 1

    order = db.scalar(select(Order).where(Order.discogs_order_id == "1-1"))
    assert order is not None
    assert order.origin == OrderOrigen.discogs
    assert order.status == OrderStatus.pendiente_pago
    assert order.contact_email == "discos_fan@discogs-buyer.local"

    db.refresh(item)
    assert item.status == ItemStatus.vendido

    oi = db.scalar(select(OrderItem).where(OrderItem.order_id == order.id))
    assert oi.item_id == item.id


def test_sync_idempotent_actualitza_estat(db, monkeypatch):
    item = _seed_item(db, codi_discogs=888222)
    monkeypatch.setattr(discogs_sync, "fetch_open_discogs_orders", lambda token: [_fake_order(listing_id=888222, status="New Order")])
    discogs_sync.sync_discogs_orders(db, "fake-token")

    monkeypatch.setattr(discogs_sync, "fetch_open_discogs_orders", lambda token: [_fake_order(listing_id=888222, status="Payment Received")])
    resum = discogs_sync.sync_discogs_orders(db, "fake-token")
    assert resum["actualitzats"] == 1
    assert resum["creats"] == 0

    order = db.scalar(select(Order).where(Order.discogs_order_id == "1-1"))
    assert order.status == OrderStatus.pagado


def test_sync_no_sobreescriu_estat_terminal_local(db, monkeypatch):
    item = _seed_item(db, codi_discogs=777333)
    monkeypatch.setattr(discogs_sync, "fetch_open_discogs_orders", lambda token: [_fake_order(listing_id=777333, status="New Order")])
    discogs_sync.sync_discogs_orders(db, "fake-token")

    order = db.scalar(select(Order).where(Order.discogs_order_id == "1-1"))
    order.status = OrderStatus.entregado  # decisió manual nostra
    db.commit()

    monkeypatch.setattr(discogs_sync, "fetch_open_discogs_orders", lambda token: [_fake_order(listing_id=777333, status="Shipped")])
    discogs_sync.sync_discogs_orders(db, "fake-token")

    db.refresh(order)
    assert order.status == OrderStatus.entregado  # no l'ha tocat


def test_sync_sense_match_no_crea_res(db, monkeypatch):
    monkeypatch.setattr(discogs_sync, "fetch_open_discogs_orders", lambda token: [_fake_order(listing_id=123456789)])
    resum = discogs_sync.sync_discogs_orders(db, "fake-token")
    assert resum["sense_match"] == 1
    assert db.scalar(select(Order)) is None


# ---------------------------------------------------------------------------
# Endpoint admin + push en marcar "enviado"
# ---------------------------------------------------------------------------

def test_endpoint_sync_orders(db, client, monkeypatch):
    admin = _admin_token(client, db)
    _seed_item(db, codi_discogs=555444)
    monkeypatch.setattr(discogs_sync, "fetch_open_discogs_orders", lambda token: [_fake_order(listing_id=555444)])

    resp = client.post("/admin/discogs/sync/orders", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json()["creats"] == 1


def test_marcar_enviado_fa_push_a_discogs(db, client, monkeypatch):
    admin = _admin_token(client, db)
    item = _seed_item(db, codi_discogs=333222)
    monkeypatch.setattr(discogs_sync, "fetch_open_discogs_orders", lambda token: [_fake_order(listing_id=333222)])
    discogs_sync.sync_discogs_orders(db, "fake-token")
    order = db.scalar(select(Order).where(Order.discogs_order_id == "1-1"))

    calls = []
    monkeypatch.setattr(discogs_sync, "push_shipped_status", lambda *a, **k: calls.append(a) or True)
    # admin.py importa la funció directament: cal pegar-la també allà
    import app.routers.admin as admin_module
    monkeypatch.setattr(admin_module.orders, "push_shipped_status", lambda *a, **k: calls.append(a) or True)

    resp = client.patch(
        f"/admin/orders/{order.id}/status",
        json={"status": "enviado", "tracking_number": "ABC123", "carrier": "Correos"},
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    assert len(calls) == 1
    # calls[0][0] es el token (primer arg posicional ahora), el discogs_order_id es el segundo
    assert calls[0][1] == "1-1"


# ---------------------------------------------------------------------------
# sync_stock_listing (nou: listing virtual de 1)
# ---------------------------------------------------------------------------

def _seed_item_nou(db, discogs_release_id=123, cantidad=5, codi_discogs=None) -> Item:
    release = Release(artista="Artista", title="Àlbum", formato="LP", discogs_release_id=discogs_release_id)
    db.add(release)
    db.commit()
    item = Item(
        release_id=release.id, price=Decimal("20.00"), condition=CondicionItem.nou,
        quantity=cantidad, codi_discogs=codi_discogs,
    )
    db.add(item)
    db.commit()
    return item


def test_sync_stock_listing_publica_si_hay_stock_y_no_hay_listing(db, monkeypatch):
    item = _seed_item_nou(db, cantidad=3, codi_discogs=None)
    monkeypatch.setattr(discogs_sync, "push_item_to_discogs", lambda token, **k: 424242)

    discogs_sync.sync_stock_listing(db, item, "fake-token")

    assert item.codi_discogs == 424242


def test_sync_stock_listing_no_duplica_si_ya_hay_listing(db, monkeypatch):
    item = _seed_item_nou(db, cantidad=3, codi_discogs=111)
    calls = []
    monkeypatch.setattr(discogs_sync, "push_item_to_discogs", lambda token, **k: calls.append(k) or 999)

    discogs_sync.sync_stock_listing(db, item, "fake-token")

    assert item.codi_discogs == 111  # no lo sustituye
    assert calls == []


def test_sync_stock_listing_retira_si_cantidad_llega_a_cero(db, monkeypatch):
    item = _seed_item_nou(db, cantidad=0, codi_discogs=555)
    removed = []
    monkeypatch.setattr(discogs_sync, "remove_item_from_discogs", lambda token, codi: removed.append(codi) or True)

    discogs_sync.sync_stock_listing(db, item, "fake-token")

    assert item.codi_discogs is None
    assert removed == [555]


def test_sync_discogs_orders_nou_descuenta_y_republica(db, monkeypatch):
    item = _seed_item_nou(db, cantidad=3, codi_discogs=777)
    monkeypatch.setattr(discogs_sync, "fetch_open_discogs_orders", lambda token: [_fake_order(listing_id=777)])
    monkeypatch.setattr(discogs_sync, "push_item_to_discogs", lambda token, **k: 888)

    resum = discogs_sync.sync_discogs_orders(db, "fake-token")
    assert resum["creats"] == 1

    db.refresh(item)
    assert item.quantity == 2  # se vendió 1 unidad, no la línea entera
    assert item.codi_discogs == 888  # listing viejo consumido, uno nuevo publicado

    oi = db.scalar(select(OrderItem).where(OrderItem.item_id == item.id))
    assert oi.quantity == 1
    assert oi.condition == CondicionItem.nou


def test_sync_discogs_orders_nou_agota_stock_no_republica(db, monkeypatch):
    item = _seed_item_nou(db, cantidad=1, codi_discogs=666)
    monkeypatch.setattr(discogs_sync, "fetch_open_discogs_orders", lambda token: [_fake_order(listing_id=666)])
    calls = []
    monkeypatch.setattr(discogs_sync, "push_item_to_discogs", lambda token, **k: calls.append(k) or 999)

    discogs_sync.sync_discogs_orders(db, "fake-token")

    db.refresh(item)
    assert item.quantity == 0
    assert item.codi_discogs is None
    assert calls == []  # no queda stock: no se publica nada nuevo


def test_marcar_enviado_web_no_fa_push(db, client, monkeypatch):
    """Una comanda web normal (origen='web') no té discogs_order_id: no s'ha de cridar Discogs."""
    admin = _admin_token(client, db)
    item = _seed_item(db)
    order = Order(
        contact_email="client@example.com",
        status=OrderStatus.pagado,
        total=item.price,
        shipping_method="recogida_tienda",
    )
    db.add(order)
    db.commit()
    db.add(OrderItem(order_id=order.id, item_id=item.id, price=item.price))
    db.commit()

    calls = []
    import app.routers.admin as admin_module
    monkeypatch.setattr(admin_module.orders, "push_shipped_status", lambda *a, **k: calls.append(a) or True)

    resp = client.patch(
        f"/admin/orders/{order.id}/status",
        json={"status": "enviado"},
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    assert calls == []
