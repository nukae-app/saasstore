"""Tests del servicio de resolución del módulo de pricing (ofertas y cupones):
match de criterios, resolución de solapamientos por prioridad, idempotencia
del recompute, ajustes manuales, y validación de cupones."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models import (
    CanalVenta, CondicionItem, Coupon, DiscountType, Etiqueta, Item, MetodoPago, Offer, OfferItem,
    OfferItemMode, Order, OrderItem, OrderStatus, Release, VentaExterna,
)
from app.services.pricing import (
    CuponInvalido, compute_coupon_discount, detect_overlaps, match_items_by_criteria,
    preview_criteria, recompute_tenant_pricing, resolve_offer_items, validate_coupon,
)
from app.schemas.pricing import OfferCriteria

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _release(db, **kwargs) -> Release:
    r = Release(artista="Test Artist", title="Test Title", formato="LP", **kwargs)
    db.add(r)
    db.commit()
    return r


def _item(db, release, price="20.00", condition=CondicionItem.segona_ma, **kwargs) -> Item:
    item = Item(release_id=release.id, price=Decimal(price), condition=condition, **kwargs)
    db.add(item)
    db.commit()
    return item


def _offer(db, *, discount_type=DiscountType.percentage, discount_value="20", priority=0, criteria=None, active=True) -> Offer:
    offer = Offer(
        name="Test offer", discount_type=discount_type, discount_value=Decimal(discount_value),
        priority=priority, criteria=criteria or {}, active=active,
    )
    db.add(offer)
    db.commit()
    return offer


# ---------------------------------------------------------------------------
# match_items_by_criteria / resolve_offer_items
# ---------------------------------------------------------------------------


def test_match_por_precio_y_condicion(db):
    release = _release(db)
    barato_segona = _item(db, release, price="10.00", condition=CondicionItem.segona_ma)
    caro_segona = _item(db, release, price="50.00", condition=CondicionItem.segona_ma)
    _item(db, release, price="10.00", condition=CondicionItem.nou, quantity=3)

    criteria = OfferCriteria(precio_max=Decimal("15"), condicion="segona_ma")
    ids = set(db.scalars(match_items_by_criteria(criteria)))
    assert ids == {barato_segona.id}
    assert caro_segona.id not in ids


def test_match_excluye_stock_no_disponible(db):
    from app.models import ItemStatus
    release = _release(db)
    item = _item(db, release, price="10.00", status=ItemStatus.vendido)

    criteria = OfferCriteria(precio_max=Decimal("100"))
    ids = set(db.scalars(match_items_by_criteria(criteria)))
    assert item.id not in ids


def test_match_por_etiqueta(db):
    from app.models import ReleaseEtiqueta

    etiqueta = Etiqueta(slug="rebaixes", name_ca="Rebaixes")
    db.add(etiqueta)
    db.commit()

    con_etiqueta = _release(db)
    sin_etiqueta = _release(db)
    db.add(ReleaseEtiqueta(release_id=con_etiqueta.id, etiqueta_id=etiqueta.id))
    db.commit()
    item_con = _item(db, con_etiqueta)
    item_sin = _item(db, sin_etiqueta)

    criteria = OfferCriteria(etiqueta_id=etiqueta.id)
    ids = set(db.scalars(match_items_by_criteria(criteria)))
    assert ids == {item_con.id}
    assert item_sin.id not in ids


def test_match_antiguedad_minima(db):
    release = _release(db)
    viejo = _item(db, release, entry_date=datetime.now(timezone.utc) - timedelta(days=200))
    nuevo = _item(db, release, entry_date=datetime.now(timezone.utc) - timedelta(days=5))

    criteria = OfferCriteria(antiguedad_dias_min=180)
    ids = set(db.scalars(match_items_by_criteria(criteria)))
    assert ids == {viejo.id}
    assert nuevo.id not in ids


def test_match_sin_venta_reciente(db):
    release = _release(db)
    vendido_reciente = _item(db, release)
    nunca_vendido = _item(db, release)
    vendido_externo_reciente = _item(db, release)

    order = Order(
        status=OrderStatus.pagado, contact_email="x@example.com", total=Decimal("20.00"),
        shipping_method="recogida_tienda", paid_at=datetime.now(timezone.utc) - timedelta(days=2),
    )
    db.add(order)
    db.commit()
    db.add(OrderItem(order_id=order.id, item_id=vendido_reciente.id, price=Decimal("20.00")))
    db.add(VentaExterna(
        item_id=vendido_externo_reciente.id, channel=CanalVenta.mostrador, payment_method=MetodoPago.efectivo,
        sale_price=Decimal("20.00"), date=datetime.now(timezone.utc) - timedelta(days=1),
    ))
    db.commit()

    criteria = OfferCriteria(sin_venta_dias_min=30)
    ids = set(db.scalars(match_items_by_criteria(criteria)))
    assert ids == {nunca_vendido.id}
    assert vendido_reciente.id not in ids
    assert vendido_externo_reciente.id not in ids


def test_resolve_offer_items_include_y_exclude_manual(db):
    release = _release(db)
    matchea_criterio = _item(db, release, price="10.00")
    incluido_a_mano = _item(db, release, price="999.00")  # no matchearía por precio
    excluido_a_mano = _item(db, release, price="10.00")  # matchea criterio pero se excluye

    offer = _offer(db, criteria={"precio_max": "50"})
    db.add(OfferItem(offer_id=offer.id, item_id=incluido_a_mano.id, mode=OfferItemMode.include))
    db.add(OfferItem(offer_id=offer.id, item_id=excluido_a_mano.id, mode=OfferItemMode.exclude))
    db.commit()
    db.refresh(offer)

    result = resolve_offer_items(db, offer)
    assert result == {matchea_criterio.id, incluido_a_mano.id}


# ---------------------------------------------------------------------------
# recompute_tenant_pricing
# ---------------------------------------------------------------------------


def test_recompute_aplica_y_es_idempotente(db):
    release = _release(db)
    item = _item(db, release, price="20.00")
    offer = _offer(db, discount_type=DiscountType.percentage, discount_value="20", criteria={"precio_max": "100"})

    result = recompute_tenant_pricing(db)
    assert result.applied == 1
    assert result.reverted == 0

    db.refresh(item)
    assert item.list_price == Decimal("20.00")
    assert item.price == Decimal("16.00")
    assert item.active_offer_id == offer.id

    # Segunda llamada: no debe componer el descuento sobre el precio ya rebajado.
    result2 = recompute_tenant_pricing(db)
    assert result2.applied == 0
    db.refresh(item)
    assert item.price == Decimal("16.00")
    assert item.list_price == Decimal("20.00")


def test_recompute_revierte_al_desactivar_la_oferta(db):
    release = _release(db)
    item = _item(db, release, price="20.00")
    offer = _offer(db, criteria={"precio_max": "100"})
    recompute_tenant_pricing(db)
    db.refresh(item)
    assert item.price == Decimal("16.00")

    offer.active = False
    db.commit()
    result = recompute_tenant_pricing(db)
    assert result.reverted == 1

    db.refresh(item)
    assert item.price == Decimal("20.00")
    assert item.list_price is None
    assert item.active_offer_id is None


def test_recompute_resuelve_solapamiento_por_prioridad(db):
    release = _release(db)
    item = _item(db, release, price="100.00")
    baja_prioridad = _offer(
        db, discount_type=DiscountType.percentage, discount_value="10", priority=0,
        criteria={"precio_max": "1000"},
    )
    alta_prioridad = _offer(
        db, discount_type=DiscountType.percentage, discount_value="30", priority=5,
        criteria={"precio_max": "1000"},
    )

    result = recompute_tenant_pricing(db)
    assert result.applied == 1

    db.refresh(item)
    assert item.active_offer_id == alta_prioridad.id
    assert item.price == Decimal("70.00")  # 30% off, no la de baja prioridad


def test_recompute_fixed_price_nunca_deja_precio_negativo(db):
    release = _release(db)
    item = _item(db, release, price="5.00")
    _offer(db, discount_type=DiscountType.fixed_amount, discount_value="50", criteria={"precio_max": "1000"})

    recompute_tenant_pricing(db)
    db.refresh(item)
    assert item.price == Decimal("0.01")


# ---------------------------------------------------------------------------
# detect_overlaps / preview_criteria
# ---------------------------------------------------------------------------


def test_detect_overlaps_encuentra_ofertas_activas_que_comparten_items(db):
    release = _release(db)
    item = _item(db, release, price="20.00")
    existente = _offer(db, criteria={"precio_max": "100"})

    overlaps = detect_overlaps(db, OfferCriteria(precio_max=Decimal("100")))
    assert len(overlaps) == 1
    assert overlaps[0].offer.id == existente.id
    assert item.id in overlaps[0].overlapping_item_ids


def test_detect_overlaps_excluye_la_propia_oferta(db):
    release = _release(db)
    _item(db, release, price="20.00")
    offer = _offer(db, criteria={"precio_max": "100"})

    overlaps = detect_overlaps(db, OfferCriteria(precio_max=Decimal("100")), exclude_offer_id=offer.id)
    assert overlaps == []


def test_preview_criteria_cuenta_y_muestra(db):
    release = _release(db)
    for _ in range(3):
        _item(db, release, price="10.00")

    total, sample = preview_criteria(db, OfferCriteria(precio_max=Decimal("50")), sample_size=2)
    assert total == 3
    assert len(sample) == 2


# ---------------------------------------------------------------------------
# Cupones
# ---------------------------------------------------------------------------


def _coupon(db, **kwargs) -> Coupon:
    defaults = dict(code="PROMO10", discount_type=DiscountType.percentage, discount_value=Decimal("10"))
    defaults.update(kwargs)
    coupon = Coupon(**defaults)
    db.add(coupon)
    db.commit()
    return coupon


def test_validate_coupon_ok(db):
    coupon = _coupon(db)
    result = validate_coupon(db, "promo10", subtotal=Decimal("50"), user_id=None)
    assert result.id == coupon.id


def test_validate_coupon_no_encontrado(db):
    _coupon(db)  # asegura que la tabla tiene datos; el código pedido no coincide con ninguno
    try:
        validate_coupon(db, "NOEXISTE", subtotal=Decimal("50"), user_id=None)
        assert False, "debía lanzar CuponInvalido"
    except CuponInvalido as e:
        assert e.motivo == "no_encontrado"


def test_validate_coupon_caducado(db):
    coupon = _coupon(db, ends_at=datetime.now(timezone.utc) - timedelta(days=1))
    try:
        validate_coupon(db, coupon.code, subtotal=Decimal("50"), user_id=None)
        assert False, "debía lanzar CuponInvalido"
    except CuponInvalido as e:
        assert e.motivo == "caducado"


def test_validate_coupon_importe_minimo(db):
    coupon = _coupon(db, min_order_amount=Decimal("100"))
    try:
        validate_coupon(db, coupon.code, subtotal=Decimal("50"), user_id=None)
        assert False, "debía lanzar CuponInvalido"
    except CuponInvalido as e:
        assert e.motivo == "importe_minimo_no_alcanzado"


def test_validate_coupon_limite_de_usos(db):
    from app.models import CouponRedemption

    coupon = _coupon(db, max_uses=1)
    db.add(CouponRedemption(coupon_id=coupon.id, order_id=uuid.uuid4(), discount_amount=Decimal("5")))
    db.commit()
    try:
        validate_coupon(db, coupon.code, subtotal=Decimal("50"), user_id=None)
        assert False, "debía lanzar CuponInvalido"
    except CuponInvalido as e:
        assert e.motivo == "limite_de_usos_alcanzado"


def test_compute_coupon_discount_percentage_y_tope_al_subtotal(db):
    coupon = _coupon(db, discount_type=DiscountType.percentage, discount_value=Decimal("200"))
    # 200% se recorta a 100% al calcular, y nunca deja el descuento por encima del subtotal
    discount = compute_coupon_discount(coupon, Decimal("30.00"))
    assert discount == Decimal("30.00")


def test_compute_coupon_discount_fixed_amount(db):
    coupon = _coupon(db, discount_type=DiscountType.fixed_amount, discount_value=Decimal("5.00"))
    discount = compute_coupon_discount(coupon, Decimal("30.00"))
    assert discount == Decimal("5.00")
