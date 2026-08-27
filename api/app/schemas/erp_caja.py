import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class CajaSessionIn(BaseModel):
    opened_at: datetime
    opening_float: Decimal
    notes: str | None = None


class CajaCierreIn(BaseModel):
    actual_count: Decimal
    notes: str | None = None


class CajaSessionOut(BaseModel):
    id: uuid.UUID
    opened_at: datetime
    opening_float: Decimal
    closed_at: datetime | None
    total_cash_sales: Decimal | None
    total_cash_in: Decimal | None = None
    total_cash_out: Decimal | None = None
    actual_count: Decimal | None
    diferencia: Decimal | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CajaMovimientoIn(BaseModel):
    type: Literal["entrada", "salida"]
    concept: str
    amount: Decimal
    date: datetime


class CajaMovimientoOut(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    type: str
    concept: str
    amount: Decimal
    date: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Devoluciones ---
