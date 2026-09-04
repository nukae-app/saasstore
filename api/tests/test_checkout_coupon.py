"""Tests de la integración de cupones en /checkout/confirm: aplicación,
snapshot en el pedido, consumo del cupón y liberación al cancelar."""

from decimal import Decimal

from sqlalchemy import select

from app.models import CondicionItem, Coupon, CouponRedemption, DiscountType, Item, Order, OrderStatus, Release


def _seed_item(db, price="20.00") -> Item:
    release = Release(artista="Artista", title="Àlbum", formato="LP")
    db.add(release)
    db.flush()
    item = Item(release_id=release.id, price=Decimal(price), condition=CondicionItem.segona_ma)
    db.add(item)
    db.commit()
    return item


def _coupon(db, **kwargs) -> Coupon:
    defaults = dict(code="PROMO10", discount_type=DiscountType.percentage, discount_value=Decimal("10"))
    defaults.update(kwargs)
    coupon = Coupon(**defaults)
    db.add(coupon)
    db.commit()
    return coupon


def test_validate_coupon_endpoint_preview(db, client):
    item = _seed_item(db, price="100.00")
    _coupon(db)
    client.post("/cart/items", json={"item_id": str(item.id)})

    resp = client.get("/checkout/validate-coupon?code=promo10")
    assert resp.status_code == 200
    body = resp.json()
    assert body["coupon_code"] == "PROMO10"
    assert Decimal(body["discount_amount"]) == Decimal("10.00")


def test_validate_coupon_endpoint_invalido(db, client):
    item = _seed_item(db, price="100.00")
    client.post("/cart/items", json={"item_id": str(item.id)})

    resp = client.get("/checkout/validate-coupon?code=NOEXISTE")
    assert resp.status_code == 422


def test_checkout_confirm_con_cupon_valido(db, client):
    item = _seed_item(db, price="100.00")
    _coupon(db)
    client.post("/cart/items", json={"item_id": str(item.id)})
    client.post("/checkout/start")

    resp = client.post(
        "/checkout/confirm",
        json={
            "contact_email": "client@example.com", "shipping_method": "recogida_tienda",
            "coupon_code": "promo10",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["coupon_code"] == "PROMO10"
    assert Decimal(body["coupon_discount"]) == Decimal("10.00")
    assert Decimal(body["total"]) == Decimal("90.00")

    db.expire_all()
    redemption = db.scalar(select(CouponRedemption))
    assert redemption is not None
    assert redemption.discount_amount == Decimal("10.00")


def test_checkout_confirm_con_cupon_invalido_falla(db, client):
    item = _seed_item(db, price="100.00")
    client.post("/cart/items", json={"item_id": str(item.id)})
    client.post("/checkout/start")

    resp = client.post(
        "/checkout/confirm",
        json={
            "contact_email": "client@example.com", "shipping_method": "recogida_tienda",
            "coupon_code": "NOEXISTE",
        },
    )
    assert resp.status_code == 422


def test_checkout_confirm_sin_cupon_no_afecta_total(db, client):
    item = _seed_item(db, price="100.00")
    client.post("/cart/items", json={"item_id": str(item.id)})
    client.post("/checkout/start")

    resp = client.post(
        "/checkout/confirm",
        json={"contact_email": "client@example.com", "shipping_method": "recogida_tienda"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["coupon_code"] is None
    assert Decimal(body["total"]) == Decimal("100.00")


def test_cancelar_pedido_libera_el_cupon(db, client):
    from tests.test_admin_pricing import _admin_token, _auth

    item = _seed_item(db, price="100.00")
    coupon = _coupon(db, max_uses=1)
    client.post("/cart/items", json={"item_id": str(item.id)})
    client.post("/checkout/start")
    resp = client.post(
        "/checkout/confirm",
        json={
            "contact_email": "client@example.com", "shipping_method": "recogida_tienda",
            "coupon_code": "PROMO10",
        },
    )
    order_id = resp.json()["id"]
    db.expire_all()
    assert db.scalar(select(CouponRedemption).where(CouponRedemption.coupon_id == coupon.id)) is not None

    admin = _admin_token(client, db)
    cancel_resp = client.patch(
        f"/admin/orders/{order_id}/status", json={"status": "cancelado"}, headers=_auth(admin),
    )
    assert cancel_resp.status_code == 200

    db.expire_all()
    assert db.scalar(select(CouponRedemption).where(CouponRedemption.coupon_id == coupon.id)) is None
