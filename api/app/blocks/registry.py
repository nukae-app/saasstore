"""Registre de tipus de bloc del home constructible (ver models/storefront.py
::HomeBlock) — font única de veritat de quins `block_type` existeixen i
quins `props` accepta cadascun. Afegir un bloc nou és afegir una entrada
aquí (i el seu component a web/components/store/blocks/registry.js) — no
cal tocar cap altre codi.

Regla d'or: `props` només configura copy/comportament (títol, quina
etiqueta alimenta un carrusel...), mai dades de catàleg en viu — això ho
segueix resolent [locale]/page.jsx a cada request, igual que avui."""

from pydantic import BaseModel


class BackgroundProps(BaseModel):
    """Fons personalitzable — comú a hero/text/testimonials. Si hi ha
    `background_image_url`, mana sobre `background_color` (ver components
    de bloc a web/components/store/*)."""
    background_color: str | None = None
    background_image_url: str | None = None


# Variants de disposició del bloc "hero" — ver
# web/components/store/HomeHero.jsx per al render de cadascuna i
# web/components/store/blocks/HeroPropsForm.jsx per al selector d'admin.
# String lliure (no Literal), mateix criteri que la resta de camps triats
# per preset en aquest fitxer (etiqueta_slug, icon...): l'admin només manda
# valors que ja surten d'aquest registre, mai text escrit a mà.
HERO_LAYOUTS = (
    "image_right", "image_left", "dual_featured", "mosaic",
    "background_center", "background_left", "background_video",
    "solid_color", "no_image", "logo_tagline",
)


class HeroProps(BackgroundProps):
    layout: str = "image_right"
    eyebrow: str | None = None
    title: str = ""
    subtitle: str | None = None
    cta_label: str | None = None
    cta_href: str = "/cataleg"
    # Text de la targeta flotant a image_right/image_left/dual_featured —
    # per defecte cap (el component fa servir la traducció "Ara sona"), però
    # un tenant d'un altre vertical (no discos) pot voler-lo genèric, p. ex.
    # "Producte destacat".
    featured_label: str | None = None
    # Només rellevant amb layout="background_video".
    background_video_url: str | None = None
    # Només rellevant amb layout="background_video" — als altres layouts
    # l'alineació ja ve fixada pel propi layout (image_right/image_left...).
    text_align: str = "center"


# Variants de disposició del bloc "carousel" — ver
# web/components/store/blocks/CarouselBlock.jsx per al render de cadascuna.
CAROUSEL_LAYOUTS = (
    "classic", "overlay", "featured_large", "list_rows",
    "minimal", "grid", "autoplay", "oferta",
)


class CarouselProps(BaseModel):
    layout: str = "classic"
    heading: str = ""
    subtitle: str | None = None
    cta_label: str | None = None
    # Quina etiqueta alimenta el carrusel (ver Etiqueta) — "novetat" per
    # defecte, mateix criteri que el carrusel de "New arrivals" d'avui.
    etiqueta_slug: str = "novetat"


class EmptyProps(BaseModel):
    """Blocs sense props configurables en v1 — la seva única configuració
    és si estan presents/actius a la llista de HomeBlock del tenant."""


class CuratorSelectionProps(BaseModel):
    # Quina etiqueta alimenta la selecció (mateix mecanisme que
    # CarouselProps.etiqueta_slug) — "recomanat" per defecte, el mateix
    # criteri que la secció tenia en dur abans.
    etiqueta_slug: str = "recomanat"


# Variants de disposició del bloc "text" — ver
# web/components/store/blocks/TextBlock.jsx per al render de cadascuna.
TEXT_LAYOUTS = (
    "centered", "full_width", "two_columns_image", "two_columns_video",
    "background_image", "stats", "pull_quote", "checklist",
    "cta_banner", "editorial_dropcap",
)


class TextStatItem(BaseModel):
    value: str = ""
    label: str = ""


class TextProps(BackgroundProps):
    layout: str = "centered"
    heading: str | None = None
    body: str = ""
    cta_label: str | None = None
    cta_href: str | None = None
    # Només rellevant amb layout="two_columns_video".
    video_url: str | None = None
    # Només rellevant amb layout="stats" — 3 xifres destacades.
    stats: list[TextStatItem] = []


class TestimonialItem(BaseModel):
    quote: str = ""
    author: str = ""


class TestimonialsProps(BackgroundProps):
    heading: str | None = None
    items: list[TestimonialItem] = []


class GalleryItem(BaseModel):
    image_url: str = ""
    caption: str | None = None
    href: str | None = None


class GalleryProps(BaseModel):
    heading: str | None = None
    items: list[GalleryItem] = []


class FaqItem(BaseModel):
    question: str = ""
    answer: str = ""


class FaqProps(BaseModel):
    heading: str | None = None
    items: list[FaqItem] = []


class BannerProps(BackgroundProps):
    text: str = ""
    cta_label: str | None = None
    cta_href: str | None = None


class BrandItem(BaseModel):
    image_url: str = ""
    href: str | None = None


class BrandStripProps(BaseModel):
    heading: str | None = None
    items: list[BrandItem] = []


# Icones disponibles per al bloc "feature_grid" — subconjunt curat de
# lucide-react (ver web/components/store/blocks/FeatureGridBlock.jsx per al
# mapa icona->component). Llista tancada perquè l'admin tria d'una paleta
# coherent, no escriu el nom d'una icona a mà.
FEATURE_GRID_ICONS = (
    "music", "disc", "truck", "gift", "tag", "percent",
    "map-pin", "phone", "mail", "heart", "star", "sparkles",
)


class FeatureGridItem(BaseModel):
    icon: str = "music"
    label: str = ""
    href: str | None = None


class FeatureGridProps(BaseModel):
    heading: str | None = None
    items: list[FeatureGridItem] = []


class VideoProps(BaseModel):
    heading: str | None = None
    subtitle: str | None = None
    # URL normal de YouTube/Vimeo (no cal que sigui ja d'embed) — ver
    # web/components/store/blocks/videoEmbedUrl.js per a la conversió.
    video_url: str = ""


BLOCK_REGISTRY: dict[str, type[BaseModel]] = {
    "hero": HeroProps,
    "carousel": CarouselProps,
    "curator_selection": CuratorSelectionProps,
    "genre_grid": EmptyProps,
    "spotify_recommendations": EmptyProps,
    "about_strip": EmptyProps,
    "text": TextProps,
    "testimonials": TestimonialsProps,
    "gallery": GalleryProps,
    "faq": FaqProps,
    "banner": BannerProps,
    "brand_strip": BrandStripProps,
    "feature_grid": FeatureGridProps,
    "video": VideoProps,
}
