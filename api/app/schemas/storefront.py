import re
from datetime import datetime

from pydantic import BaseModel, field_validator

from ..blocks.registry import BLOCK_REGISTRY

# Rutas literales ya existentes bajo web/app/[locale]/ (auth, blog, carret,
# checkout, compte, disc, login, subscripcio) — un `Page.slug` que coincida
# rompería esas páginas Core. Mantener sincronizado a mano cada vez que se
# añada una ruta nueva bajo [locale]/ (ver docs/ARQUITECTURA_DISENY_FIGMA.md
# §6, riesgo ya anotado allí).
#
# "cataleg" y "home" NO están aquí a propósito, a diferencia de las demás:
# esas dos rutas comprueban primero si existe una `Page` publicada con ese
# slug exacto antes de usar su implementación hardcoded (mismo patrón de
# coexistencia que `[slug]/page.jsx` ya usa con `Pagina`, §3e) — ver
# [locale]/page.jsx y [locale]/cataleg/page.jsx. "disc" sigue reservado: la
# ficha de producto (`/disc/[id]`) es una plantilla por item, no una página
# única, y todavía no tiene ese mecanismo (ver bitácora, "fuera de fases").
RESERVED_PAGE_SLUGS = {
    "auth", "blog", "carret", "checkout", "compte", "disc", "login", "preview-pagina", "subscripcio",
}

# Tipus de node "vius" que no exposen props de comportament (§3d, ARQUITECTURA_
# DISENY_FIGMA.md) — l'editor de Fase 2 els farà no esborrables; aquí només
# defineixen el vocabulari vàlid per a `Page.requires_nodes`, perquè aquest
# camp no accepti qualsevol string arbitrari (mateix criteri que
# `RESERVED_PAGE_SLUGS`/`BLOCK_REGISTRY`: el vocabulari viu en codi).
PROTECTED_NODE_TYPES = {"checkout_form", "cart_summary", "payment_widget"}

_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _valid_requires_nodes(v: list[str]) -> list[str]:
    desconeguts = sorted(set(v) - PROTECTED_NODE_TYPES)
    if desconeguts:
        raise ValueError(f"Tipus de node protegit desconegut: {', '.join(desconeguts)}")
    return v


class PageOut(BaseModel):
    id: int
    slug: str
    draft_tree: dict
    published_tree: dict | None
    seo_title: dict
    seo_description: dict
    requires_nodes: list[str]
    updated_at: datetime

    model_config = {"from_attributes": True}


class PagePublicOut(BaseModel):
    """Lectura pública (/config/public/pages/{slug}) — nunca `draft_tree`,
    solo lo publicado, mismo criterio que `HomeBlockPublicOut`."""
    slug: str
    published_tree: dict
    seo_title: dict
    seo_description: dict

    model_config = {"from_attributes": True}


class PageCreateIn(BaseModel):
    slug: str
    seo_title: dict = {}
    seo_description: dict = {}
    requires_nodes: list[str] = []

    @field_validator("slug")
    @classmethod
    def _valid_slug(cls, v: str) -> str:
        v = v.strip().lower()
        if not _SLUG_RE.match(v):
            raise ValueError(
                "El slug només pot tenir minúscules, números i guions, sense començar/acabar en guió"
            )
        if v in RESERVED_PAGE_SLUGS:
            raise ValueError(f"'{v}' és una ruta reservada — tria un altre nom")
        return v

    @field_validator("requires_nodes")
    @classmethod
    def _valid_requires_nodes(cls, v: list[str]) -> list[str]:
        return _valid_requires_nodes(v)


class PageUpdateIn(BaseModel):
    # `slug` no és editable en v1 a propòsit: canviar la URL d'una pàgina ja
    # publicada implica decidir redireccions, que no s'ha demanat encara.
    draft_tree: dict | None = None
    seo_title: dict | None = None
    seo_description: dict | None = None
    requires_nodes: list[str] | None = None

    @field_validator("requires_nodes")
    @classmethod
    def _valid_requires_nodes(cls, v: list[str] | None) -> list[str] | None:
        return v if v is None else _valid_requires_nodes(v)


class HomeBlockOut(BaseModel):
    id: int
    block_type: str
    position: int
    enabled: bool
    props: dict
    updated_at: datetime

    model_config = {"from_attributes": True}


class HomeBlockPublicOut(BaseModel):
    """Lectura pública (/config/public/home-blocks) — sin id/updated_at,
    solo lo que [locale]/page.jsx necesita para renderizar."""
    id: int
    block_type: str
    props: dict

    model_config = {"from_attributes": True}


class HomeBlockCreateIn(BaseModel):
    block_type: str
    props: dict = {}

    @field_validator("block_type")
    @classmethod
    def _known_block_type(cls, v: str) -> str:
        if v not in BLOCK_REGISTRY:
            # ValueError de Pydantic aquí es aceptable (a diferencia del
            # slug de tenant/tema): esto no es un formulario de admin con
            # texto libre, el frontend solo manda valores que ya salen del
            # propio registro, nunca tecleados a mano.
            raise ValueError(f"Tipus de bloc desconegut: '{v}'")
        return v


class HomeBlockUpdateIn(BaseModel):
    props: dict | None = None
    enabled: bool | None = None


class HomeBlockPositionIn(BaseModel):
    id: int
    position: int


class HomeBlockReorderIn(BaseModel):
    order: list[HomeBlockPositionIn]


class UploadedVideoOut(BaseModel):
    id: int
    url: str
    filename: str
    size_bytes: int
    created_at: datetime

    model_config = {"from_attributes": True}
