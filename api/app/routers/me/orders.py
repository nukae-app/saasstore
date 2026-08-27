import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ...database import get_db
from ...models import EstadoPeticionCliente, Item, Order, OrderItem, PeticionCliente, Release, User
from ...services.security import get_current_user

router = APIRouter(prefix="/me", tags=["me"])


class OrderItemOut(BaseModel):
    artista: str | None
    titulo: str | None
    imagen_url: str | None
    precio: float
    pendent_arribada: bool = False  # línia de reserva (petició pagada, exemplar encara sense arribar)


class OrderDetailOut(BaseModel):
    id: uuid.UUID
    status: str
    total: float
    metodo_envio: str
    metodo_pago: str
    direccion_envio: dict | None
    notas: str | None
    created_at: str
    items: list[OrderItemOut]


class OrderSummaryOut(BaseModel):
    id: uuid.UUID
    tipo: Literal["comanda", "reserva_botiga", "venda_botiga"] = "comanda"
    status: str
    total: float
    metodo_envio: str | None = None
    metodo_pago: str | None = None
    created_at: str
    num_items: int
    # Només per a tipo='reserva_botiga' | 'venda_botiga' (peticions sense Order real).
    artista: str | None = None
    titulo: str | None = None
    imagen_url: str | None = None
    reserved_until: str | None = None


@router.get("/orders", response_model=list[OrderSummaryOut])
def list_orders(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Llista unificada de 'les meves comandes': comandes web reals + les
    peticions Via 2 (recollida i pagament a botiga) que ja tenen exemplar
    reservat o ja s'han recollit — així el client les segueix des d'un sol
    lloc, com si fossin una comanda més (reserva sense enviament, o ja
    tancada). Les peticions encara pendents d'acció (per exemple Via 1
    esperant que el client faci "Comprar ara") es queden a /me/peticiones."""
    orders = db.scalars(
        select(Order)
        .where(Order.user_id == user.id)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
    ).all()
    resultat = [
        OrderSummaryOut(
            id=o.id,
            tipo="comanda",
            status=o.status,
            total=float(o.total),
            metodo_envio=o.shipping_method,
            metodo_pago=o.payment_method,
            created_at=o.created_at.isoformat(),
            num_items=len(o.items),
        )
        for o in orders
    ]

    peticiones_botiga = db.scalars(
        select(PeticionCliente)
        .where(
            PeticionCliente.user_id == user.id,
            PeticionCliente.chosen_delivery_method == "recollida_paga_botiga",
            PeticionCliente.status.in_([EstadoPeticionCliente.reservada, EstadoPeticionCliente.recollida]),
        )
        .options(selectinload(PeticionCliente.release), selectinload(PeticionCliente.item))
    ).all()
    for p in peticiones_botiga:
        resultat.append(OrderSummaryOut(
            id=p.id,
            tipo="reserva_botiga" if p.status == EstadoPeticionCliente.reservada else "venda_botiga",
            status=p.status.value,
            total=float(p.estimated_price) if p.estimated_price is not None else 0.0,
            created_at=p.updated_at.isoformat(),
            num_items=1,
            artista=p.release.artista if p.release else p.free_artist,
            titulo=p.release.title if p.release else p.free_title,
            imagen_url=p.release.image_url if p.release else None,
            reserved_until=p.item.reserved_until.isoformat() if p.item and p.item.reserved_until else None,
        ))

    resultat.sort(key=lambda o: o.created_at, reverse=True)
    return resultat


@router.get("/orders/{order_id}", response_model=OrderDetailOut)
def get_order(
    order_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = db.scalar(
        select(Order)
        .where(Order.id == order_id, Order.user_id == user.id)
        .options(
            selectinload(Order.items).selectinload(OrderItem.item).selectinload(Item.release),
            selectinload(Order.items).selectinload(OrderItem.release),
        )
    )
    if order is None:
        raise HTTPException(404, "Comanda no trobada")

    items_out = []
    for oi in order.items:
        r: Release | None = oi.item.release if oi.item else oi.release
        items_out.append(OrderItemOut(
            artista=r.artista if r else None,
            titulo=r.title if r else None,
            imagen_url=r.image_url if r else None,
            precio=float(oi.price),
            pendent_arribada=oi.item_id is None,
        ))

    return OrderDetailOut(
        id=order.id,
        status=order.status,
        total=float(order.total),
        metodo_envio=order.shipping_method,
        metodo_pago=order.payment_method,
        direccion_envio=order.shipping_address,
        notas=order.notes,
        created_at=order.created_at.isoformat(),
        items=items_out,
    )
