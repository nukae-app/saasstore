"""Panel admin del módulo de pricing: ofertas de catálogo (con preview y
detección de solapamiento antes de guardar) y cupones de checkout."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ...database import get_db
from ...models import Coupon, CouponRedemption, Item, Offer, OfferItem, OfferItemMode
from ...schemas import (
    CouponIn, CouponOut, CouponRedemptionOut, OfferApplyResultOut, OfferCriteria, OfferIn,
    OfferItemIn, OfferItemOut, OfferOut, OfferOverlapOut, OfferPreviewItem, OfferPreviewOut,
)
from ...services.pricing import detect_overlaps, preview_criteria, recompute_tenant_pricing
from ...services.security import require_admin

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


# ---------------------------------------------------------------------------
# Ofertas
# ---------------------------------------------------------------------------


@router.get("/offers", response_model=list[OfferOut])
def list_offers(db: Session = Depends(get_db)):
    return db.scalars(
        select(Offer).options(selectinload(Offer.items)).order_by(Offer.priority.desc(), Offer.created_at.desc())
    ).all()


@router.post("/offers/preview", response_model=OfferPreviewOut)
def preview_offer_criteria(criteria: OfferCriteria, db: Session = Depends(get_db)):
    """Antes de guardar (o al editar los criterios de) una oferta: cuántos
    items matchearían y una muestra para enseñar en el panel."""
    total, items = preview_criteria(db, criteria)
    return OfferPreviewOut(
        total_items=total,
        sample=[
            OfferPreviewItem(
                item_id=item.id, release_id=item.release_id, title=item.release.title,
                artista=item.release.artista, price=item.price, condition=item.condition.value,
            )
            for item in items
        ],
    )


class _OverlapCheckIn(OfferCriteria):
    exclude_offer_id: uuid.UUID | None = None


@router.post("/offers/overlaps", response_model=list[OfferOverlapOut])
def check_offer_overlaps(payload: _OverlapCheckIn, db: Session = Depends(get_db)):
    """Qué otras ofertas activas ya cubren algún item de estos criterios —
    el panel lo enseña como aviso; nunca se resuelve solo (ver
    services/pricing.py::detect_overlaps)."""
    criteria = OfferCriteria(**payload.model_dump(exclude={"exclude_offer_id"}))
    overlaps = detect_overlaps(db, criteria, exclude_offer_id=payload.exclude_offer_id)
    return [
        OfferOverlapOut(
            offer_id=o.offer.id, offer_name=o.offer.name, priority=o.offer.priority,
            overlapping_items=len(o.overlapping_item_ids),
        )
        for o in overlaps
    ]


@router.post("/offers", response_model=OfferOut, status_code=201)
def create_offer(payload: OfferIn, db: Session = Depends(get_db)):
    offer = Offer(
        name=payload.name, description=payload.description, discount_type=payload.discount_type,
        discount_value=payload.discount_value, starts_at=payload.starts_at, ends_at=payload.ends_at,
        active=payload.active, priority=payload.priority,
        criteria=payload.criteria.model_dump(mode="json", exclude_none=True) if payload.criteria else {},
    )
    db.add(offer)
    db.commit()
    recompute_tenant_pricing(db)
    db.refresh(offer)
    return offer


@router.put("/offers/{offer_id}", response_model=OfferOut)
def update_offer(offer_id: uuid.UUID, payload: OfferIn, db: Session = Depends(get_db)):
    offer = db.get(Offer, offer_id)
    if offer is None:
        raise HTTPException(404, "Oferta no encontrada")
    offer.name = payload.name
    offer.description = payload.description
    offer.discount_type = payload.discount_type
    offer.discount_value = payload.discount_value
    offer.starts_at = payload.starts_at
    offer.ends_at = payload.ends_at
    offer.active = payload.active
    offer.priority = payload.priority
    offer.criteria = payload.criteria.model_dump(mode="json", exclude_none=True) if payload.criteria else {}
    db.commit()
    recompute_tenant_pricing(db)
    db.refresh(offer)
    return offer


@router.delete("/offers/{offer_id}", status_code=204)
def delete_offer(offer_id: uuid.UUID, db: Session = Depends(get_db)):
    offer = db.get(Offer, offer_id)
    if offer is None:
        raise HTTPException(404, "Oferta no encontrada")
    # Revertir ANTES de borrar, no después: `Item.active_offer_id` tiene
    # ON DELETE SET NULL, así que en Postgres esa FK ya deja el campo a NULL
    # dentro del propio DELETE — si revirtiéramos con un recompute posterior
    # (que localiza los items afectados vía `active_offer_id == offer_id`),
    # el enlace ya se habría perdido y el precio rebajado se quedaría
    # huérfano para siempre. En SQLite (tests) no pasa porque no aplica FKs
    # por defecto, así que este orden importa solo en producción — no lo
    # cambies sin repetir la prueba contra Postgres de verdad.
    governed = list(db.scalars(select(Item).where(Item.active_offer_id == offer_id)))
    for item in governed:
        item.price = item.list_price if item.list_price is not None else item.price
        item.list_price = None
        item.active_offer_id = None
    db.delete(offer)
    db.commit()
    # Por si algún otro item ganaba esta oferta con menos prioridad que otra
    # aún activa: que la que tocaba ahora tome el relevo.
    recompute_tenant_pricing(db)


@router.post("/offers/{offer_id}/items", response_model=OfferItemOut, status_code=201)
def add_offer_item(offer_id: uuid.UUID, payload: OfferItemIn, db: Session = Depends(get_db)):
    """Ajuste manual (include/exclude) sobre el match dinámico de la
    oferta — ver Offer.criteria. Reemplaza el ajuste anterior sobre el mismo
    item si ya existía (cambiar de include a exclude, o viceversa)."""
    offer = db.get(Offer, offer_id)
    if offer is None:
        raise HTTPException(404, "Oferta no encontrada")
    existing = db.scalar(
        select(OfferItem).where(OfferItem.offer_id == offer_id, OfferItem.item_id == payload.item_id)
    )
    if existing is not None:
        existing.mode = OfferItemMode(payload.mode)
        offer_item = existing
    else:
        offer_item = OfferItem(offer_id=offer_id, item_id=payload.item_id, mode=OfferItemMode(payload.mode))
        db.add(offer_item)
    db.commit()
    recompute_tenant_pricing(db)
    db.refresh(offer_item)
    return offer_item


@router.delete("/offers/{offer_id}/items/{item_id}", status_code=204)
def remove_offer_item(offer_id: uuid.UUID, item_id: uuid.UUID, db: Session = Depends(get_db)):
    offer_item = db.scalar(
        select(OfferItem).where(OfferItem.offer_id == offer_id, OfferItem.item_id == item_id)
    )
    if offer_item is None:
        raise HTTPException(404, "Ajuste manual no encontrado")
    db.delete(offer_item)
    db.commit()
    recompute_tenant_pricing(db)


@router.post("/offers/recompute", response_model=OfferApplyResultOut)
def trigger_recompute(db: Session = Depends(get_db)):
    """Disparo manual del recompute (además de la tarea periódica de
    Celery) — útil justo después de tocar el catálogo (nuevas altas,
    cambios de sección/etiqueta) sin esperar al siguiente ciclo."""
    result = recompute_tenant_pricing(db)
    return OfferApplyResultOut(applied=result.applied, reverted=result.reverted)


# ---------------------------------------------------------------------------
# Cupones
# ---------------------------------------------------------------------------


@router.get("/coupons", response_model=list[CouponOut])
def list_coupons(db: Session = Depends(get_db)):
    return db.scalars(select(Coupon).order_by(Coupon.created_at.desc())).all()


def _validar_restrict_to_offer(db: Session, offer_id: uuid.UUID | None) -> None:
    if offer_id is not None and db.get(Offer, offer_id) is None:
        raise HTTPException(422, "La oferta indicada en restrict_to_offer_id no existe")


@router.post("/coupons", response_model=CouponOut, status_code=201)
def create_coupon(payload: CouponIn, db: Session = Depends(get_db)):
    code = payload.code.strip().upper()
    if db.scalar(select(Coupon).where(Coupon.code == code)):
        raise HTTPException(409, f"Ya existe un cupón con el código '{code}'")
    _validar_restrict_to_offer(db, payload.restrict_to_offer_id)
    data = payload.model_dump(exclude={"code"})
    coupon = Coupon(code=code, **data)
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return coupon


@router.put("/coupons/{coupon_id}", response_model=CouponOut)
def update_coupon(coupon_id: uuid.UUID, payload: CouponIn, db: Session = Depends(get_db)):
    coupon = db.get(Coupon, coupon_id)
    if coupon is None:
        raise HTTPException(404, "Cupón no encontrado")
    code = payload.code.strip().upper()
    conflict = db.scalar(select(Coupon).where(Coupon.code == code, Coupon.id != coupon_id))
    if conflict:
        raise HTTPException(409, f"Ya existe un cupón con el código '{code}'")
    _validar_restrict_to_offer(db, payload.restrict_to_offer_id)
    for field, value in payload.model_dump(exclude={"code"}).items():
        setattr(coupon, field, value)
    coupon.code = code
    db.commit()
    db.refresh(coupon)
    return coupon


@router.delete("/coupons/{coupon_id}", status_code=204)
def delete_coupon(coupon_id: uuid.UUID, db: Session = Depends(get_db)):
    coupon = db.get(Coupon, coupon_id)
    if coupon is None:
        raise HTTPException(404, "Cupón no encontrado")
    db.delete(coupon)
    db.commit()


@router.get("/coupons/{coupon_id}/redemptions", response_model=list[CouponRedemptionOut])
def list_coupon_redemptions(coupon_id: uuid.UUID, db: Session = Depends(get_db)):
    if db.get(Coupon, coupon_id) is None:
        raise HTTPException(404, "Cupón no encontrado")
    return db.scalars(
        select(CouponRedemption)
        .where(CouponRedemption.coupon_id == coupon_id)
        .order_by(CouponRedemption.created_at.desc())
    ).all()
