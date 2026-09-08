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


class FacturaLiniaIn(BaseModel):
    description: str
    quantity: Decimal = Field(gt=0, default=Decimal("1"))
    unit_price: Decimal
    vat_pct: Decimal = Decimal("21")


class FacturaManualIn(BaseModel):
    """Factura des de zero (servei fora del catàleg) — ver Factura.origen."""
    client_name: str
    client_nif: str | None = None
    user_id: uuid.UUID | None = None
    notes: str | None = None
    lines: list[FacturaLiniaIn] = Field(min_length=1)


class FacturaLiniaOut(BaseModel):
    id: uuid.UUID
    description: str
    quantity: Decimal
    unit_price: Decimal
    vat_pct: Decimal


class FacturaOut(BaseModel):
    id: uuid.UUID
    fiscal_year: int
    number: int
    origen: str
    status: str
    order_id: uuid.UUID | None
    user_id: uuid.UUID | None
    client_name: str
    client_nif: str | None
    client_address: dict | None
    issue_date: date
    notes: str | None
    base_total: Decimal
    vat_total: Decimal
    total: Decimal
    created_at: datetime
    lines: list[FacturaLiniaOut] = []
