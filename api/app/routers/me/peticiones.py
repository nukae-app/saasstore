import uuid
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ...database import get_db
from ...models import (
    Address, Cart, CartItem, CondicionItem, EstadoPeticionCliente, Item, ItemStatus, Order,
    OrderItem, OrderStatus, PeticionCliente, Release, User,
)
from ...services.reservations import claim_peticion_item_for_cart
from ...services.security import get_current_user
from ..cart import get_or_create_cart
from .addresses import AddressIn

router = APIRouter(prefix="/me", tags=["me"])


class PeticionClienteIn(BaseModel):
    release_id: uuid.UUID | None = None
    free_artist: str | None = None
    free_title: str | None = None
    client_notes: str | None = None

    @model_validator(mode="after")
    def check_disco(self) -> "PeticionClienteIn":
        if not self.release_id and not (self.free_artist and self.free_title):
            raise ValueError("Cal indicar release_id, o bé artista i títol (disc fora de catàleg)")
        return self


class PeticionClienteOut(BaseModel):
    id: uuid.UUID
    release_id: uuid.UUID | None
    artista: str | None
    titulo: str | None
    imagen_url: str | None
    status: str
    estimated_price: Decimal | None
    chosen_delivery_method: str | None
    client_notes: str | None
    created_at: str
    order_id: uuid.UUID | None = None
    pagament_pendent: bool = False  # True si hi ha una Order creada en acceptar que encara no s'ha pagat


class AceptarPeticionIn(BaseModel):
    # envio i recollida_paga_ara es paguen ONLINE JA EN ACCEPTAR (com un
    # checkout normal, però encara sense exemplar físic assignat — es crea
    # una Order amb una línia "de reserva"); recollida_paga_botiga no paga
    # res ara, es reserva 72h quan arriba l'exemplar (Via 2).
    metodo_entrega: Literal["envio", "recollida_paga_ara", "recollida_paga_botiga"]
    address_id: uuid.UUID | None = None
    direccion_envio: AddressIn | None = None


def _peticion_out(peticion: PeticionCliente) -> PeticionClienteOut:
    if peticion.release:
        artista, titulo, imagen = peticion.release.artista, peticion.release.title, peticion.release.image_url
    else:
        artista, titulo, imagen = peticion.free_artist, peticion.free_title, None
    pagament_pendent = (
        peticion.status in (EstadoPeticionCliente.acceptada, EstadoPeticionCliente.en_tramit)
        and peticion.order is not None
        and peticion.order.status in (OrderStatus.pendiente_pago, OrderStatus.cancelado)
    )
    return PeticionClienteOut(
        id=peticion.id, release_id=peticion.release_id, artista=artista, titulo=titulo, imagen_url=imagen,
        status=peticion.status, estimated_price=peticion.estimated_price,
        chosen_delivery_method=peticion.chosen_delivery_method, client_notes=peticion.client_notes,
        created_at=peticion.created_at.isoformat(), order_id=peticion.order_id,
        pagament_pendent=pagament_pendent,
    )


def _address_snapshot(addr: Address) -> dict:
    return {
        "recipient_name": addr.recipient_name, "address_line1": addr.address_line1, "address_line2": addr.address_line2,
        "city": addr.city, "postal_code": addr.postal_code, "province": addr.province, "country": addr.country,
        "phone": addr.phone,
    }


def _resolver_direccion_envio(db: Session, user: User, payload: AceptarPeticionIn) -> dict:
    if payload.direccion_envio is not None:
        return payload.direccion_envio.model_dump()
    if payload.address_id is not None:
        addr = db.scalar(select(Address).where(Address.id == payload.address_id, Address.user_id == user.id))
        if addr is None:
            raise HTTPException(404, "Adreça no trobada")
        return _address_snapshot(addr)
    addr = db.scalar(select(Address).where(Address.user_id == user.id, Address.is_default.is_(True)))
    if addr is None:
        raise HTTPException(422, "Cal una adreça d'enviament: indica'n una o crea'n una de nova")
    return _address_snapshot(addr)


def _get_own_peticion_or_404(db: Session, peticion_id: uuid.UUID, user: User) -> PeticionCliente:
    peticion = db.scalar(
        select(PeticionCliente)
        .where(PeticionCliente.id == peticion_id, PeticionCliente.user_id == user.id)
        .options(selectinload(PeticionCliente.release), selectinload(PeticionCliente.order))
    )
    if peticion is None:
        raise HTTPException(404, "Petició no trobada")
    return peticion


