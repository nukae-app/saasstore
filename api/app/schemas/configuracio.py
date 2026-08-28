import re
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
    catalog_browse_mode: bool
    catalog_format_filter: bool
    catalog_genre_filter: bool
    favicon_url: str | None
    logo_url: str | None
    theme: dict
    custom_css: str | None
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
    catalog_browse_mode: bool | None = None
    catalog_format_filter: bool | None = None
    catalog_genre_filter: bool | None = None
    maintenance_active: bool | None = None
    discogs_habilitat: bool | None = None


HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
THEME_COLOR_FIELDS = (
    "background", "foreground", "primary", "primary_foreground",
    "secondary", "secondary_foreground", "accent", "accent_foreground",
    "muted", "muted_foreground", "border",
)
THEME_FONT_FIELDS = ("font_headline", "font_body")


class ThemeTokens(BaseModel):
    """Body del PATCH de tema — claus 1:1 amb les variables CSS de
    web/app/globals.css (injecció = bucle tonto al front, sense taula de
    mapeig). Un dict obert de noms de variable arbitraris NO s'accepta a
    propòsit: reobriria la porta d'injecció CSS lliure que es reserva a
    `custom_css`, sanejat a part.

    Sense @field_validator/Field(pattern=...) a propòsit: un error de
    validació de Pydantic torna `detail` com a llista d'objectes, no
    l'string simple que espera el frontend — es valida a mà a
    update_theme(), mateix criteri que ja es va aplicar a
    superadmin.py::create_tenant() per al mateix motiu."""
    background: str | None = None
    foreground: str | None = None
    primary: str | None = None
    primary_foreground: str | None = None
    secondary: str | None = None
    secondary_foreground: str | None = None
    accent: str | None = None
    accent_foreground: str | None = None
    muted: str | None = None
    muted_foreground: str | None = None
    border: str | None = None
    font_headline: str | None = Field(default=None, max_length=200)
    font_body: str | None = Field(default=None, max_length=200)
    # Aparença: valors CSS ja resolts (no enums), mateix criteri que la resta
    # d'aquest esquema — la UI només ofereix uns quants preajustos, però el
    # backend els accepta com a text lliure curt. Cada component del
    # storefront que els fa servir declara el seu propi valor de fallback
    # CSS (var(--radius-card, 24px)), així que mentre aquest camp és buit
    # (tots els tenants existents avui) l'aspecte no canvia gens.
    radius_card: str | None = Field(default=None, max_length=50)
    radius_button: str | None = Field(default=None, max_length=50)
    shadow_card: str | None = Field(default=None, max_length=200)
    border_card: str | None = Field(default=None, max_length=100)
    content_width: str | None = Field(default=None, max_length=50)


class CustomCssUpdateIn(BaseModel):
    custom_css: str | None = None


class FontSearchOut(BaseModel):
    id: str
    family: str
    category: str
    variable: bool


class FontSelectIn(BaseModel):
    font_id: str


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
    catalog_browse_mode: bool
    catalog_format_filter: bool
    catalog_genre_filter: bool
    favicon_url: str | None
    logo_url: str | None
    theme: dict
    custom_css: str | None
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
