import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

CATEGORIES_ACTIU = Literal["maquinaria", "mobiliari", "equips_informatics", "elements_transport", "altres"]


class FixedAssetIn(BaseModel):
    name: str
    category: CATEGORIES_ACTIU
    acquisition_date: date
    acquisition_cost: Decimal
    vat_amount: Decimal = Decimal("0")
    supplier_name: str | None = None
    annual_depreciation_pct: Decimal
    notes: str | None = None


class FixedAssetOut(BaseModel):
    id: uuid.UUID
    name: str
    category: str
    acquisition_date: date
    acquisition_cost: Decimal
    vat_amount: Decimal
    supplier_name: str | None
    depreciation_method: str
    annual_depreciation_pct: Decimal
    disposal_date: date | None
    disposal_amount: Decimal | None
    notes: str | None
    created_at: datetime
    accumulated_depreciation: Decimal
    book_value: Decimal


class AssetDepreciationEntryOut(BaseModel):
    id: uuid.UUID
    actiu_id: uuid.UUID
    year: int
    month: int
    amount: Decimal


class GenerarAmortitzacionsOut(BaseModel):
    year: int
    mes: int
    entrades_generades: list[AssetDepreciationEntryOut]
    actius_saltats: list[str]  # noms d'actius sense amortització aquest mes (ja generada, no vigent o completament amortitzats)
