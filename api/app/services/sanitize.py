"""Sanitización del HTML del blog/CMS (`post.content`, `pagina.content`)
antes de guardarlo. Defensa en profundidad: hoy solo el admin escribe aquí
(`admin.py`, protegido por `require_admin`), pero si esa cuenta se viera
comprometida esto evita servir contenido inyectado en páginas públicas
indexadas."""

from urllib.parse import urlparse

import bleach
from bleach.css_sanitizer import CSSSanitizer

_ALLOWED_TAGS = [
    "p", "br", "div", "span", "b", "strong", "i", "em", "u",
    "h1", "h2", "h3", "h4", "ul", "ol", "li", "a", "img", "blockquote", "iframe",
]

# Mismos dominios de embed que reconoce el front (ver `hasAudio()` en
# web/app/[locale]/[pagina]/page.jsx).
_IFRAME_DOMAINS = (
    "mixcloud.com", "bandcamp.com", "soundcloud.com",
    "open.spotify.com", "youtube.com", "youtube-nocookie.com",
)


def _link_attrs(tag: str, name: str, value: str) -> bool:
    return name in {"href", "target", "rel"}


def _img_attrs(tag: str, name: str, value: str) -> bool:
    return name in {"src", "alt", "style"}


def _iframe_attrs(tag: str, name: str, value: str) -> bool:
    if name == "src":
        parsed = urlparse(value)
        host = parsed.netloc
        return parsed.scheme == "https" and any(host == d or host.endswith(f".{d}") for d in _IFRAME_DOMAINS)
    return name in {"width", "height", "frameborder", "allow", "allowfullscreen"}


# Solo las propiedades que el propio editor (RichTextEditor.jsx) inserta al
# subir una imagen (`max-width:100%;height:auto;display:block;`). bleach solo
# conserva declaraciones `style` si se le da un CSSSanitizer explícito.
_css_sanitizer = CSSSanitizer(allowed_css_properties=["max-width", "width", "height", "display", "text-align"])

_cleaner = bleach.sanitizer.Cleaner(
    tags=_ALLOWED_TAGS,
    attributes={"a": _link_attrs, "img": _img_attrs, "iframe": _iframe_attrs},
    protocols=["http", "https", "mailto"],
    css_sanitizer=_css_sanitizer,
    strip=True,
)


def sanitize_rich_html(html: str | None) -> str | None:
    if not html:
        return html
    return _cleaner.clean(html)
