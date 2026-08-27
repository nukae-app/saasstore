import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class PeticionClienteAdminOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_nombre: str | None
    user_email: str
    channel: str
    release_id: uuid.UUID | None
    artista: str | None
    titulo: str | None
    status: str
    estimated_price: Decimal | None
    chosen_delivery_method: str | None
    client_notes: str | None
    admin_notes: str | None
    solicitud_compra_linea_id: uuid.UUID | None
    order_id: uuid.UUID | None = None
    pagada: bool = False
    created_at: datetime


class PeticionCatalogarIn(BaseModel):
    release_id: uuid.UUID


class PeticionPrecioIn(BaseModel):
    estimated_price: Decimal


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
    free_artist: str | None = None
    free_title: str | None = None
    client_notes: str | None = None

    @model_validator(mode="after")
    def check_disco(self) -> "PeticionTiendaIn":
        if not self.release_id and not (self.free_artist and self.free_title):
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
