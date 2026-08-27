import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class ConfiguracioSubscripcioOut(BaseModel):
    preu_per_disc: Decimal
    marge_min_pct: Decimal
    marge_max_pct: Decimal
    periodicitats_mesos_disponibles: list[int]
    quantitats_disponibles: list[int]

    model_config = {"from_attributes": True}


class ConfiguracioSubscripcioUpdate(BaseModel):
    preu_per_disc: Decimal | None = None
    marge_min_pct: Decimal | None = None
    marge_max_pct: Decimal | None = None
    periodicitats_mesos_disponibles: list[int] | None = None
    quantitats_disponibles: list[int] | None = None


class SubscripcioAltaIn(BaseModel):
    periodicitat_mesos: int
    quantitat: int
    address_id: uuid.UUID
    generes_preferits: list[str] | None = None


class SubscripcioReleaseRebutOut(BaseModel):
    release_id: uuid.UUID
    artista: str
    titulo: str
    imagen_url: str | None
    confirmada_at: datetime | None


class SubscripcioMeOut(BaseModel):
    id: uuid.UUID
    estat: str
    periodicitat_mesos: int
    quantitat: int
    preu_periode: Decimal
    generes_preferits: list[str] | None
    proxima_facturacio: date
    discos_rebuts: list[SubscripcioReleaseRebutOut]

    model_config = {"from_attributes": True}


class SubscripcioMePatch(BaseModel):
    estat: Literal["activa", "pausada"] | None = None
    generes_preferits: list[str] | None = None
    address_id: uuid.UUID | None = None


class SubscripcioCatalogItemOut(BaseModel):
    item_id: uuid.UUID
    release_id: uuid.UUID
    artista: str
    titulo: str
    imagen_url: str | None
    precio: Decimal
    marge_pct: float
    dies_estoc: int | None
    subscription_pool: bool


class InformeSubscripcioMensualOut(BaseModel):
    any_: int = Field(serialization_alias="any")
    mes: int
    subscriptors_actius: int
    noves_subscripcions: int
    baixes: int
    cobraments_ok: int
    import_total: Decimal
    cobraments_fallits: int
    discos_enviats: int

    model_config = {"populate_by_name": True}


# --- Secretos de tenant (Redsys/Discogs/Spotify) ---
# Compartidas entre routers/configuracio.py (GET/POST /admin/secrets, el
# propio tenant edita los suyos, Fase 5) y routers/superadmin.py (GET
# /superadmin/tenants/{id}/secrets, solo lectura de estado — el operador
# ya no puede escribirlos).
