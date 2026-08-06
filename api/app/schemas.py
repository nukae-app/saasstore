"""Esquemas Pydantic de entrada/salida de la API (no exponen los modelos tal cual)."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator, computed_field


# --- Catálogo ---

class ItemOut(BaseModel):
    id: uuid.UUID
    precio: Decimal
    condicion: str
    estado_disco: str | None
    estado_funda: str | None
    status: str
    # Solo relevantes para condicion='nou' (stock agregado); para segona_ma
    # cantidad siempre es 1 y cantidad_reservada 0.
    cantidad: int
    cantidad_reservada: int

    model_config = {"from_attributes": True}


class EtiquetaOut(BaseModel):
    id: int
    slug: str
    nom_ca: str
    nom_es: str | None
    color: str | None
    activa: bool
    posicio: int

    model_config = {"from_attributes": True}


class EtiquetaIn(BaseModel):
    slug: str
    nom_ca: str
    nom_es: str | None = None
    color: str | None = None
    activa: bool = True
    posicio: int = 0


class SeccioOut(BaseModel):
    id: int
    slug: str
    nom_ca: str
    nom_es: str | None
    color: str | None
    activa: bool
    posicio: int

    model_config = {"from_attributes": True}


class SeccioIn(BaseModel):
    slug: str
    nom_ca: str
    nom_es: str | None = None
    color: str | None = None
    activa: bool = True
    posicio: int = 0


class ReleaseImageOut(BaseModel):
    id: int
    url: str
    posicio: int
    tipus: str | None
    font: str

    model_config = {"from_attributes": True}


class ReleaseOut(BaseModel):
    id: uuid.UUID
    artista: str
    titulo: str
    sello: str | None
    referencia: str | None
    ean: str | None = None
    formato: str | None
    anio: int | None
    genero: str | None
    estilos: str | None = None
    pais: str | None = None
    descripcion: str | None
    imagen_url: str | None
    pes_g: int | None = None
    tracklist: list | None = None
    credits: list | None = None
    properament: bool = False
    data_disponibilitat: date | None = None
    esta_sonant: bool = False
    seccio: SeccioOut | None = None
    etiquetes: list[EtiquetaOut] = []
    images: list[ReleaseImageOut] = []
    items: list[ItemOut] = []
    spotify_album_id: str | None = None

    model_config = {"from_attributes": True}


class CatalogPage(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[ReleaseOut]


# --- Auth ---

class MagicLinkRequest(BaseModel):
    email: EmailStr
    idioma: str = "ca"


class PasswordLoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    nombre: str | None = None
    idioma: str = "ca"


class SetPasswordRequest(BaseModel):
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    nombre: str | None
    rol: str
    idioma: str

    model_config = {"from_attributes": True}


# --- Carrito y checkout ---

class CartAdd(BaseModel):
    item_id: uuid.UUID
    # Solo relevante para condicion='nou' (stock agregado): cuántas unidades
    # de esa línea se quieren en el carrito. Para segona_ma siempre 1.
    cantidad: int = 1


class CartItemOut(BaseModel):
    item_id: uuid.UUID
    artista: str
    titulo: str
    precio: Decimal
    status: str
    cantidad: int
    condicion: str
    imagen_url: str | None


class CartOut(BaseModel):
    items: list[CartItemOut]
    total: Decimal


class AddressIn(BaseModel):
    nombre_destinatario: str
    linea1: str
    linea2: str | None = None
    ciudad: str
    cp: str
    provincia: str | None = None
    pais: str = "ES"
    telefono: str | None = None


class CheckoutConfirm(BaseModel):
    email_contacto: EmailStr
    metodo_envio: str = Field(pattern="^(envio|recogida_tienda)$")
    metodo_pago: str = Field(default="redsys", pattern="^(redsys|tienda)$")
    direccion_envio: AddressIn | None = None
    notas: str | None = None
    idioma: str = "ca"


class OrderOut(BaseModel):
    id: uuid.UUID
    status: str
    total: Decimal
    coste_envio: Decimal
    metodo_envio: str
    metodo_pago: str
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderStatusUpdate(BaseModel):
    status: str | None = None
    numero_seguiment: str | None = None
    transportista: str | None = None
    metodo_envio: Literal["envio", "recogida_tienda"] | None = None
    direccion_envio: AddressIn | None = None


# --- Admin ---

class ReleaseIn(BaseModel):
    artista: str
    titulo: str
    sello: str | None = None
    referencia: str | None = None
    ean: str | None = None
    formato: str | None = None
    anio: int | None = None
    genero: str | None = None
    estilos: str | None = None
    pais: str | None = None
    descripcion: str | None = None
    imagen_url: str | None = None
    pes_g: int | None = None
    tracklist: list | None = None
    credits: list | None = None
    discogs_release_id: int | None = None
    seccio_id: int | None = None


class ItemIn(BaseModel):
    release_id: uuid.UUID
    precio: Decimal
    coste_adquisicion: Decimal | None = None
    condicion: str = "segona_ma"
    estado_disco: str | None = None
    estado_funda: str | None = None
    codi_discogs: int | None = None
    # Només per a condicion='nou': unitats donades d'alta. Per a segona_ma
    # sempre 1 (cada alta és una còpia física amb el seu propi grading).
    cantidad: int = 1


class ItemUpdate(BaseModel):
    """Edició d'una còpia ja existent. No es permet canviar release_id ni codi_discogs
    (la relació amb el release i amb Discogs es gestionen per altres camins)."""

    precio: Decimal
    coste_adquisicion: Decimal | None = None
    condicion: str = "segona_ma"
    estado_disco: str | None = None
    estado_funda: str | None = None


# --- ERP: Proveedores ---

TIPUS_PROVEIDOR = Literal[
    "distribuidor", "proveidor_online", "subministrador",
    "professional", "transport", "particular", "altres"
]
METODES_PAGAMENT_PROV = Literal[
    "transferencia", "rebut_domiciliat", "targeta", "efectiu", "paypal_altres"
]


class ProveedorIn(BaseModel):
    nombre: str
    tipo: TIPUS_PROVEIDOR | None = None
    nif: str | None = None
    email: str | None = None
    telefon: str | None = None
    direccion: str | None = None
    contacto: str | None = None
    actiu: bool = True
    iban_proveidor: str | None = None
    metode_pagament: METODES_PAGAMENT_PROV | None = None
    dies_pagament: int | None = None
    dia_pagament_mes: int | None = None
    notas: str | None = None


class ProveedorOut(BaseModel):
    id: uuid.UUID
    nombre: str
    tipo: str | None
    nif: str | None
    email: str | None
    telefon: str | None
    direccion: str | None
    contacto: str | None
    actiu: bool
    iban_proveidor: str | None
    metode_pagament: str | None
    dies_pagament: int | None
    dia_pagament_mes: int | None
    notas: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- ERP: Compras a particular (entrada de stock instantània) ---
# Les compres a proveïdor ja no es creen directament: passen sempre per
# Comanda -> recepció (veure més avall).

class CompraParticularItemIn(BaseModel):
    release_id: uuid.UUID
    precio: Decimal                       # precio de venta previst al catàleg
    coste_adquisicion: Decimal            # preu pagat al particular (sempre conegut)
    condicion: str = "segona_ma"
    estado_disco: str | None = None
    estado_funda: str | None = None


class CompraParticularIn(BaseModel):
    nombre_particular: str | None = None
    user_id: uuid.UUID | None = None   # usuari registrat (opcional)
    fecha: datetime
    notas: str | None = None
    items: list[CompraParticularItemIn] = Field(min_length=1)

    @model_validator(mode="after")
    def check_origen(self) -> "CompraParticularIn":
        if not self.nombre_particular and not self.user_id:
            raise ValueError("nombre_particular o user_id son obligatorios para compras a particular")
        return self


class CompraItemOut(BaseModel):
    item_id: uuid.UUID
    release_id: uuid.UUID
    artista: str
    titulo: str
    precio: Decimal
    coste_adquisicion: Decimal | None
    item_status: str = "disponible"
    devuelto: bool = False


class CompraOut(BaseModel):
    id: uuid.UUID
    tipo: str
    proveedor_id: uuid.UUID | None
    nombre_particular: str | None
    user_id: uuid.UUID | None = None
    user_nom: str | None = None
    fecha: datetime
    num_albaran: str | None
    notas: str | None
    comanda_id: uuid.UUID | None = None
    despesa_id: uuid.UUID | None = None
    despesa_estat: str | None = None
    created_at: datetime
    items: list[CompraItemOut] = []

    model_config = {"from_attributes": True}


# --- ERP: Comandas a proveïdor ---

class ComandaLineaIn(BaseModel):
    release_id: uuid.UUID
    cantidad: int = Field(gt=0)
    precio_unitario_estimado: Decimal | None = None
    notas: str | None = None


class ComandaIn(BaseModel):
    proveedor_id: uuid.UUID
    fecha: datetime
    notas: str | None = None
    lineas: list[ComandaLineaIn] = Field(min_length=1)


class ComandaLineaOut(BaseModel):
    id: uuid.UUID
    release_id: uuid.UUID
    artista: str
    titulo: str
    cantidad: int
    precio_unitario_estimado: Decimal | None
    cantidad_rebuda: int
    notas: str | None


class ComandaOut(BaseModel):
    id: uuid.UUID
    proveedor_id: uuid.UUID
    proveedor_nombre: str
    fecha: datetime
    status: str
    num_comanda: str | None
    notas: str | None
    enviada_at: datetime | None
    created_at: datetime
    lineas: list[ComandaLineaOut] = []


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


class SolicitudCompraLineaIn(BaseModel):
    release_id: uuid.UUID | None = None
    artista: str | None = None
    titulo: str | None = None
    sello: str | None = None
    formato: str | None = None
    cantidad: int = Field(gt=0, default=1)
    proveedor_sugerido_id: uuid.UUID | None = None
    notas: str | None = None

    @model_validator(mode="after")
    def check_disco(self) -> "SolicitudCompraLineaIn":
        if not self.release_id and not (self.artista and self.titulo):
            raise ValueError("Cal indicar release_id, o bé artista i titulo (disc encara no catalogat)")
        return self


class SolicitudCompraIn(BaseModel):
    origen: Literal["manual", "refill_stock"] = "manual"
    user_id: uuid.UUID | None = None
    notas: str | None = None
    lineas: list[SolicitudCompraLineaIn] = Field(min_length=1)


class SolicitudCompraLineaOut(BaseModel):
    id: uuid.UUID
    release_id: uuid.UUID | None
    artista: str | None
    titulo: str | None
    sello: str | None
    formato: str | None
    cantidad: int
    proveedor_sugerido_id: uuid.UUID | None
    proveedor_sugerido_nombre: str | None = None
    comanda_linea_id: uuid.UUID | None
    item_resuelto_id: uuid.UUID | None = None
    resuelta: bool = False
    notas: str | None


class SolicitudCompraOut(BaseModel):
    id: uuid.UUID
    estado: str
    origen: str
    user_id: uuid.UUID | None
    user_nom: str | None = None
    notas: str | None
    created_at: datetime
    lineas: list[SolicitudCompraLineaOut] = []


class SolicitudResolverLineaIn(BaseModel):
    solicitud_linea_id: uuid.UUID
    cantidad: int | None = None  # per defecte, la cantidad demanada a la línia
    precio_unitario_estimado: Decimal | None = None


class SolicitudResolverIn(BaseModel):
    proveedor_id: uuid.UUID
    fecha: datetime
    notas: str | None = None
    lineas: list[SolicitudResolverLineaIn] = Field(min_length=1)


class ResoldreEstocIn(BaseModel):
    item_id: uuid.UUID


class HistorialCompraOut(BaseModel):
    id: uuid.UUID
    proveedor_id: uuid.UUID
    proveedor_nombre: str
    fecha: date
    artista: str | None
    titulo: str | None
    sello: str | None
    formato: str | None
    cantidad: int
    precio_coste: Decimal | None
    notas: str | None
    release_id: uuid.UUID | None = None
    ean: str | None = None


class HistorialResumProveedorOut(BaseModel):
    proveedor_id: uuid.UUID
    proveedor_nombre: str
    count: int
    ultima_compra: date


class PeticionClienteAdminOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_nombre: str | None
    user_email: str
    canal: str
    release_id: uuid.UUID | None
    artista: str | None
    titulo: str | None
    estado: str
    precio_estimado: Decimal | None
    metodo_entrega_triat: str | None
    notas_cliente: str | None
    notas_admin: str | None
    solicitud_compra_linea_id: uuid.UUID | None
    order_id: uuid.UUID | None = None
    pagada: bool = False
    created_at: datetime


class PeticionCatalogarIn(BaseModel):
    release_id: uuid.UUID


class PeticionPrecioIn(BaseModel):
    precio_estimado: Decimal


class PeticionVincularIn(BaseModel):
    cantidad: int = Field(gt=0, default=1)
    proveedor_sugerido_id: uuid.UUID | None = None


class PeticionVincularItemIn(BaseModel):
    item_id: uuid.UUID


class PeticionTiendaIn(BaseModel):
    """Petició creada per l'admin en nom d'un client (trucada o mostrador).
    Mateixa forma que `PeticionClienteIn` de me.py, però el client s'indica
    explícitament (ja existent al sistema; l'admin el busca o el crea des de
    /admin/users abans de cridar aquest endpoint)."""

    user_id: uuid.UUID
    release_id: uuid.UUID | None = None
    artista_lliure: str | None = None
    titulo_lliure: str | None = None
    notas_cliente: str | None = None

    @model_validator(mode="after")
    def check_disco(self) -> "PeticionTiendaIn":
        if not self.release_id and not (self.artista_lliure and self.titulo_lliure):
            raise ValueError("Cal indicar release_id, o bé artista i títol (disc fora de catàleg)")
        return self


class ReservaRecollidaOut(BaseModel):
    peticion_id: uuid.UUID
    item_id: uuid.UUID
    artista: str
    titulo: str
    imagen_url: str | None
    precio: Decimal
    condicion: str
    estado_disco: str | None
    user_id: uuid.UUID
    user_nombre: str | None
    user_email: str
    reserved_until: datetime | None


class OrderPendentTiendaItemOut(BaseModel):
    item_id: uuid.UUID | None
    artista: str | None
    titulo: str | None
    imagen_url: str | None
    estado_disco: str | None
    precio: Decimal


class OrderPendentTiendaOut(BaseModel):
    order_id: uuid.UUID
    email: str
    total: Decimal
    created_at: datetime
    reserved_until: datetime | None  # mínim entre els items de la comanda
    user_id: uuid.UUID | None
    user_nombre: str | None
    items: list[OrderPendentTiendaItemOut]


class OrderMarcarPagadoTiendaIn(BaseModel):
    metodo_pago: Literal["efectivo", "tarjeta"]
    # Descompte aplicat al mostrador (opcional). Només vàlid si la comanda té
    # un únic disc: amb diversos OrderItem no hi ha un preu unitari a on
    # aplicar-lo sense ambigüitat.
    precio: Decimal | None = None


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


class RecepcionItemIn(BaseModel):
    comanda_linea_id: uuid.UUID
    precio: Decimal
    # La majoria de discos que entren per comanda a proveïdor són nous
    # (a diferència de la compra a particular, sempre segona mà per defecte).
    condicion: str = "nou"
    coste_adquisicion: Decimal | None = None
    estado_disco: str | None = None
    estado_funda: str | None = None
    # Només té sentit per a condicion='nou' (stock agregat): unitats que
    # representa aquesta entrada. Per a segona_ma sempre 1 (cada entrada és
    # una còpia física amb el seu propi grading).
    cantidad: int = 1


class RecepcionIn(BaseModel):
    fecha: datetime
    num_albaran: str | None = None
    notas: str | None = None
    items: list[RecepcionItemIn] = Field(min_length=1)


# --- ERP: Ventas externas (TPV + Discogs) ---

class VentaExternaIn(BaseModel):
    # Venda de catàleg: item_id (còpia física reservada i venuda). Venda
    # d'article manual (llibre, samarreta...): item_id buit, descripcion +
    # tipus_iva_id obligatoris perquè no hi ha `Item` del qual deduir-los.
    item_id: uuid.UUID | None = None
    descripcion: str | None = None
    tipus_iva_id: int | None = None
    canal: Literal["mostrador", "discogs", "otro"]
    metodo_pago: Literal["efectivo", "tarjeta", "bizum", "bono_cultural"] = "efectivo"
    precio_venta: Decimal
    # Solo relevante para condicion='nou': unidades que cubre precio_venta
    # (que es el TOTAL de la línea, no por unidad).
    cantidad: int = 1
    fecha: datetime
    nombre_cliente: str | None = None
    user_id: uuid.UUID | None = None   # usuari registrat (opcional)
    discogs_sale_id: int | None = None
    notas: str | None = None

    @model_validator(mode="after")
    def _item_o_manual(self):
        if self.item_id is None:
            if not (self.descripcion and self.descripcion.strip()):
                raise ValueError("Un article manual necessita descripcion")
            if self.tipus_iva_id is None:
                raise ValueError("Un article manual necessita tipus_iva_id")
        return self


class VentaExternaLoteLineaIn(BaseModel):
    item_id: uuid.UUID | None = None
    descripcion: str | None = None
    tipus_iva_id: int | None = None
    precio_venta: Decimal
    # Solo relevante para condicion='nou' (stock agregado): unidades que
    # cubre precio_venta (que es el TOTAL de la línea, no por unidad).
    cantidad: int = 1

    @model_validator(mode="after")
    def _item_o_manual(self):
        if self.item_id is None:
            if not (self.descripcion and self.descripcion.strip()):
                raise ValueError("Un article manual necessita descripcion")
            if self.tipus_iva_id is None:
                raise ValueError("Un article manual necessita tipus_iva_id")
        return self


class VentaExternaLoteIn(BaseModel):
    """Venta de varios ejemplares (discos distintos, o varias copias del
    mismo álbum) en una sola operación de TPV. Comparten canal, método de
    pago, fecha y cliente; el precio se fija por línea porque cada ejemplar
    es único."""
    lineas: list[VentaExternaLoteLineaIn] = Field(min_length=1)
    canal: Literal["mostrador", "discogs", "otro"] = "mostrador"
    metodo_pago: Literal["efectivo", "tarjeta", "bizum", "bono_cultural"] = "efectivo"
    fecha: datetime
    nombre_cliente: str | None = None
    user_id: uuid.UUID | None = None
    notas: str | None = None


class VincularUsuariTicketIn(BaseModel):
    """Vincula (o desvincula, amb None) un usuari registrat a totes les
    línies d'un tiquet ja cobrat — per quan al moment de vendre no es va
    triar client i es vol lligar més tard des de Resum vendes."""
    user_id: uuid.UUID | None = None


class VentaExternaOut(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID
    item_id: uuid.UUID | None
    descripcion: str | None = None
    canal: str
    metodo_pago: str = "efectivo"
    precio_venta: Decimal
    coste_adquisicion: Decimal | None
    fecha: datetime
    nombre_cliente: str | None = None
    user_id: uuid.UUID | None = None
    user_nom: str | None = None
    discogs_sale_id: int | None
    notas: str | None
    created_at: datetime
    tipus_iva_id: int | None = None
    iva_pct: Decimal | None = None
    iva_import: Decimal | None = None
    cantidad: int = 1
    condicion: str | None = None
    # Enriquecido en el endpoint (no viene del ORM directamente)
    artista: str | None = None
    titulo: str | None = None
    devuelta: bool = False

    model_config = {"from_attributes": True}


class CajaSessionIn(BaseModel):
    fecha_apertura: datetime
    fondo_inicial: Decimal
    notas: str | None = None


class CajaCierreIn(BaseModel):
    conteo_real: Decimal
    notas: str | None = None


class CajaSessionOut(BaseModel):
    id: uuid.UUID
    fecha_apertura: datetime
    fondo_inicial: Decimal
    fecha_cierre: datetime | None
    total_ventas_efectivo: Decimal | None
    total_entradas: Decimal | None = None
    total_salidas: Decimal | None = None
    conteo_real: Decimal | None
    diferencia: Decimal | None
    notas: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CajaMovimientoIn(BaseModel):
    tipo: Literal["entrada", "salida"]
    concepto: str
    importe: Decimal
    fecha: datetime


class CajaMovimientoOut(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    tipo: str
    concepto: str
    importe: Decimal
    fecha: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Devoluciones ---

class DevolucionVentaIn(BaseModel):
    order_item_id: uuid.UUID | None = None
    venta_externa_id: uuid.UUID | None = None
    item_id: uuid.UUID
    motivo: str
    destino_item: Literal["disponible", "retirat"] = "disponible"
    fecha: datetime
    notas: str | None = None
    # Solo relevante para condicion='nou': unidades que se devuelven.
    cantidad: int = 1

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
    motivo: str
    destino_item: str
    fecha: datetime
    notas: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DevolucionCompraIn(BaseModel):
    item_id: uuid.UUID
    compra_id: uuid.UUID | None = None
    motivo: str
    fecha: datetime
    notas: str | None = None
    # Solo relevante para condicion='nou': unidades que se devuelven al proveedor/particular.
    cantidad: int = 1


class DevolucionCompraOut(BaseModel):
    id: uuid.UUID
    item_id: uuid.UUID
    compra_id: uuid.UUID | None
    motivo: str
    fecha: datetime
    notas: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Blog y agenda ---

class PostOut(BaseModel):
    slug: str
    titulo: str
    contenido: str
    idioma: str
    publicado_at: datetime | None

    model_config = {"from_attributes": True}


class EventOut(BaseModel):
    id: uuid.UUID
    titulo: str
    descripcion: str | None
    fecha: datetime
    lugar: str
    link: str | None

    model_config = {"from_attributes": True}


# --- Comptabilitat: Tipus d'IVA ---

class TipusIvaIn(BaseModel):
    nom: str
    percentatge: Decimal
    es_rebu: bool = False
    per_defecte_nou: bool = False
    per_defecte_segona_ma: bool = False
    actiu: bool = True


class TipusIvaUpdate(BaseModel):
    nom: str | None = None
    percentatge: Decimal | None = None
    es_rebu: bool | None = None
    per_defecte_nou: bool | None = None
    per_defecte_segona_ma: bool | None = None
    actiu: bool | None = None


class TipusIvaOut(BaseModel):
    id: int
    nom: str
    percentatge: Decimal
    es_rebu: bool
    per_defecte_nou: bool
    per_defecte_segona_ma: bool
    actiu: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MargeConfigIn(BaseModel):
    nom: str
    percentatge: Decimal
    per_defecte_nou: bool = False
    per_defecte_segona_ma: bool = False
    actiu: bool = True


class MargeConfigUpdate(BaseModel):
    nom: str | None = None
    percentatge: Decimal | None = None
    per_defecte_nou: bool | None = None
    per_defecte_segona_ma: bool | None = None
    actiu: bool | None = None


class MargeConfigOut(BaseModel):
    id: int
    nom: str
    percentatge: Decimal
    per_defecte_nou: bool
    per_defecte_segona_ma: bool
    actiu: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TramEnviamentIn(BaseModel):
    pes_maxim_g: int
    preu: Decimal
    pais: str = Field(min_length=2, max_length=2, description='Codi ISO 3166-1 alpha-2, p. ex. "ES", "FR"')
    actiu: bool = True

    @field_validator("pais")
    @classmethod
    def _pais_majuscules(cls, v: str) -> str:
        return v.strip().upper()


class TramEnviamentUpdate(BaseModel):
    pes_maxim_g: int | None = None
    preu: Decimal | None = None
    pais: str | None = Field(default=None, min_length=2, max_length=2)
    actiu: bool | None = None

    @field_validator("pais")
    @classmethod
    def _pais_majuscules(cls, v: str | None) -> str | None:
        return v.strip().upper() if v else v


class TramEnviamentOut(BaseModel):
    id: int
    pes_maxim_g: int
    preu: Decimal
    pais: str
    actiu: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PesFormatIn(BaseModel):
    formato: str
    pes_g: int


class PesFormatUpdate(BaseModel):
    pes_g: int


class PesFormatOut(BaseModel):
    id: int
    formato: str
    pes_g: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ConfiguracioBotigaOut(BaseModel):
    id: int
    nom_fiscal: str
    nif: str | None
    adreca: str
    telefon: str | None
    email_contacte: str | None
    instagram_url: str | None
    horari: str | None
    reserva_minuts: int
    subscripcions_actives: bool
    manteniment_actiu: bool
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConfiguracioBotigaUpdate(BaseModel):
    nom_fiscal: str | None = None
    nif: str | None = None
    adreca: str | None = None
    telefon: str | None = None
    email_contacte: str | None = None
    instagram_url: str | None = None
    horari: str | None = None
    reserva_minuts: int | None = None
    subscripcions_actives: bool | None = None
    manteniment_actiu: bool | None = None


class ConfiguracioBotigaPublic(BaseModel):
    """Subconjunt públic (footer): mai el NIF."""
    adreca: str
    telefon: str | None
    email_contacte: str | None
    instagram_url: str | None
    horari: str | None
    subscripcions_actives: bool
    manteniment_actiu: bool

    model_config = {"from_attributes": True}


# --- Comptabilitat: Despeses ---

CATEGORIES_DESPESA = Literal[
    "compres_material", "subministraments", "lloguer", "comunicacions",
    "serveis_professionals", "transport", "material_oficina", "publicitat", "altres"
]
ESTATS_PAGAMENT = Literal["pendent", "pagat", "vencut"]
METODES_PAGAMENT_DESPESA = Literal["transferencia", "rebut_domiciliat", "targeta", "efectiu", "paypal_altres"]


class DespesaIn(BaseModel):
    num_factura: str | None = None
    data_factura: date
    data_venciment: date | None = None
    proveidor_id: uuid.UUID | None = None
    proveidor_nom: str
    categoria: CATEGORIES_DESPESA
    concepte: str
    base_imposable: Decimal
    tipus_iva_id: int | None = None        # si s'indica, el seu percentatge mana sobre iva_pct
    iva_pct: Decimal = Decimal("21.00")
    total: Decimal | None = None           # si None, es calcula: base + base*iva_pct/100
    estat_pagament: ESTATS_PAGAMENT = "pendent"
    data_pagament: date | None = None
    metode_pagament: METODES_PAGAMENT_DESPESA | None = None
    notes: str | None = None

    @computed_field
    @property
    def iva_import(self) -> Decimal:
        return (self.base_imposable * self.iva_pct / 100).quantize(Decimal("0.01"))


class DespesaUpdate(BaseModel):
    num_factura: str | None = None
    data_factura: date | None = None
    data_venciment: date | None = None
    proveidor_id: uuid.UUID | None = None
    proveidor_nom: str | None = None
    categoria: CATEGORIES_DESPESA | None = None
    concepte: str | None = None
    base_imposable: Decimal | None = None
    tipus_iva_id: int | None = None
    iva_pct: Decimal | None = None
    iva_import: Decimal | None = None
    total: Decimal | None = None
    estat_pagament: ESTATS_PAGAMENT | None = None
    data_pagament: date | None = None
    metode_pagament: METODES_PAGAMENT_DESPESA | None = None
    notes: str | None = None


class DespesaOut(BaseModel):
    id: uuid.UUID
    num_factura: str | None
    data_factura: date
    data_venciment: date | None
    proveidor_id: uuid.UUID | None
    proveidor_nom: str
    categoria: str
    concepte: str
    base_imposable: Decimal
    tipus_iva_id: int | None
    iva_pct: Decimal
    iva_import: Decimal
    total: Decimal
    estat_pagament: str
    data_pagament: date | None
    metode_pagament: str | None
    compra_ids: list[uuid.UUID] = []
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DespesaDesDeComprasIn(BaseModel):
    """Crea una factura de proveïdor que cobreix una o més recepcions (Compra)
    encara no facturades. El total i l'IVA es calculen a partir del cost
    d'adquisició dels items de les compres seleccionades."""
    compra_ids: list[uuid.UUID] = Field(min_length=1)
    num_factura: str | None = None
    data_factura: date | None = None
    tipus_iva_id: int | None = None
    notes: str | None = None


