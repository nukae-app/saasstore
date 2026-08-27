from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class MargeConfigIn(BaseModel):
    name: str
    percentage: Decimal
    default_new: bool = False
    default_used: bool = False
    active: bool = True


class MargeConfigUpdate(BaseModel):
    name: str | None = None
    percentage: Decimal | None = None
    default_new: bool | None = None
    default_used: bool | None = None
    active: bool | None = None


class MargeConfigOut(BaseModel):
    id: int
    name: str
    percentage: Decimal
    default_new: bool
    default_used: bool
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TramEnviamentIn(BaseModel):
    max_weight_g: int
    price: Decimal
    country: str = Field(min_length=2, max_length=2, description='Codi ISO 3166-1 alpha-2, p. ex. "ES", "FR"')
    active: bool = True

    @field_validator("country")
    @classmethod
    def _pais_majuscules(cls, v: str) -> str:
        return v.strip().upper()


class TramEnviamentUpdate(BaseModel):
    max_weight_g: int | None = None
    price: Decimal | None = None
    country: str | None = Field(default=None, min_length=2, max_length=2)
    active: bool | None = None

    @field_validator("country")
    @classmethod
    def _pais_majuscules(cls, v: str | None) -> str | None:
        return v.strip().upper() if v else v


class TramEnviamentOut(BaseModel):
    id: int
    max_weight_g: int
    price: Decimal
    country: str
    active: bool
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
    fiscal_name: str
    nif: str | None
    address: str
    phone: str | None
    contact_email: str | None
    instagram_url: str | None
    hours: str | None
    reservation_minutes: int
    email_from: str | None
    subscripcions_actives: bool
    maintenance_active: bool
    discogs_habilitat: bool
    favicon_url: str | None
    logo_url: str | None
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConfiguracioBotigaUpdate(BaseModel):
    fiscal_name: str | None = None
    nif: str | None = None
    address: str | None = None
    phone: str | None = None
    contact_email: str | None = None
    email_from: str | None = None
    instagram_url: str | None = None
    hours: str | None = None
    reservation_minutes: int | None = None
    subscripcions_actives: bool | None = None
    maintenance_active: bool | None = None
    discogs_habilitat: bool | None = None


class ConfiguracioBotigaPublic(BaseModel):
    """Subconjunt públic (footer): mai el NIF ni email_from (operatiu, no de cara al client)."""
    address: str
    phone: str | None
    contact_email: str | None
    instagram_url: str | None
    hours: str | None
    subscripcions_actives: bool
    maintenance_active: bool
    discogs_habilitat: bool
    favicon_url: str | None
    logo_url: str | None
    # `vertical`/`nombre` no viven en ConfiguracioBotiga (son de Tenant) —
    # se mezclan a mano en routers/configuracio.py::get_configuracio_publica,
    # no hay columna equivalente en este modelo. `nombre` es el nombre
    # comercial (distinto de `nom_fiscal`, que no es público — ver el alta
    # de tenant en superadmin, ya separa ambos conceptos).
    vertical: str
    nombre: str
    slug: str

    model_config = {"from_attributes": True}


# --- Comptabilitat: Despeses ---


class TenantSecretsStatusOut(BaseModel):
    """Nunca se devuelven los valores en sí — solo si están configurados o no."""
    redsys_merchant_code: bool
    redsys_terminal: bool
    redsys_secret_key: bool
    discogs_token: bool
    spotify_client_id: bool
    spotify_client_secret: bool


class TenantSecretsUpdateIn(BaseModel):
    redsys_merchant_code: str | None = None
    redsys_terminal: str | None = None
    redsys_secret_key: str | None = None
    discogs_token: str | None = None
    spotify_client_id: str | None = None
    spotify_client_secret: str | None = None
