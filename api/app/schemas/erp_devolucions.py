import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, model_validator


class DevolucionVentaIn(BaseModel):
    order_item_id: uuid.UUID | None = None
    venta_externa_id: uuid.UUID | None = None
    item_id: uuid.UUID
    reason: str
    item_destination: Literal["disponible", "retirat"] = "disponible"
    date: datetime
    notes: str | None = None
    # Solo relevante para condicion='nou': unidades que se devuelven.
    quantity: int = 1

    @model_validator(mode="after")
    def check_origen(self) -> "DevolucionVentaIn":
        if not self.order_item_id and not self.venta_externa_id:
            raise ValueError("Se requiere order_item_id o venta_externa_id")
        return self


class DevolucionVentaOut(BaseModel):
    id: uuid.UUID
    order_item_id: uuid.UUID | None
    venta_externa_id: uuid.UUID | None
    item_id: uuid.UUID
    reason: str
    item_destination: str
    date: datetime
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DevolucionCompraIn(BaseModel):
    item_id: uuid.UUID
    compra_id: uuid.UUID | None = None
    reason: str
    date: datetime
    notes: str | None = None
    # Solo relevante para condicion='nou': unidades que se devuelven al proveedor/particular.
    quantity: int = 1


class DevolucionCompraOut(BaseModel):
    id: uuid.UUID
    item_id: uuid.UUID
    compra_id: uuid.UUID | None
    reason: str
    date: datetime
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Blog y agenda ---
