import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import CondicionItem, Item, ItemStatus, OrderItem, Release
from ...schemas import ItemIn, ItemUpdate
from ...services.discogs_sync import push_item_to_discogs, remove_item_from_discogs, sync_stock_listing
from ...services.security import require_admin
from ...tenant_secrets import get_tenant_secrets

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.post("/items", status_code=201)
def create_item(payload: ItemIn, db: Session = Depends(get_db)):
    release = db.get(Release, payload.release_id)
    if release is None:
        raise HTTPException(404, "Release no encontrado")

    if payload.condition == CondicionItem.nou.value:
        # Stock agregado: si ya hay línea nou para este release, se suma en
        # vez de duplicar (mismo criterio que la recepción de comandas, ver
        # erp.py::recibir_comanda).
        agregado = db.scalar(
            select(Item).where(Item.release_id == payload.release_id, Item.condition == CondicionItem.nou)
        )
        if agregado is not None:
            coste_anterior = agregado.acquisition_cost or Decimal("0")
            coste_nuevo = payload.acquisition_cost if payload.acquisition_cost is not None else coste_anterior
            agregado.acquisition_cost = (
                agregado.quantity * coste_anterior + payload.quantity * coste_nuevo
            ) / (agregado.quantity + payload.quantity)
            agregado.quantity += payload.quantity
            agregado.price = payload.price
            sync_stock_listing(db, agregado, get_tenant_secrets(agregado.tenant_id).discogs_token)
            db.commit()
            db.refresh(agregado)
            return {"id": agregado.id, "codi_discogs": agregado.codi_discogs}

    item = Item(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)

    if item.condition == CondicionItem.nou:
        sync_stock_listing(db, item, get_tenant_secrets(item.tenant_id).discogs_token)
        db.commit()
    # Opció B: push automàtic a Discogs si el release té discogs_release_id (segona_ma)
    elif release.discogs_release_id and not item.codi_discogs:
        listing_id = push_item_to_discogs(
            get_tenant_secrets(item.tenant_id).discogs_token,
            item_id=item.id,
            release_discogs_id=release.discogs_release_id,
            precio=float(item.price),
            estado_disco=item.estado_disco,
            estado_funda=item.estado_funda,
        )
        if listing_id:
            item.codi_discogs = listing_id
            db.commit()

    return {"id": item.id, "codi_discogs": item.codi_discogs}


@router.put("/items/{item_id}")
def update_item(item_id: uuid.UUID, payload: ItemUpdate, db: Session = Depends(get_db)):
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "Ejemplar no encontrado")
    if item.status == ItemStatus.vendido:
        raise HTTPException(409, "No es pot editar: ja està venut (hi ha un pedido associat)")
    for field, value in payload.model_dump().items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return {"id": item.id}


@router.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: uuid.UUID, db: Session = Depends(get_db)):
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "Ejemplar no encontrado")
    if db.scalar(select(OrderItem.id).where(OrderItem.item_id == item_id).limit(1)):
        raise HTTPException(409, "No es pot eliminar: aquest exemplar té un pedido associat. Marca'l com a retirat en lloc d'eliminar-lo.")
    if item.codi_discogs:
        remove_item_from_discogs(get_tenant_secrets(item.tenant_id).discogs_token, item.codi_discogs)
    db.delete(item)
    db.commit()


@router.patch("/items/{item_id}/retirar")
def retire_item(item_id: uuid.UUID, db: Session = Depends(get_db)):
    """Vendido en tienda física o en Discogs: lo quitamos de la web."""
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "Ejemplar no encontrado")
    if item.status == ItemStatus.vendido:
        raise HTTPException(409, "Ya está vendido en la web (hay un pedido)")
    item.status = ItemStatus.retirado
    item.reserved_until = None
    item.reserved_by_cart_id = None
    db.commit()
    return {"status": item.status}
