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


class HeroProps(BackgroundProps):
    eyebrow: str | None = None
    title: str = ""
    subtitle: str | None = None
    cta_label: str | None = None
    cta_href: str = "/cataleg"


class CarouselProps(BaseModel):
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


class TextProps(BackgroundProps):
    heading: str | None = None
    body: str = ""
    cta_label: str | None = None
    cta_href: str | None = None


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
}
