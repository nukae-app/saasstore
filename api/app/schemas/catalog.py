import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class ItemOut(BaseModel):
    id: uuid.UUID
    price: Decimal
    condition: str
    estado_disco: str | None
    estado_funda: str | None
    status: str
    # Solo relevantes para condicion='nou' (stock agregado); para segona_ma
    # quantity siempre es 1 y reserved_quantity 0.
    quantity: int
    reserved_quantity: int
    min_stock_alert: int | None = None

    model_config = {"from_attributes": True}


class EtiquetaOut(BaseModel):
    id: int
    slug: str
    name_ca: str
    name_es: str | None
    color: str | None
    active: bool
    position: int

    model_config = {"from_attributes": True}


class EtiquetaIn(BaseModel):
    slug: str
    name_ca: str
    name_es: str | None = None
    color: str | None = None
    active: bool = True
    position: int = 0


class GeneroFacetOut(BaseModel):
    """Gènere real amb almenys una còpia disponible — alimenta el bloc
    "genre_grid" del home (ver blocks/registry.py), en lloc de la llista
    fixa que hi havia abans."""
    genero: str
    count: int


class SeccioOut(BaseModel):
    id: int
    slug: str
    name_ca: str
    name_es: str | None
    color: str | None
    active: bool
    position: int

    model_config = {"from_attributes": True}


class SeccioIn(BaseModel):
    slug: str
    name_ca: str
    name_es: str | None = None
    color: str | None = None
    active: bool = True
    position: int = 0


class ReleaseImageOut(BaseModel):
    id: int
    url: str
    position: int
    type: str | None
    source: str

    model_config = {"from_attributes": True}


class ReleaseOut(BaseModel):
    id: uuid.UUID
    # Optional (no `str` a secas): un release del vertical floristry no
    # tiene extensión RecordProduct, así que este campo viene vacío para él
    # — ver docs/ARQUITECTURA_CORE_VERTICAL.md, Fase 2.
    artista: str | None = None
    title: str
    sello: str | None
    referencia: str | None
    ean: str | None = None
    formato: str | None
    anio: int | None
    genero: str | None
    estilos: str | None = None
    pais: str | None = None
    description: str | None
    image_url: str | None
    weight_g: int | None = None
    tracklist: list | None = None
    credits: list | None = None
    coming_soon: bool = False
    available_at: date | None = None
    esta_sonant: bool = False
    seccio: SeccioOut | None = None
    etiquetes: list[EtiquetaOut] = []
    images: list[ReleaseImageOut] = []
    items: list[ItemOut] = []
    spotify_album_id: str | None = None
    # Extensió de floristeria (Fase 4/7) — None per a un tenant vinils.
    color: str | None = None
    tipus_flor: str | None = None
    durabilitat_dies: int | None = None

    model_config = {"from_attributes": True}


class CatalogPage(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[ReleaseOut]


# --- Auth ---


class ReleaseIn(BaseModel):
    # Optional: un tenant del vertical floristry no lo rellena — el backend
    # ignora este campo (y el resto de RECORD_FIELDS) salvo que el tenant
    # sea del vertical records, ver routers/admin.py::_upsert_vertical_extension.
    artista: str | None = None
    title: str
    sello: str | None = None
    referencia: str | None = None
    ean: str | None = None
    formato: str | None = None
    anio: int | None = None
    genero: str | None = None
    estilos: str | None = None
    pais: str | None = None
    description: str | None = None
    image_url: str | None = None
    weight_g: int | None = None
    tracklist: list | None = None
    credits: list | None = None
    discogs_release_id: int | None = None
    section_id: int | None = None
    # Vertical floristry — extensión ReleaseFloristeria, ver
    # routers/admin.py::_upsert_vertical_extension. Un tenant records nunca
    # los rellena (el backend los ignora aunque vinieran en el payload).
    color: str | None = None
    tipus_flor: str | None = None
    durabilitat_dies: int | None = None


class ItemIn(BaseModel):
    release_id: uuid.UUID
    price: Decimal
    acquisition_cost: Decimal | None = None
    condition: str = "segona_ma"
    estado_disco: str | None = None
    estado_funda: str | None = None
    codi_discogs: int | None = None
    # Només per a condicion='nou': unitats donades d'alta. Per a segona_ma
    # sempre 1 (cada alta és una còpia física amb el seu propi grading).
    quantity: int = 1
    # Alarma de stock (Bloc B4): només té sentit per a condicion='nou'.
    min_stock_alert: int | None = None


class ItemUpdate(BaseModel):
    """Edició d'una còpia ja existent. No es permet canviar release_id ni codi_discogs
    (la relació amb el release i amb Discogs es gestionen per altres camins)."""

    price: Decimal
    acquisition_cost: Decimal | None = None
    condition: str = "segona_ma"
    estado_disco: str | None = None
    estado_funda: str | None = None
    min_stock_alert: int | None = None


# --- ERP: Proveedores ---


class CatalogAgingBucketOut(BaseModel):
    key: str
    label: str
    count: int
    valor: Decimal
    coste: Decimal


class CatalogAgingItemOut(BaseModel):
    item_id: uuid.UUID
    release_id: uuid.UUID
    artista: str
    titulo: str
    imagen_url: str | None
    dias: int | None
    fecha_entrada: datetime | None
    precio: Decimal
    coste: Decimal | None
    condicion: str
    origen: Literal["compra", "discogs", "desconegut"]


class CatalogAgingItemsOut(BaseModel):
    total: int
    items: list[CatalogAgingItemOut]


class CatalogAgingOut(BaseModel):
    total_disponible: int
    con_fecha: int
    sin_fecha: int
    valor_total: Decimal
    valor_sin_fecha: Decimal
    coste_total: Decimal
    coste_sin_fecha: Decimal
    edad_media_dias: float | None
    edad_mediana_dias: float | None
    buckets: list[CatalogAgingBucketOut]


class StockAlertItemOut(BaseModel):
    item_id: uuid.UUID
    release_id: uuid.UUID
    artista: str
    titulo: str
    imagen_url: str | None
    disponible: int
    alerta_stock_minimo: int


class StockAlertsOut(BaseModel):
    total: int
    items: list[StockAlertItemOut]
