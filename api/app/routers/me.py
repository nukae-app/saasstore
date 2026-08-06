"""Endpoints per a l'usuari autenticat (perfil propi + comandes)."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import (
    Address, Assignacio, Cart, CartItem, CondicionItem, EstadoPeticionCliente, EstatAssignacio,
    EstatSubscripcio, Item, ItemStatus, Order, OrderItem, OrderStatus, PeticionCliente, Release,
    Subscripcio, User,
)
from ..schemas import AddressIn, SubscripcioMeOut, SubscripcioMePatch
from ..services.reservations import claim_peticion_item_for_cart
from ..services.security import get_current_user
from .cart import get_or_create_cart

router = APIRouter(prefix="/me", tags=["me"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ProfilePatch(BaseModel):
    nombre: str | None = None
    telefon: str | None = None
    idioma: str | None = None
    consent_newsletter: bool | None = None


class MeFullOut(BaseModel):
    id: uuid.UUID
    email: str
    nombre: str | None
    telefon: str | None
    rol: str
    idioma: str
    consent_newsletter: bool
    activo: bool

    model_config = {"from_attributes": True}


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


class AddressIn(BaseModel):
    nombre_destinatario: str
    linea1: str
    linea2: str | None = None
    ciudad: str
    cp: str
    provincia: str | None = None
    pais: str = "ES"
    telefono: str | None = None
    predeterminada: bool = False


class AddressOut(BaseModel):
    id: uuid.UUID
    nombre_destinatario: str
    linea1: str
    linea2: str | None
    ciudad: str
    cp: str
    provincia: str | None
    pais: str
    telefono: str | None
    predeterminada: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/profile", response_model=MeFullOut)
def get_profile(user: User = Depends(get_current_user)):
    return user


@router.patch("/profile", response_model=MeFullOut)
def update_profile(
    payload: ProfilePatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, val)
    db.commit()
    db.refresh(user)
    return user


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
            metodo_envio=o.metodo_envio,
            metodo_pago=o.metodo_pago,
            created_at=o.created_at.isoformat(),
            num_items=len(o.items),
        )
        for o in orders
    ]

    peticiones_botiga = db.scalars(
        select(PeticionCliente)
        .where(
            PeticionCliente.user_id == user.id,
            PeticionCliente.metodo_entrega_triat == "recollida_paga_botiga",
            PeticionCliente.estado.in_([EstadoPeticionCliente.reservada, EstadoPeticionCliente.recollida]),
        )
        .options(selectinload(PeticionCliente.release), selectinload(PeticionCliente.item))
    ).all()
    for p in peticiones_botiga:
        resultat.append(OrderSummaryOut(
            id=p.id,
            tipo="reserva_botiga" if p.estado == EstadoPeticionCliente.reservada else "venda_botiga",
            status=p.estado.value,
            total=float(p.precio_estimado) if p.precio_estimado is not None else 0.0,
            created_at=p.updated_at.isoformat(),
            num_items=1,
            artista=p.release.artista if p.release else p.artista_lliure,
            titulo=p.release.titulo if p.release else p.titulo_lliure,
            imagen_url=p.release.imagen_url if p.release else None,
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
            titulo=r.titulo if r else None,
            imagen_url=r.imagen_url if r else None,
            precio=float(oi.precio),
            pendent_arribada=oi.item_id is None,
        ))

    return OrderDetailOut(
        id=order.id,
        status=order.status,
        total=float(order.total),
        metodo_envio=order.metodo_envio,
        metodo_pago=order.metodo_pago,
        direccion_envio=order.direccion_envio,
        notas=order.notas,
        created_at=order.created_at.isoformat(),
        items=items_out,
    )


# ---------------------------------------------------------------------------
# Adreces
# ---------------------------------------------------------------------------

@router.get("/addresses", response_model=list[AddressOut])
def list_addresses(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(Address)
        .where(Address.user_id == user.id)
        .order_by(Address.predeterminada.desc(), Address.id)
    ).all()


@router.post("/addresses", response_model=AddressOut, status_code=201)
def create_address(
    payload: AddressIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.predeterminada:
        db.execute(
            Address.__table__.update()
            .where(Address.user_id == user.id)
            .values(predeterminada=False)
        )
    addr = Address(user_id=user.id, **payload.model_dump())
    db.add(addr)
    db.commit()
    db.refresh(addr)
    return addr


@router.put("/addresses/{addr_id}", response_model=AddressOut)
def update_address(
    addr_id: uuid.UUID,
    payload: AddressIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    addr = db.scalar(select(Address).where(Address.id == addr_id, Address.user_id == user.id))
    if addr is None:
        raise HTTPException(404, "Adreça no trobada")
    if payload.predeterminada and not addr.predeterminada:
        db.execute(
            Address.__table__.update()
            .where(Address.user_id == user.id)
            .values(predeterminada=False)
        )
    for field, val in payload.model_dump().items():
        setattr(addr, field, val)
    db.commit()
    db.refresh(addr)
    return addr


@router.delete("/addresses/{addr_id}", status_code=204)
def delete_address(
    addr_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    addr = db.scalar(select(Address).where(Address.id == addr_id, Address.user_id == user.id))
    if addr is None:
        raise HTTPException(404, "Adreça no trobada")
    db.delete(addr)
    db.commit()


@router.post("/addresses/{addr_id}/set-default", response_model=AddressOut)
def set_default_address(
    addr_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.execute(
        Address.__table__.update()
        .where(Address.user_id == user.id)
        .values(predeterminada=False)
    )
    addr = db.scalar(select(Address).where(Address.id == addr_id, Address.user_id == user.id))
    if addr is None:
        raise HTTPException(404, "Adreça no trobada")
    addr.predeterminada = True
    db.commit()
    db.refresh(addr)
    return addr


# ---------------------------------------------------------------------------
# Peticions de disc sense estoc ("avisa'm quan torni" / "no el trobo, el vull")
# ---------------------------------------------------------------------------

class PeticionClienteIn(BaseModel):
    release_id: uuid.UUID | None = None
    artista_lliure: str | None = None
    titulo_lliure: str | None = None
    notas_cliente: str | None = None

    @model_validator(mode="after")
    def check_disco(self) -> "PeticionClienteIn":
        if not self.release_id and not (self.artista_lliure and self.titulo_lliure):
            raise ValueError("Cal indicar release_id, o bé artista i títol (disc fora de catàleg)")
        return self


class PeticionClienteOut(BaseModel):
    id: uuid.UUID
    release_id: uuid.UUID | None
    artista: str | None
    titulo: str | None
    imagen_url: str | None
    estado: str
    precio_estimado: Decimal | None
    metodo_entrega_triat: str | None
    notas_cliente: str | None
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
        artista, titulo, imagen = peticion.release.artista, peticion.release.titulo, peticion.release.imagen_url
    else:
        artista, titulo, imagen = peticion.artista_lliure, peticion.titulo_lliure, None
    pagament_pendent = (
        peticion.estado in (EstadoPeticionCliente.acceptada, EstadoPeticionCliente.en_tramit)
        and peticion.order is not None
        and peticion.order.status in (OrderStatus.pendiente_pago, OrderStatus.cancelado)
    )
    return PeticionClienteOut(
        id=peticion.id, release_id=peticion.release_id, artista=artista, titulo=titulo, imagen_url=imagen,
        estado=peticion.estado, precio_estimado=peticion.precio_estimado,
        metodo_entrega_triat=peticion.metodo_entrega_triat, notas_cliente=peticion.notas_cliente,
        created_at=peticion.created_at.isoformat(), order_id=peticion.order_id,
        pagament_pendent=pagament_pendent,
    )


def _address_snapshot(addr: Address) -> dict:
    return {
        "nombre_destinatario": addr.nombre_destinatario, "linea1": addr.linea1, "linea2": addr.linea2,
        "ciudad": addr.ciudad, "cp": addr.cp, "provincia": addr.provincia, "pais": addr.pais,
        "telefono": addr.telefono,
    }


def _resolver_direccion_envio(db: Session, user: User, payload: AceptarPeticionIn) -> dict:
    if payload.direccion_envio is not None:
        return payload.direccion_envio.model_dump()
    if payload.address_id is not None:
        addr = db.scalar(select(Address).where(Address.id == payload.address_id, Address.user_id == user.id))
        if addr is None:
            raise HTTPException(404, "Adreça no trobada")
        return _address_snapshot(addr)
    addr = db.scalar(select(Address).where(Address.user_id == user.id, Address.predeterminada.is_(True)))
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
                Item.condicion == CondicionItem.nou, Item.cantidad > Item.cantidad_reservada,
            )
        )
        if stock:
            raise HTTPException(409, "Aquest disc ja té estoc disponible: el pots comprar directament")

    peticion = PeticionCliente(
        user_id=user.id, release_id=payload.release_id,
        artista_lliure=payload.artista_lliure, titulo_lliure=payload.titulo_lliure,
        notas_cliente=payload.notas_cliente,
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
            PeticionCliente.estado != EstadoPeticionCliente.recollida,
            ~(
                (PeticionCliente.metodo_entrega_triat == "recollida_paga_botiga")
                & (PeticionCliente.estado == EstadoPeticionCliente.reservada)
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
    if peticion.estado != EstadoPeticionCliente.pendent_acceptacio:
        raise HTTPException(409, "Aquesta petició no està esperant acceptació")

    direccion_envio = None
    if payload.metodo_entrega == "envio":
        direccion_envio = _resolver_direccion_envio(db, user, payload)

    peticion.estado = EstadoPeticionCliente.acceptada
    peticion.metodo_entrega_triat = payload.metodo_entrega

    if payload.metodo_entrega in ("envio", "recollida_paga_ara"):
        order = Order(
            user_id=user.id, email_contacto=user.email, status=OrderStatus.pendiente_pago,
            total=peticion.precio_estimado,
            metodo_envio="envio" if payload.metodo_entrega == "envio" else "recogida_tienda",
            metodo_pago="redsys", direccion_envio=direccion_envio,
            notas=f"Petició de client #{str(peticion.id)[:8]}",
        )
        db.add(order)
        db.flush()
        db.add(OrderItem(
            order_id=order.id, item_id=None, release_id=peticion.release_id, precio=peticion.precio_estimado,
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
    if peticion.estado not in estats_amb_pagament_possible or peticion.order_id is None:
        raise HTTPException(409, "Aquesta petició no té cap pagament pendent")

    order = db.get(Order, peticion.order_id)
    if order.status == OrderStatus.pendiente_pago:
        return {"order_id": str(order.id)}
    if order.status != OrderStatus.cancelado:
        raise HTTPException(409, f"Aquesta comanda ja no es pot pagar (estat: {order.status.value})")

    linia = db.scalar(select(OrderItem).where(OrderItem.order_id == order.id))
    nou = Order(
        user_id=user.id, email_contacto=user.email, status=OrderStatus.pendiente_pago,
        total=order.total, metodo_envio=order.metodo_envio, metodo_pago="redsys",
        direccion_envio=order.direccion_envio, notas=order.notas,
    )
    db.add(nou)
    db.flush()
    db.add(OrderItem(order_id=nou.id, item_id=None, release_id=linia.release_id, precio=linia.precio))
    peticion.order_id = nou.id
    db.commit()
    return {"order_id": str(nou.id)}


@router.post("/peticiones/{peticion_id}/rechazar", response_model=PeticionClienteOut)
def rechazar_peticion(
    peticion_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    peticion = _get_own_peticion_or_404(db, peticion_id, user)
    if peticion.estado != EstadoPeticionCliente.pendent_acceptacio:
        raise HTTPException(409, "Aquesta petició no està esperant acceptació")
    peticion.estado = EstadoPeticionCliente.rebutjada
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
    if peticion.estado != EstadoPeticionCliente.pendent_acceptacio:
        raise HTTPException(409, "Aquesta petició no està esperant acceptació")
    nota = f"[El client indica que aquest disc no és el correcte]: {payload.comentari}"
    peticion.notas_cliente = f"{peticion.notas_cliente}\n\n{nota}" if peticion.notas_cliente else nota
    peticion.precio_estimado = None
    peticion.estado = EstadoPeticionCliente.pendent
    db.commit()
    return _peticion_out(_get_own_peticion_or_404(db, peticion.id, user))


@router.delete("/peticiones/{peticion_id}", status_code=204)
def cancelar_peticion(
    peticion_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    peticion = _get_own_peticion_or_404(db, peticion_id, user)
    if peticion.estado not in (EstadoPeticionCliente.pendent, EstadoPeticionCliente.pendent_acceptacio):
        raise HTTPException(409, "Aquesta petició ja no es pot cancel·lar")
    peticion.estado = EstadoPeticionCliente.cancelada
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
    if peticion.estado != EstadoPeticionCliente.reservada:
        raise HTTPException(409, "Aquesta petició encara no té cap exemplar disponible per comprar")
    if peticion.metodo_entrega_triat not in ("envio", "recollida_paga_ara"):
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


# ---------------------------------------------------------------------------
# Subscripció (club del disc)
# ---------------------------------------------------------------------------

def _get_own_subscripcio_or_404(db: Session, user: User) -> Subscripcio:
    subscripcio = db.scalar(
        select(Subscripcio)
        .where(Subscripcio.user_id == user.id, Subscripcio.estat != EstatSubscripcio.cancel_lada)
    )
    if subscripcio is None:
        raise HTTPException(404, "No tens cap subscripció")
    return subscripcio


def _subscripcio_me_dict(db: Session, subscripcio: Subscripcio) -> dict:
    discos_rebuts = list(db.execute(
        select(Release.id, Release.artista, Release.titulo, Release.imagen_url, Assignacio.confirmada_at)
        .join(Assignacio, Assignacio.release_id == Release.id)
        .where(Assignacio.subscripcio_id == subscripcio.id, Assignacio.estat == EstatAssignacio.confirmada)
        .order_by(Assignacio.confirmada_at.desc())
    ).all())
    return {
        "id": subscripcio.id,
        "estat": subscripcio.estat,
        "periodicitat_mesos": subscripcio.periodicitat_mesos,
        "quantitat": subscripcio.quantitat,
        "preu_periode": subscripcio.preu_periode,
        "generes_preferits": subscripcio.generes_preferits,
        "proxima_facturacio": subscripcio.proxima_facturacio,
        "discos_rebuts": [
            {"release_id": r[0], "artista": r[1], "titulo": r[2], "imagen_url": r[3], "confirmada_at": r[4]}
            for r in discos_rebuts
        ],
    }


@router.get("/subscripcio", response_model=SubscripcioMeOut)
def get_subscripcio(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    subscripcio = _get_own_subscripcio_or_404(db, user)
    return _subscripcio_me_dict(db, subscripcio)


@router.patch("/subscripcio", response_model=SubscripcioMeOut)
def patch_subscripcio(
    payload: SubscripcioMePatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subscripcio = _get_own_subscripcio_or_404(db, user)
    if subscripcio.estat == EstatSubscripcio.pendent_pagament:
        raise HTTPException(409, "Encara no s'ha confirmat el pagament d'aquesta subscripció")

    if payload.estat is not None:
        if payload.estat not in ("activa", "pausada"):
            raise HTTPException(422, "Estat no vàlid")
        subscripcio.estat = EstatSubscripcio(payload.estat)
    if payload.generes_preferits is not None:
        subscripcio.generes_preferits = payload.generes_preferits
    if payload.address_id is not None:
        address = db.get(Address, payload.address_id)
        if address is None or address.user_id != user.id:
            raise HTTPException(404, "Adreça no trobada")
        subscripcio.address_id = address.id

    db.commit()
    return _subscripcio_me_dict(db, subscripcio)


@router.post("/subscripcio/cancelar", response_model=SubscripcioMeOut)
def cancelar_subscripcio(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    subscripcio = _get_own_subscripcio_or_404(db, user)
    subscripcio.estat = EstatSubscripcio.cancel_lada
    subscripcio.cancel_lada_at = datetime.now(timezone.utc)
    db.commit()
    return _subscripcio_me_dict(db, subscripcio)
