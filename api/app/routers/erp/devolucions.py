from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import (
    CajaMovimiento, CajaSession, CondicionItem, DevolucionCompra, DevolucionVenta, Item,
    ItemStatus, MetodoPago, Release, TipoMovimiento, VentaExterna,
)
from ...schemas import (
    DevolucionCompraIn, DevolucionCompraOut, DevolucionVentaIn, DevolucionVentaOut,
)
from ...services.discogs_sync import get_discogs_token_if_enabled, sync_stock_listing
from ...services.security import require_admin

router = APIRouter(prefix="/admin", tags=["erp"], dependencies=[Depends(require_admin)])


@router.post("/devolucions/venta", status_code=201, response_model=DevolucionVentaOut)
def create_devolucion_venta(payload: DevolucionVentaIn, db: Session = Depends(get_db)):
    item = db.get(Item, payload.item_id)
    if item is None:
        raise HTTPException(404, "Ejemplar no encontrado")

    dev = DevolucionVenta(
        order_item_id=payload.order_item_id,
        venta_externa_id=payload.venta_externa_id,
        item_id=payload.item_id,
        reason=payload.reason,
        item_destination=payload.item_destination,
        date=payload.date,
        notes=payload.notes,
        quantity=payload.quantity,
    )
    db.add(dev)

    if item.condition == CondicionItem.nou:
        # No hay status individual que restaurar: si vuelve a la venta, se
        # suman las unidades de vuelta a la línea agregada.
        if payload.item_destination == "disponible":
            item.quantity += payload.quantity
            sync_stock_listing(db, item, get_discogs_token_if_enabled(db, item.tenant_id))
    else:
        item.status = ItemStatus.disponible if payload.item_destination == "disponible" else ItemStatus.retirado
        item.reserved_until = None
        item.reserved_by_cart_id = None

    # Si la venda original era en efectiu, registrar la devolució com a sortida de caixa
    if payload.venta_externa_id:
        venta = db.get(VentaExterna, payload.venta_externa_id)
        if venta and venta.payment_method == MetodoPago.efectivo:
            sesion = db.scalar(
                select(CajaSession).where(CajaSession.closed_at.is_(None))
                .order_by(CajaSession.opened_at.desc())
            )
            if sesion:
                release = db.get(Release, item.release_id) if item.release_id else None
                concepto = (
                    f"Devolució: {release.artista} — {release.title}"
                    if release else "Devolució venda efectiu"
                )
                db.add(CajaMovimiento(
                    session_id=sesion.id,
                    type=TipoMovimiento.salida,
                    concept=concepto,
                    amount=venta.sale_price,
                    date=payload.date,
                ))

    db.commit()
    db.refresh(dev)
    return dev


@router.post("/devolucions/compra", status_code=201, response_model=DevolucionCompraOut)
def create_devolucion_compra(payload: DevolucionCompraIn, db: Session = Depends(get_db)):
    item = db.get(Item, payload.item_id)
    if item is None:
        raise HTTPException(404, "Ejemplar no encontrado")

    if item.condition == CondicionItem.nou:
        if item.quantity - item.reserved_quantity < payload.quantity:
            raise HTTPException(409, "No hi ha prou unitats lliures per tornar al proveïdor")
        item.quantity -= payload.quantity
        sync_stock_listing(db, item, get_discogs_token_if_enabled(db, item.tenant_id))
    else:
        if item.status != ItemStatus.disponible:
            raise HTTPException(409, f"El exemplar no està disponible (estat: {item.status})")
        item.status = ItemStatus.retirado

    dev = DevolucionCompra(
        item_id=payload.item_id,
        compra_id=payload.compra_id,
        reason=payload.reason,
        date=payload.date,
        notes=payload.notes,
        quantity=payload.quantity,
    )
    db.add(dev)
    db.commit()
    db.refresh(dev)
    return dev


@router.get("/devolucions/venta", response_model=list[DevolucionVentaOut])
def list_devolucions_venta(db: Session = Depends(get_db)):
    return db.scalars(select(DevolucionVenta).order_by(DevolucionVenta.date.desc())).all()


@router.get("/devolucions/compra", response_model=list[DevolucionCompraOut])
def list_devolucions_compra(db: Session = Depends(get_db)):
    return db.scalars(select(DevolucionCompra).order_by(DevolucionCompra.date.desc())).all()
