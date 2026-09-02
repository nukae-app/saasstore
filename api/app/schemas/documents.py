import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class PressupostLiniaIn(BaseModel):
    description: str
    quantity: Decimal = Field(gt=0, default=Decimal("1"))
    unit_price: Decimal
    vat_pct: Decimal = Decimal("21")


class PressupostIn(BaseModel):
    client_name: str
    client_email: str | None = None
    user_id: uuid.UUID | None = None
    valid_until: date | None = None
    notes: str | None = None
    lines: list[PressupostLiniaIn] = Field(min_length=1)


class PressupostStatusIn(BaseModel):
    status: str


class PressupostLiniaOut(BaseModel):
    id: uuid.UUID
    description: str
    quantity: Decimal
    unit_price: Decimal
    vat_pct: Decimal


class PressupostOut(BaseModel):
    id: uuid.UUID
    fiscal_year: int
    number: int
    status: str
    client_name: str
    client_email: str | None
    user_id: uuid.UUID | None
    issue_date: date
    valid_until: date | None
    notes: str | None
    converted_order_id: uuid.UUID | None
    created_at: datetime
    lines: list[PressupostLiniaOut] = []


class AlbaraIn(BaseModel):
    order_id: uuid.UUID
    delivery_date: date | None = None
    notes: str | None = None


class AlbaraOut(BaseModel):
    id: uuid.UUID
    fiscal_year: int
    number: int
    order_id: uuid.UUID
    delivery_date: date
    notes: str | None
    created_at: datetime
