import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class AddressIn(BaseModel):
    recipient_name: str
    address_line1: str
    address_line2: str | None = None
    city: str
    postal_code: str
    province: str | None = None
    country: str = "ES"
    phone: str | None = None


class CheckoutConfirm(BaseModel):
    contact_email: EmailStr
    shipping_method: str = Field(pattern="^(envio|recogida_tienda)$")
    payment_method: str = Field(default="redsys", pattern="^(redsys|tienda)$")
    shipping_address: AddressIn | None = None
    notes: str | None = None
    language: str = "ca"


class OrderOut(BaseModel):
    id: uuid.UUID
    status: str
    total: Decimal
    shipping_cost: Decimal
    shipping_method: str
    payment_method: str
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderStatusUpdate(BaseModel):
    status: str | None = None
    tracking_number: str | None = None
    carrier: str | None = None
    shipping_method: Literal["envio", "recogida_tienda"] | None = None
    shipping_address: AddressIn | None = None


# --- Admin ---


class OrderPendentTiendaItemOut(BaseModel):
    item_id: uuid.UUID | None
    artista: str | None
    titulo: str | None
    imagen_url: str | None
    estado_disco: str | None
    precio: Decimal


class OrderPendentTiendaOut(BaseModel):
    order_id: uuid.UUID
    email: str
    total: Decimal
    created_at: datetime
    reserved_until: datetime | None  # mínim entre els items de la comanda
    user_id: uuid.UUID | None
    user_nombre: str | None
    items: list[OrderPendentTiendaItemOut]


class OrderMarcarPagadoTiendaIn(BaseModel):
    payment_method: Literal["efectivo", "tarjeta"]
    # Descompte aplicat al mostrador (opcional). Només vàlid si la comanda té
    # un únic disc: amb diversos OrderItem no hi ha un preu unitari a on
    # aplicar-lo sense ambigüitat.
    price: Decimal | None = None
