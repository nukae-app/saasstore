import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class CompraParticularItemIn(BaseModel):
    release_id: uuid.UUID
    price: Decimal                       # precio de venta previst al catàleg
    acquisition_cost: Decimal            # preu pagat al particular (sempre conegut)
    condition: str = "segona_ma"
    estado_disco: str | None = None
    estado_funda: str | None = None


class CompraParticularIn(BaseModel):
    individual_name: str | None = None
    user_id: uuid.UUID | None = None   # usuari registrat (opcional)
    date: datetime
    notes: str | None = None
    items: list[CompraParticularItemIn] = Field(min_length=1)

    @model_validator(mode="after")
    def check_origen(self) -> "CompraParticularIn":
        if not self.individual_name and not self.user_id:
            raise ValueError("individual_name o user_id son obligatorios para compras a particular")
        return self


class CompraItemOut(BaseModel):
    item_id: uuid.UUID
    release_id: uuid.UUID
    artista: str
    title: str
    price: Decimal
    acquisition_cost: Decimal | None
    item_status: str = "disponible"
    devuelto: bool = False


class CompraOut(BaseModel):
    id: uuid.UUID
    type: str
    proveedor_id: uuid.UUID | None
    individual_name: str | None
    user_id: uuid.UUID | None = None
    user_nom: str | None = None
    date: datetime
    delivery_note_number: str | None
    notes: str | None
    comanda_id: uuid.UUID | None = None
    despesa_id: uuid.UUID | None = None
    despesa_estat: str | None = None
    created_at: datetime
    items: list[CompraItemOut] = []

    model_config = {"from_attributes": True}


# --- ERP: Comandas a proveïdor ---


class ComprasStatsProveedorOut(BaseModel):
    proveedor_id: uuid.UUID
    nombre: str
    total: Decimal


class ComprasStatsMesOut(BaseModel):
    mes: str  # "2026-07"
    proveidor: Decimal
    particular: Decimal


class ComprasStatsOut(BaseModel):
    total_mes: Decimal
    total_trimestre: Decimal
    total_any: Decimal
    total_mes_proveidor: Decimal
    total_mes_particular: Decimal
    comandes_pendents: int
    sense_facturar_count: int
    sense_facturar_import: Decimal
    top_proveidors: list[ComprasStatsProveedorOut]
    serie_mensual: list[ComprasStatsMesOut]
