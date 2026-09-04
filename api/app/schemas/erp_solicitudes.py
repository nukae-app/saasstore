import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class SolicitudCompraLineaIn(BaseModel):
    release_id: uuid.UUID | None = None
    artist: str | None = None
    title: str | None = None
    label: str | None = None
    format: str | None = None
    quantity: int = Field(gt=0, default=1)
    proveedor_sugerido_id: uuid.UUID | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def check_producte(self) -> "SolicitudCompraLineaIn":
        # `artist`/`label`/`format` són detall opcional (només té sentit per
        # a discos, veure docs/ARQUITECTURA_CORE_VERTICAL.md §17.1) — el
        # mínim per descriure una línia sense catàleg encara és `title`,
        # genèric a qualsevol vertical.
        if not self.release_id and not self.title:
            raise ValueError("Cal indicar release_id, o bé title (producte encara no catalogat)")
        return self


class PoolLineasIn(BaseModel):
    """Afegeix línies soltes al pool (sense sol·licitud): `origen` s'aplica
    a totes les línies d'aquesta crida. `peticion_cliente` no és aquí perquè
    ja té el seu propi flux (`POST /peticiones/{id}/vincular-solicitud`)."""
    origen: Literal["manual", "refill_stock"] = "manual"
    lineas: list[SolicitudCompraLineaIn] = Field(min_length=1)


class SolicitudGenerarIn(BaseModel):
    """Consolida línies del pool (`solicitud_id IS NULL`, poden ser de
    diversos orígens) en una nova sol·licitud numerada."""
    linea_ids: list[uuid.UUID] = Field(min_length=1)
    notes: str | None = None


class SolicitudCompraLineaOut(BaseModel):
    id: uuid.UUID
    origen: str
    release_id: uuid.UUID | None
    artist: str | None
    title: str | None
    label: str | None
    format: str | None
    quantity: int
    proveedor_sugerido_id: uuid.UUID | None
    proveedor_sugerido_nombre: str | None = None
    comanda_linea_id: uuid.UUID | None
    item_resuelto_id: uuid.UUID | None = None
    resuelta: bool = False
    notes: str | None
    created_at: datetime


class SolicitudCompraOut(BaseModel):
    id: uuid.UUID
    numero: str
    estado: str
    # Orígens distints de les línies que conté (pot ser més d'un: una
    # sol·licitud consolidada des del pool pot barrejar-los).
    origenes: list[str]
    user_id: uuid.UUID | None
    user_nom: str | None = None
    notes: str | None
    created_at: datetime
    lineas: list[SolicitudCompraLineaOut] = []


class SolicitudResolverLineaIn(BaseModel):
    solicitud_linea_id: uuid.UUID
    quantity: int | None = None  # per defecte, la cantidad demanada a la línia
    estimated_unit_price: Decimal | None = None
    # Si la línia es va crear a mà (sense release_id, disc encara no al
    # catàleg), el frontend el resol aquí mateix (cerca a Discogs + alta
    # automàtica, o alta manual) en comptes d'obligar a sortir d'aquesta
    # pantalla. Si la línia ja tenia release_id, es pot ometre.
    release_id: uuid.UUID | None = None


class SolicitudResolverIn(BaseModel):
    proveedor_id: uuid.UUID
    date: datetime
    notes: str | None = None
    lineas: list[SolicitudResolverLineaIn] = Field(min_length=1)


class ResoldreEstocIn(BaseModel):
    item_id: uuid.UUID


class SolicitudPoolPage(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[SolicitudCompraLineaOut]


class SolicitudCompraListPage(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[SolicitudCompraOut]


class RefillSugerenciaOut(BaseModel):
    release_id: uuid.UUID
    artista: str
    titulo: str
    formato: str | None
    stock_actual: int
    vendes_periode: int
    vendes_periode_anterior: int
    tendencia: Literal["accelerant", "frenant", "estable"]
    dies_estoc: float
    marge_mitja: Decimal | None
    devolucions_recents: int
    cantidad_sugerida: int
    proveedor_sugerido_id: uuid.UUID | None
    proveedor_sugerido_nombre: str | None
