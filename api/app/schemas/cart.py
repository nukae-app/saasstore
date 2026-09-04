import uuid
from decimal import Decimal

from pydantic import BaseModel


class CartAdd(BaseModel):
    item_id: uuid.UUID
    # Solo relevante para condicion='nou' (stock agregado): cuántas unidades
    # de esa línea se quieren en el carrito. Para segona_ma siempre 1.
    quantity: int = 1


class CartItemOut(BaseModel):
    item_id: uuid.UUID
    artista: str | None = None
    title: str
    price: Decimal
    list_price: Decimal | None = None
    status: str
    quantity: int
    condition: str
    image_url: str | None


class CartOut(BaseModel):
    items: list[CartItemOut]
    total: Decimal