# --- Comptabilitat: Comptes bancaris ---

class CompteBancariIn(BaseModel):
    nom: str
    iban: str | None = None
    entitat: str | None = None
    saldo_inicial: Decimal = Decimal("0")
    data_saldo_inicial: date | None = None


class CompteBancariOut(BaseModel):
    id: int
    nom: str
    iban: str | None
    entitat: str | None
    actiu: bool
    saldo_inicial: Decimal
    data_saldo_inicial: date | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Comptabilitat: Moviments bancaris ---

class MovimentBancariOut(BaseModel):
    id: uuid.UUID
    compte_id: int
    data_operacio: date
    data_valor: date | None
    concepte: str
    import_moviment: Decimal
    saldo: Decimal | None
    estat: str
    despesa_id: uuid.UUID | None
    order_id: uuid.UUID | None
    venta_externa_id: uuid.UUID | None
    notes_conciliacio: str | None
    created_at: datetime
    # Enriquit
    despesa_concepte: str | None = None
    despesa_proveidor: str | None = None

    model_config = {"from_attributes": True}


class ConciliarMovimentIn(BaseModel):
    estat: Literal["conciliat", "ignorat"]
    despesa_id: uuid.UUID | None = None
    order_id: uuid.UUID | None = None
    venta_externa_id: uuid.UUID | None = None
    notes_conciliacio: str | None = None


