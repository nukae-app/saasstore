import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ComandaLineaIn(BaseModel):
    release_id: uuid.UUID
    quantity: int = Field(gt=0)
    estimated_unit_price: Decimal | None = None
    notes: str | None = None


class ComandaIn(BaseModel):
    proveedor_id: uuid.UUID
    date: datetime
    notes: str | None = None
    lineas: list[ComandaLineaIn] = Field(min_length=1)


class ComandaLineaOut(BaseModel):
    id: uuid.UUID
    release_id: uuid.UUID
    artista: str
    titulo: str
    quantity: int
    estimated_unit_price: Decimal | None
    received_quantity: int
    notes: str | None


class ComandaOut(BaseModel):
    id: uuid.UUID
    proveedor_id: uuid.UUID
    proveedor_nombre: str
    date: datetime
    status: str
    order_number: str | None
    notes: str | None
    sent_at: datetime | None
    created_at: datetime
    lineas: list[ComandaLineaOut] = []


class RecepcionItemIn(BaseModel):
    comanda_linea_id: uuid.UUID
    price: Decimal
    # La majoria de discos que entren per comanda a proveïdor són nous
    # (a diferència de la compra a particular, sempre segona mà per defecte).
    condition: str = "nou"
    acquisition_cost: Decimal | None = None
    estado_disco: str | None = None
    estado_funda: str | None = None
    # Només té sentit per a condicion='nou' (stock agregat): unitats que
    # representa aquesta entrada. Per a segona_ma sempre 1 (cada entrada és
    # una còpia física amb el seu propi grading).
    quantity: int = 1


class RecepcionIn(BaseModel):
    date: datetime
    delivery_note_number: str | None = None
    notes: str | None = None
    items: list[RecepcionItemIn] = Field(min_length=1)


# --- ERP: Ventas externas (TPV + Discogs) ---
