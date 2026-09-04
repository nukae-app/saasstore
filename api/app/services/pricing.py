"""Motor de resolución del módulo de pricing (ofertas y cupones).

Piezas:
- `match_items_by_criteria` / `resolve_offer_items`: qué items cubre una
  oferta (dinámica por criterios + ajustes manuales de `OfferItem`).
- `preview_criteria` / `detect_overlaps`: para el panel de admin, antes de
  guardar una oferta — cuántos items matchean y con qué otras ofertas
  activas se solapa (el panel avisa, nunca resuelve el solapamiento solo,
  ver `Offer.priority`).
- `recompute_tenant_pricing`: el único punto que escribe `Item.price`. Se
  llama entero (todo el tenant), nunca oferta a oferta — ver su docstring.
- `validate_coupon` / `compute_coupon_discount` / `redeem_coupon`: cupones
  de checkout, independientes de las ofertas de catálogo.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..models import (
    CondicionItem, Coupon, CouponRedemption, DiscountType, Item, ItemStatus, Offer, OfferItem,
    OfferItemMode, Order, OrderItem, RecordProduct, Release, ReleaseEtiqueta, VentaExterna,
)
from ..schemas.pricing import OfferCriteria

# Una oferta nunca deja un item a precio 0 o negativo (sigue siendo un
# artículo real en venta, no un regalo).
PRECIO_MINIMO = Decimal("0.01")


class CuponInvalido(Exception):
    """`motivo` es un código corto pensado para traducir en el front (mismo
    espíritu que las excepciones de dominio de `services/enviament.py`)."""

    def __init__(self, motivo: str):
        self.motivo = motivo
        super().__init__(motivo)


@dataclass
class RecomputeResult:
    applied: int = 0
    reverted: int = 0


@dataclass
class OfferOverlap:
    offer: Offer
    overlapping_item_ids: set[uuid.UUID]


def _item_disponible_clause():
    """Mismo criterio que catalog.py: solo tiene sentido ofertar sobre stock
    realmente vendible ahora mismo."""
    return and_(
        Item.status == ItemStatus.disponible,
        or_(Item.condition != CondicionItem.nou, Item.quantity > Item.reserved_quantity),
    )


def match_items_by_criteria(criteria: OfferCriteria) -> Select:
    """SELECT de `Item.id` que cumplen los criterios dinámicos de una oferta,
    sobre stock disponible. No incluye los ajustes manuales (`OfferItem`) —
    ver `resolve_offer_items`."""
    now = datetime.now(timezone.utc)
    stmt = (
        select(Item.id)
        .join(Release, Release.id == Item.release_id)
        .outerjoin(RecordProduct, RecordProduct.release_id == Release.id)
        .where(_item_disponible_clause())
    )
    if criteria.condicion is not None:
        stmt = stmt.where(Item.condition == CondicionItem(criteria.condicion))
    if criteria.precio_min is not None:
        stmt = stmt.where(Item.price >= criteria.precio_min)
    if criteria.precio_max is not None:
        stmt = stmt.where(Item.price <= criteria.precio_max)
    if criteria.seccio_id is not None:
        stmt = stmt.where(Release.section_id == criteria.seccio_id)
    if criteria.etiqueta_id is not None:
        stmt = stmt.where(
            select(ReleaseEtiqueta.release_id)
            .where(
                ReleaseEtiqueta.release_id == Release.id,
                ReleaseEtiqueta.etiqueta_id == criteria.etiqueta_id,
            )
            .exists()
        )
    if criteria.antiguedad_dias_min is not None:
        cutoff = now - timedelta(days=criteria.antiguedad_dias_min)
        stmt = stmt.where(func.coalesce(Item.entry_date, Item.created_at) <= cutoff)
    if criteria.sin_venta_dias_min is not None:
        cutoff = now - timedelta(days=criteria.sin_venta_dias_min)
        vendido_recientemente = or_(
            select(OrderItem.id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(OrderItem.item_id == Item.id, Order.paid_at.isnot(None), Order.paid_at >= cutoff)
            .exists(),
            select(VentaExterna.id)
            .where(VentaExterna.item_id == Item.id, VentaExterna.date >= cutoff)
            .exists(),
        )
        stmt = stmt.where(~vendido_recientemente)
    # Campos propios del vertical "records" (viven en RecordProduct, outer
    # join a None para cualquier otro vertical — simplemente no coinciden
    # nunca, sin que el resolver necesite saber de verticales).
    if criteria.genero:
        stmt = stmt.where(RecordProduct.genero.ilike(f"%{criteria.genero}%"))
    if criteria.artista:
        stmt = stmt.where(RecordProduct.artista.ilike(f"%{criteria.artista}%"))
    if criteria.sello:
        stmt = stmt.where(RecordProduct.sello.ilike(f"%{criteria.sello}%"))
    if criteria.formato:
        stmt = stmt.where(RecordProduct.formato.ilike(f"%{criteria.formato}%"))
    return stmt


def resolve_offer_items(db: Session, offer: Offer) -> set[uuid.UUID]:
    """Conjunto final de items cubiertos por `offer`: match dinámico por
    `offer.criteria` con los ajustes manuales de `OfferItem` por encima —
    `exclude` siempre gana sobre `include` y sobre el match dinámico."""
    criteria = OfferCriteria.model_validate(offer.criteria or {})
    dynamic_ids = set(db.scalars(match_items_by_criteria(criteria)))
    includes = {oi.item_id for oi in offer.items if oi.mode == OfferItemMode.include}
    excludes = {oi.item_id for oi in offer.items if oi.mode == OfferItemMode.exclude}
    return (dynamic_ids | includes) - excludes


def preview_criteria(
    db: Session, criteria: OfferCriteria, *, sample_size: int = 20,
) -> tuple[int, list[Item]]:
    """Para el admin antes de guardar una oferta (o al editar sus
    criterios): cuenta cuántos items matchean y devuelve una muestra
    cargada (con `release`) para enseñarlos en el panel."""
    stmt = match_items_by_criteria(criteria)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    sample_ids = list(db.scalars(stmt.limit(sample_size)))
    if not sample_ids:
        return total, []
    items = list(db.scalars(
        select(Item).where(Item.id.in_(sample_ids)).options(selectinload(Item.release))
    ))
    return total, items


def detect_overlaps(
    db: Session,
    criteria: OfferCriteria,
    *,
    exclude_offer_id: uuid.UUID | None = None,
    manual_include: frozenset[uuid.UUID] = frozenset(),
    manual_exclude: frozenset[uuid.UUID] = frozenset(),
) -> list[OfferOverlap]:
    """Qué otras ofertas ACTIVAS ya cubren algún item que cubriría esta
    (nueva o en edición, `exclude_offer_id` para no compararla consigo
    misma). No decide nada: el panel enseña esto al admin, que ajusta
    `priority`/criterios/exclusiones a mano — nunca se resuelve solo."""
    candidate_ids = (set(db.scalars(match_items_by_criteria(criteria))) | manual_include) - manual_exclude
    if not candidate_ids:
        return []
    now = datetime.now(timezone.utc)
    stmt = select(Offer).where(
        Offer.active.is_(True),
        or_(Offer.starts_at.is_(None), Offer.starts_at <= now),
        or_(Offer.ends_at.is_(None), Offer.ends_at > now),
    )
    if exclude_offer_id is not None:
        stmt = stmt.where(Offer.id != exclude_offer_id)

    overlaps = []
    for other in db.scalars(stmt):
        shared = resolve_offer_items(db, other) & candidate_ids
        if shared:
            overlaps.append(OfferOverlap(offer=other, overlapping_item_ids=shared))
    return overlaps


def _discounted_price(base_price: Decimal, discount_type: DiscountType, discount_value: Decimal) -> Decimal:
    if discount_type == DiscountType.percentage:
        pct = max(Decimal("0"), min(discount_value, Decimal("100")))
        result = base_price * (Decimal("100") - pct) / Decimal("100")
    elif discount_type == DiscountType.fixed_amount:
        result = base_price - discount_value
    else:  # fixed_price
        result = discount_value
    result = result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return max(result, PRECIO_MINIMO)


def recompute_tenant_pricing(db: Session) -> RecomputeResult:
    """Recalcula `Item.price`/`list_price`/`active_offer_id` para TODO el
    tenant de la sesión actual (scoping implícito, ver `tenancy.py` — igual
    que `services/reservations.py`: nunca se pasa `tenant_id` a mano, se
    fija con `db.info["tenant_id"]`/`tenancy.scoped_to` antes de llamar) a
    partir de las ofertas activas ahora mismo. Se llama entero (no oferta a
    oferta) porque el ganador de cada item depende de TODAS las ofertas que
    coinciden a la vez (gana la de `priority` más alta, empate -> la creada
    más recientemente) — aplicar una sola en aislado no sabría si otra con
    más priority ya cubre ese item, ni detectaría los items que esta oferta
    ha dejado de cubrir y hay que revertir.

    Se llama tras crear/editar/activar/desactivar una `Offer`, y
    periódicamente por Celery (ver `tasks/pricing.py`, pendiente) porque
    criterios como `antiguedad_dias_min`/`sin_venta_dias_min` cambian solos
    cada día sin que nadie toque nada — en ese caso, quien llama itera los
    tenants y entra en `tenancy.scoped_to(db, tenant.id)` en cada vuelta,
    igual que `tasks/peticiones.py::release_expired_reservations`.

    Siempre recalcula `price` a partir de `list_price` (nunca del `price`
    actual): así es idempotente aunque se llame varias veces seguidas, sin
    componer descuentos. Mientras `active_offer_id` esté puesto, cualquier
    cambio manual de precio del admin debe hacerse sobre `list_price`, no
    sobre `price` directamente — si no, esta función lo pisaría en el
    siguiente recompute.
    """
    now = datetime.now(timezone.utc)
    active_offers = list(db.scalars(
        select(Offer)
        .where(
            Offer.active.is_(True),
            or_(Offer.starts_at.is_(None), Offer.starts_at <= now),
            or_(Offer.ends_at.is_(None), Offer.ends_at > now),
        )
        .order_by(Offer.priority.desc(), Offer.created_at.desc())
    ))

    winners: dict[uuid.UUID, Offer] = {}
    for offer in active_offers:  # ya ordenadas: la primera que llega a un item gana
        for item_id in resolve_offer_items(db, offer):
            winners.setdefault(item_id, offer)

    governed_items = {
        item.id: item
        for item in db.scalars(select(Item).where(Item.active_offer_id.isnot(None)))
    }
    missing_ids = set(winners) - set(governed_items)
    if missing_ids:
        for item in db.scalars(select(Item).where(Item.id.in_(missing_ids))):
            governed_items[item.id] = item

    result = RecomputeResult()
    for item_id, item in governed_items.items():
        winner = winners.get(item_id)
        if winner is None:
            if item.active_offer_id is not None:
                item.price = item.list_price if item.list_price is not None else item.price
                item.list_price = None
                item.active_offer_id = None
                result.reverted += 1
            continue

        base_price = item.list_price if item.list_price is not None else item.price
        new_price = _discounted_price(base_price, winner.discount_type, winner.discount_value)
        if item.active_offer_id != winner.id or item.price != new_price or item.list_price != base_price:
            item.list_price = base_price
            item.price = new_price
            item.active_offer_id = winner.id
            result.applied += 1

    db.commit()
    return result


# ---------------------------------------------------------------------------
# Cupones de checkout — independientes de las ofertas de catálogo.
# ---------------------------------------------------------------------------


def validate_coupon(
    db: Session, code: str, *, subtotal: Decimal, user_id: uuid.UUID | None,
) -> Coupon:
    """Comprueba que un cupón se puede aplicar AHORA a una comanda con este
    subtotal (tenant implícito de la sesión, ver `recompute_tenant_pricing`).
    No lo consume (ver `redeem_coupon`, que sí y hay que llamar dentro de la
    MISMA transacción que confirma el pedido, para no dejar una ventana de
    carrera entre validar y gastar `max_uses`)."""
    coupon = db.scalar(select(Coupon).where(Coupon.code == code.strip().upper()))
    if coupon is None or not coupon.active:
        raise CuponInvalido("no_encontrado")
    now = datetime.now(timezone.utc)
    if coupon.starts_at is not None and coupon.starts_at > now:
        raise CuponInvalido("todavia_no_activo")
    if coupon.ends_at is not None and coupon.ends_at <= now:
        raise CuponInvalido("caducado")
    if coupon.min_order_amount is not None and subtotal < coupon.min_order_amount:
        raise CuponInvalido("importe_minimo_no_alcanzado")
    if coupon.max_uses is not None:
        total_uses = db.scalar(
            select(func.count()).select_from(CouponRedemption).where(CouponRedemption.coupon_id == coupon.id)
        ) or 0
        if total_uses >= coupon.max_uses:
            raise CuponInvalido("limite_de_usos_alcanzado")
    if coupon.max_uses_per_user is not None and user_id is not None:
        user_uses = db.scalar(
            select(func.count()).select_from(CouponRedemption)
            .where(CouponRedemption.coupon_id == coupon.id, CouponRedemption.user_id == user_id)
        ) or 0
        if user_uses >= coupon.max_uses_per_user:
            raise CuponInvalido("limite_de_usos_alcanzado")
    return coupon


def compute_coupon_discount(coupon: Coupon, subtotal: Decimal) -> Decimal:
    if coupon.discount_type == DiscountType.percentage:
        pct = max(Decimal("0"), min(coupon.discount_value, Decimal("100")))
        discount = subtotal * pct / Decimal("100")
    else:  # fixed_amount (fixed_price no es válido para Coupon, ver CouponIn)
        discount = coupon.discount_value
    discount = discount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return min(discount, subtotal)  # nunca deja el total en negativo


def redeem_coupon(
    db: Session, coupon: Coupon, order_id: uuid.UUID, discount_amount: Decimal, user_id: uuid.UUID | None,
) -> CouponRedemption:
    """Consume un uso del cupón para esta comanda concreta. NO hace commit:
    hay que llamarlo dentro de la misma transacción que confirma el pedido
    (`/checkout/confirm`), después de volver a validar con `validate_coupon`
    para cerrar la ventana de carrera de `max_uses` — si se comitea aparte,
    un fallo posterior al crear el pedido dejaría un cupón gastado sin
    pedido completo detrás. (Una pequeña carrera de todos modos es
    tolerable aquí: peor caso, un cupón se gasta una vez de más en un pico
    de tráfico simultáneo, nunca vende dos veces el mismo artículo — a
    diferencia de la reserva de stock en `services/reservations.py`, que sí
    necesita el UPDATE atómico)."""
    redemption = CouponRedemption(
        coupon_id=coupon.id, order_id=order_id, user_id=user_id, discount_amount=discount_amount,
    )
    db.add(redemption)
    return redemption


def release_coupon_redemption(db: Session, order_id: uuid.UUID) -> bool:
    """Al cancelar un pedido (denegado por Redsys, o cancelado a mano desde
    el admin) borra su `CouponRedemption` si tenía uno, para que ese uso no
    siga contando contra `max_uses`/`max_uses_per_user` — mismo espíritu que
    `release_items`/`release_stock_hold` en `services/reservations.py`
    devolviendo el stock. `orders.coupon_code`/`coupon_discount` NO se
    tocan: siguen siendo el snapshot de lo que se intentó aplicar, igual que
    el resto de campos de un pedido cancelado."""
    redemption = db.scalar(select(CouponRedemption).where(CouponRedemption.order_id == order_id))
    if redemption is None:
        return False
    db.delete(redemption)
    db.commit()
    return True
