import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class HistorialCompraOut(BaseModel):
    id: uuid.UUID
    proveedor_id: uuid.UUID
    proveedor_nombre: str
    date: date
    artist: str | None
    title: str | None
    label: str | None
    format: str | None
    quantity: int
    cost_price: Decimal | None
    notes: str | None
    release_id: uuid.UUID | None = None
    ean: str | None = None


class HistorialResumProveedorOut(BaseModel):
    proveedor_id: uuid.UUID
    proveedor_nombre: str
    count: int
    ultima_compra: date
