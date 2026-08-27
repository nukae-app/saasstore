"""Tests de la flexibilitat admin sobre comandes web: moviment lliure entre
els estats logístics (pagat/enviat/entregat) i canvi de mètode d'entrega."""

import contextlib
import io
import re
import uuid
from decimal import Decimal

from sqlalchemy import select

from app.models import Item, Order, OrderStatus, Release, User


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
    r = Release(artista="Artista", title="Àlbum", formato="LP")
    db.add(r)
    db.flush()
    order = Order(
        contact_email="client@example.com", status=status, total=Decimal("20.00"),
        shipping_method=metodo_envio, payment_method="tienda",
    )
    db.add(order)
    db.commit()
    return order


def test_moviment_lliure_entre_estats_logistics(db, client):
    admin_token = _admin_token(client, db)
    order = _seed_order(db, status=OrderStatus.pagado, metodo_envio="envio")

    resp = client.patch(
        f"/admin/orders/{order.id}/status", json={"status": "entregado"}, headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "entregado"

    # Es pot tornar enrere: s'havia marcat entregat per error.
    resp = client.patch(
        f"/admin/orders/{order.id}/status", json={"status": "pagado"}, headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "pagado"


def test_no_es_pot_saltar_de_pendent_a_entregat(db, client):
    admin_token = _admin_token(client, db)
    order = _seed_order(db, status=OrderStatus.pendiente_pago)

    resp = client.patch(
        f"/admin/orders/{order.id}/status", json={"status": "entregado"}, headers=_auth(admin_token),
    )
    assert resp.status_code == 409


def test_cancelar_no_funciona_despres_entregat(db, client):
    admin_token = _admin_token(client, db)
    order = _seed_order(db, status=OrderStatus.entregado)

    resp = client.patch(
        f"/admin/orders/{order.id}/status", json={"status": "cancelado"}, headers=_auth(admin_token),
    )
    assert resp.status_code == 409


def test_cancelar_des_de_pagat_allibera_item(db, client):
    from app.models import ItemStatus, OrderItem

    admin_token = _admin_token(client, db)
    order = _seed_order(db, status=OrderStatus.pagado)
    release = db.scalar(select(Release))
    item = Item(release_id=release.id, price=Decimal("20.00"), status=ItemStatus.vendido)
    db.add(item)
    db.flush()
    db.add(OrderItem(order_id=order.id, item_id=item.id, price=Decimal("20.00")))
    db.commit()

    resp = client.patch(
        f"/admin/orders/{order.id}/status", json={"status": "cancelado"}, headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    db.expire_all()
    assert db.get(Item, item.id).status.value == "disponible"


def test_canviar_a_envio_sense_adreca_falla(db, client):
    admin_token = _admin_token(client, db)
    order = _seed_order(db, status=OrderStatus.pagado, metodo_envio="recogida_tienda")

    resp = client.patch(
        f"/admin/orders/{order.id}/status", json={"shipping_method": "envio"}, headers=_auth(admin_token),
    )
    assert resp.status_code == 422


def test_canviar_a_envio_amb_adreca_inline(db, client):
    admin_token = _admin_token(client, db)
    order = _seed_order(db, status=OrderStatus.pagado, metodo_envio="recogida_tienda")

    resp = client.patch(
        f"/admin/orders/{order.id}/status",
        json={
            "shipping_method": "envio",
            "shipping_address": {
                "recipient_name": "Client Test", "address_line1": "Carrer Fals 1",
                "postal_code": "08001", "city": "Barcelona", "country": "ES",
            },
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["metodo_envio"] == "envio"
    db.expire_all()
    assert db.get(Order, order.id).shipping_address["address_line1"] == "Carrer Fals 1"


def test_canviar_a_recollida_botiga(db, client):
    admin_token = _admin_token(client, db)
    order = _seed_order(db, status=OrderStatus.pagado, metodo_envio="envio")

    resp = client.patch(
        f"/admin/orders/{order.id}/status", json={"shipping_method": "recogida_tienda"}, headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["metodo_envio"] == "recogida_tienda"


def test_list_orders_filtra_per_text_lliure(db, client):
    admin_token = _admin_token(client, db)
    o1 = _seed_order(db)
    o1.contact_email = "maria@example.com"
    o2 = _seed_order(db)
    o2.contact_email = "joan@example.com"
    db.commit()

    resp = client.get("/admin/orders?q=maria", headers=_auth(admin_token))
    assert resp.status_code == 200
    ids = {o["id"] for o in resp.json()}
    assert ids == {str(o1.id)}


def test_list_orders_filtra_per_metodo_envio(db, client):
    admin_token = _admin_token(client, db)
    o1 = _seed_order(db, metodo_envio="envio")
    o2 = _seed_order(db, metodo_envio="recogida_tienda")

    resp = client.get("/admin/orders?metodo_envio=recogida_tienda", headers=_auth(admin_token))
    assert resp.status_code == 200
    ids = {o["id"] for o in resp.json()}
    assert ids == {str(o2.id)}


def test_list_orders_filtra_per_origen(db, client):
    admin_token = _admin_token(client, db)
    o1 = _seed_order(db)
    o2 = _seed_order(db)
    o2.origin = "discogs"
    o2.discogs_order_id = "D-123"
    db.commit()

    resp = client.get("/admin/orders?origen=discogs", headers=_auth(admin_token))
    assert resp.status_code == 200
    ids = {o["id"] for o in resp.json()}
    assert ids == {str(o2.id)}