# --- Comptabilitat: Reports ---

class ResultatLiniaDespesa(BaseModel):
    categoria: str
    total: Decimal
    num_factures: int


class ResultatMensualOut(BaseModel):
    year: int
    mes: int
    periode_tancat: bool
    # Ingressos
    vendes_web: Decimal
    vendes_mostrador: Decimal
    vendes_discogs: Decimal
    total_ingressos: Decimal
    # Cost de les vendes (COGS — imputat al mes que es ven, no al mes de compra)
    cogs_web: Decimal
    cogs_extern: Decimal
    total_cogs: Decimal
    items_sense_cost: int        # vendes sense coste_adquisicion informat
    # Marge brut = ingressos − COGS
    marge_brut: Decimal
    # Despeses operatives (exclou compres_material, que ja van al COGS)
    despeses: list[ResultatLiniaDespesa]
    total_despeses_operatives: Decimal
    # Per compatibilitat — total de totes les despeses de la taula Despesa del mes
    total_despeses: Decimal
    # Resultat net = marge_brut − despeses_operatives
    resultat: Decimal


class IVALiniaOut(BaseModel):
    categoria: str
    base: Decimal
    iva_pct: Decimal
    iva_import: Decimal


class IVATrimestralOut(BaseModel):
    year: int
    trimestre: int           # 1-4
    mesos: list[int]         # [1,2,3] per T1, etc.
    # IVA suportat (despeses — deductible)
    iva_suportat: list[IVALiniaOut]
    total_base_suportat: Decimal
    total_iva_suportat: Decimal
    # IVA repercutit (vendes — a ingressar)
    iva_repercutit: list[IVALiniaOut]
    total_base_repercutit: Decimal
    total_iva_repercutit: Decimal
    # Resultat net
    resultat_iva: Decimal    # repercutit - suportat (+ = a pagar, - = a compensar)
    nota_rebu: bool          # True si hi ha vendes REBU que cal gestionar a part