@router.post("/peticiones", status_code=201, response_model=PeticionClienteOut)
def create_peticion(
    payload: PeticionClienteIn, user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    if payload.release_id:
        if db.get(Release, payload.release_id) is None:
            raise HTTPException(404, "Disc no trobat")
        stock = db.scalar(
            select(func.count()).select_from(Item)
            .where(
                Item.release_id == payload.release_id, Item.status == ItemStatus.disponible,
                Item.condition == CondicionItem.nou, Item.quantity > Item.reserved_quantity,
            )
        )
        if stock:
            raise HTTPException(409, "Aquest disc ja té estoc disponible: el pots comprar directament")

    peticion = PeticionCliente(
        user_id=user.id, release_id=payload.release_id,
        free_artist=payload.free_artist, free_title=payload.free_title,
        client_notes=payload.client_notes,
    )
    db.add(peticion)
    db.commit()
    return _peticion_out(_get_own_peticion_or_404(db, peticion.id, user))


@router.get("/peticiones", response_model=list[PeticionClienteOut])
def list_peticiones(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """No inclou les peticions ja resoltes en una compra real: un cop
    'recollida' sempre hi ha una Order (Via 1) o ja es va vendre a TPV
    (Via 2) — i tampoc la reserva Via 2 encara pendent de recollir. Totes
    aquestes es veuen a /me/orders, barrejades amb la resta de comandes
    (veure list_orders)."""
    peticiones = db.scalars(
        select(PeticionCliente)
        .where(
            PeticionCliente.user_id == user.id,
            PeticionCliente.status != EstadoPeticionCliente.recollida,
            ~(
                (PeticionCliente.chosen_delivery_method == "recollida_paga_botiga")
                & (PeticionCliente.status == EstadoPeticionCliente.reservada)
            ),
        )
        .options(selectinload(PeticionCliente.release), selectinload(PeticionCliente.order))
        .order_by(PeticionCliente.created_at.desc())
    ).all()
    return [_peticion_out(p) for p in peticiones]


@router.post("/peticiones/{peticion_id}/aceptar", response_model=PeticionClienteOut)
def aceptar_peticion(
    peticion_id: uuid.UUID, payload: AceptarPeticionIn,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """Envio / recollida_paga_ara: es paga JA AQUÍ, com un checkout normal
    (per això cal adreça si és enviament) — es crea l'Order en pendent de
    pagament amb una línia de reserva (encara sense exemplar físic); el
    front l'ha de portar de seguida a pagar amb Redsys (POST
    /checkout/{order_id}/pay/redsys/start, mateix endpoint que el checkout
    normal). Quan arribi l'exemplar, l'admin l'hi assigna i la comanda
    queda llesta per enviar/recollir (veure erp.py)."""
    peticion = _get_own_peticion_or_404(db, peticion_id, user)
    if peticion.status != EstadoPeticionCliente.pendent_acceptacio:
        raise HTTPException(409, "Aquesta petició no està esperant acceptació")

    direccion_envio = None
    if payload.metodo_entrega == "envio":
        direccion_envio = _resolver_direccion_envio(db, user, payload)

    peticion.status = EstadoPeticionCliente.acceptada
    peticion.chosen_delivery_method = payload.metodo_entrega

    if payload.metodo_entrega in ("envio", "recollida_paga_ara"):
        order = Order(
            user_id=user.id, contact_email=user.email, status=OrderStatus.pendiente_pago,
            total=peticion.estimated_price,
            shipping_method="envio" if payload.metodo_entrega == "envio" else "recogida_tienda",
            payment_method="redsys", shipping_address=direccion_envio,
            notes=f"Petició de client #{str(peticion.id)[:8]}",
        )
        db.add(order)
        db.flush()
        db.add(OrderItem(
            order_id=order.id, item_id=None, release_id=peticion.release_id, price=peticion.estimated_price,
        ))
        peticion.order_id = order.id

    db.commit()
    return _peticion_out(_get_own_peticion_or_404(db, peticion.id, user))


@router.post("/peticiones/{peticion_id}/reintentar-pagament")
def reintentar_pagament_peticion(
    peticion_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """Si el pagament fet en acceptar (envio/recollida_paga_ara) es va
    denegar, l'Order original queda 'cancelado' i cal una de nova per
    tornar-ho a intentar amb Redsys. Pot passar en qualsevol moment abans
    que arribi l'exemplar, tant si encara no s'ha creat la sol·licitud de
    compra (acceptada) com si ja s'està tramitant (en_tramit)."""
    peticion = _get_own_peticion_or_404(db, peticion_id, user)
    estats_amb_pagament_possible = (EstadoPeticionCliente.acceptada, EstadoPeticionCliente.en_tramit)
    if peticion.status not in estats_amb_pagament_possible or peticion.order_id is None:
        raise HTTPException(409, "Aquesta petició no té cap pagament pendent")

    order = db.get(Order, peticion.order_id)
    if order.status == OrderStatus.pendiente_pago:
        return {"order_id": str(order.id)}
    if order.status != OrderStatus.cancelado:
        raise HTTPException(409, f"Aquesta comanda ja no es pot pagar (estat: {order.status.value})")

    linia = db.scalar(select(OrderItem).where(OrderItem.order_id == order.id))
    nou = Order(
        user_id=user.id, contact_email=user.email, status=OrderStatus.pendiente_pago,
        total=order.total, shipping_method=order.shipping_method, payment_method="redsys",
        shipping_address=order.shipping_address, notes=order.notes,
    )
    db.add(nou)
    db.flush()
    db.add(OrderItem(order_id=nou.id, item_id=None, release_id=linia.release_id, price=linia.price))
    peticion.order_id = nou.id
    db.commit()
    return {"order_id": str(nou.id)}


@router.post("/peticiones/{peticion_id}/rechazar", response_model=PeticionClienteOut)
def rechazar_peticion(
    peticion_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    peticion = _get_own_peticion_or_404(db, peticion_id, user)
    if peticion.status != EstadoPeticionCliente.pendent_acceptacio:
        raise HTTPException(409, "Aquesta petició no està esperant acceptació")
    peticion.status = EstadoPeticionCliente.rebutjada
    db.commit()
    return _peticion_out(_get_own_peticion_or_404(db, peticion.id, user))


class PeticionNoEsAquestIn(BaseModel):
    comentari: str = Field(min_length=1)


@router.post("/peticiones/{peticion_id}/no-es-aquest", response_model=PeticionClienteOut)
def peticion_no_es_aquest(
    peticion_id: uuid.UUID, payload: PeticionNoEsAquestIn,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """Diferent de "Rebutja": el client encara vol el disc, però el que
    l'admin ha trobat no és el correcte. Torna la petició a 'pendent' (amb
    el comentari del client) perquè l'admin la corregeixi, en lloc de
    tancar-la definitivament."""
    peticion = _get_own_peticion_or_404(db, peticion_id, user)
    if peticion.status != EstadoPeticionCliente.pendent_acceptacio:
        raise HTTPException(409, "Aquesta petició no està esperant acceptació")
    nota = f"[El client indica que aquest disc no és el correcte]: {payload.comentari}"
    peticion.client_notes = f"{peticion.client_notes}\n\n{nota}" if peticion.client_notes else nota
    peticion.estimated_price = None
    peticion.status = EstadoPeticionCliente.pendent
    db.commit()
    return _peticion_out(_get_own_peticion_or_404(db, peticion.id, user))


@router.delete("/peticiones/{peticion_id}", status_code=204)
def cancelar_peticion(
    peticion_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    peticion = _get_own_peticion_or_404(db, peticion_id, user)
    if peticion.status not in (EstadoPeticionCliente.pendent, EstadoPeticionCliente.pendent_acceptacio):
        raise HTTPException(409, "Aquesta petició ja no es pot cancel·lar")
    peticion.status = EstadoPeticionCliente.cancelada
    db.commit()


@router.post("/peticiones/{peticion_id}/comprar")
def comprar_peticion(
    peticion_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    cart: Cart = Depends(get_or_create_cart),
):
    """Via 1 (envio o recollida pagant ara): l'exemplar ja reservat per a
    aquesta petició es transfereix al carret propi de l'usuari, perquè
    pugui seguir amb el checkout normal (/checkout/start + /confirm)."""
    peticion = _get_own_peticion_or_404(db, peticion_id, user)
    if peticion.status != EstadoPeticionCliente.reservada:
        raise HTTPException(409, "Aquesta petició encara no té cap exemplar disponible per comprar")
    if peticion.chosen_delivery_method not in ("envio", "recollida_paga_ara"):
        raise HTTPException(409, "Aquesta petició s'ha de recollir i pagar a botiga, no des d'aquí")
    if peticion.item_id is None:
        raise HTTPException(422, "Aquesta petició no té cap exemplar vinculat")

    if not claim_peticion_item_for_cart(db, peticion.item_id, peticion.id, cart.id):
        raise HTTPException(409, "L'exemplar ja no està reservat per a aquesta petició")

    exists = db.scalar(select(CartItem).where(CartItem.cart_id == cart.id, CartItem.item_id == peticion.item_id))
    if exists is None:
        db.add(CartItem(cart_id=cart.id, item_id=peticion.item_id))
        db.commit()

    return {"cart_id": str(cart.id), "item_id": str(peticion.item_id)}
