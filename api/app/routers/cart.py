"""Carrito persistente: funciona logueado (por user_id) o anónimo (cookie)."""

import secrets
import uuid
from decimal import Decimal

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import Cart, CartItem, CondicionItem, Item, ItemStatus, User
from ..schemas import CartAdd, CartItemOut, CartOut
from ..services.security import get_current_user_optional

router = APIRouter(prefix="/cart", tags=["cart"])

CART_COOKIE = "ulr_cart"


def get_or_create_cart(
    response: Response,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
    ulr_cart: str | None = Cookie(default=None),
) -> Cart:
    if user is not None:
        cart = db.scalar(select(Cart).where(Cart.user_id == user.id))
        if cart is None:
            cart = Cart(user_id=user.id)
            db.add(cart)
            db.commit()
        return cart

    if ulr_cart:
        cart = db.scalar(select(Cart).where(Cart.session_id == ulr_cart))
        if cart is not None:
            return cart

    session_id = secrets.token_urlsafe(24)
    cart = Cart(session_id=session_id)
    db.add(cart)
    db.commit()
    response.set_cookie(CART_COOKIE, session_id, httponly=True, samesite="lax", max_age=30 * 86400)
    return cart


def _serialize(db: Session, cart: Cart) -> CartOut:
    rows = db.scalars(
        select(CartItem)
        .where(CartItem.cart_id == cart.id)
        .options(selectinload(CartItem.item).selectinload(Item.release))
    ).all()
    items = [
        CartItemOut(
            item_id=ci.item.id,
            artista=ci.item.release.artista,
            titulo=ci.item.release.titulo,
            precio=ci.item.precio,
            status=ci.item.status.value,
            cantidad=ci.cantidad,
            condicion=ci.item.condicion.value,
            imagen_url=ci.item.release.imagen_url,
        )
        for ci in rows
    ]
    total = sum((i.precio * i.cantidad for i in items), Decimal("0"))
    return CartOut(items=items, total=total)


@router.get("", response_model=CartOut)
def view_cart(cart: Cart = Depends(get_or_create_cart), db: Session = Depends(get_db)):
    return _serialize(db, cart)


@router.post("/items", response_model=CartOut, status_code=201)
def add_to_cart(payload: CartAdd, cart: Cart = Depends(get_or_create_cart), db: Session = Depends(get_db)):
    item = db.get(Item, payload.item_id)
    if item is None:
        raise HTTPException(404, "Ejemplar no encontrado")

    exists = db.scalar(
        select(CartItem).where(CartItem.cart_id == cart.id, CartItem.item_id == item.id)
    )

    if item.condicion == CondicionItem.nou:
        # Comprobación laxa (igual de laxa que la de segona_ma más abajo): la
        # reserva de verdad, atómica, ocurre en /checkout/start. Aquí solo se
        # evita ofrecer más cantidad de la que físicamente existe.
        cantidad_en_carrito = exists.cantidad if exists else 0
        if item.cantidad < cantidad_en_carrito + payload.cantidad:
            raise HTTPException(409, "No queda suficiente stock de este disco")
        if exists is None:
            db.add(CartItem(cart_id=cart.id, item_id=item.id, cantidad=payload.cantidad))
        else:
            exists.cantidad += payload.cantidad
        db.commit()
        return _serialize(db, cart)

    if item.status != ItemStatus.disponible:
        raise HTTPException(409, "Este ejemplar ya no está disponible")
    if exists is None:
        db.add(CartItem(cart_id=cart.id, item_id=item.id))
        db.commit()
    return _serialize(db, cart)


@router.delete("/items/{item_id}", response_model=CartOut)
def remove_from_cart(item_id: uuid.UUID, cart: Cart = Depends(get_or_create_cart), db: Session = Depends(get_db)):
    row = db.scalar(select(CartItem).where(CartItem.cart_id == cart.id, CartItem.item_id == item_id))
    if row is not None:
        db.delete(row)
        db.commit()
    return _serialize(db, cart)