# --- Comptabilitat: Periodes ---

class PeriodeComptableOut(BaseModel):
    id: int
    year: int
    mes: int
    tancat: bool
    data_tancament: datetime | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Comptabilitat: Caixa diària ---

CAIXA_DIARIA_CAMPS = (
    "targeta_21", "targeta_4", "efectiu_21", "efectiu_4",
    "bizum_21", "bizum_4", "paypal_21", "paypal_4",
    "transfer_21", "bono_cultural",
)


class CaixaDiariaLiniaIn(BaseModel):
    data: date
    targeta_21: Decimal = Decimal("0")
    targeta_4: Decimal = Decimal("0")
    efectiu_21: Decimal = Decimal("0")
    efectiu_4: Decimal = Decimal("0")
    bizum_21: Decimal = Decimal("0")
    bizum_4: Decimal = Decimal("0")
    paypal_21: Decimal = Decimal("0")
    paypal_4: Decimal = Decimal("0")
    transfer_21: Decimal = Decimal("0")
    bono_cultural: Decimal = Decimal("0")


class CaixaDiariaLiniaOut(CaixaDiariaLiniaIn):
    total_dia: Decimal


class CaixaDiariaMesOut(BaseModel):
    year: int
    mes: int
    periode_tancat: bool
    dies: list[CaixaDiariaLiniaOut]
    totals: CaixaDiariaLiniaOut
    total_mes: Decimal


class VendesRealsLiniaOut(BaseModel):
    """Cobraments reals reconstruïts a partir de vendes web (Redsys, sempre
    targeta) i TPV mostrador (targeta/efectiu/bizum/bono cultural, segons el
    que es va triar en cobrar) — veure GET .../caixa-diaria/{y}/{m}/vendes-reals.
    Paypal i transferència no es registren enlloc a l'app (no hi ha cap
    mètode de pagament així al checkout ni al TPV), per això no apareixen
    aquí i es continuen omplint a mà."""

    data: date
    targeta_21: Decimal = Decimal("0")
    targeta_4: Decimal = Decimal("0")
    efectiu_21: Decimal = Decimal("0")
    efectiu_4: Decimal = Decimal("0")
    bizum_21: Decimal = Decimal("0")
    bizum_4: Decimal = Decimal("0")
    bono_cultural: Decimal = Decimal("0")


# --- Subscripcions (club del disc) ---
#
# No hi ha "plans": el client configura la seva pròpia subscripció
# (periodicitat, quantitat, seccions) dins dels valors que ofereix
# `ConfiguracioSubscripcio` (un sol recurs, com `ConfiguracioBotiga`).

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
    subscripcio_pool: bool


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
