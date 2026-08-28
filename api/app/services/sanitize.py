"""Sanitización del HTML del blog/CMS (`post.content`, `pagina.content`)
antes de guardarlo. Defensa en profundidad: hoy solo el admin escribe aquí
(`admin.py`, protegido por `require_admin`), pero si esa cuenta se viera
comprometida esto evita servir contenido inyectado en páginas públicas
indexadas."""

from urllib.parse import urlparse

import bleach
import tinycss2
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


# CSS propio del tenant (ConfiguracioBotiga.custom_css, ver
# routers/configuracio.py) — inyectado tal cual en un <style> en
# web/app/layout.jsx. Lo escribe el admin del propio tenant sobre su propia
# tienda (mismo nivel de confianza que subir su logo), así que el riesgo no
# es "un desconocido inyecta HTML" sino "una cuenta de admin comprometida
# usa este campo para algo más que retocar colores". Dos capas:
MAX_CUSTOM_CSS_BYTES = 32_000


def sanitize_custom_css(css: str | None) -> str | None:
    if not css:
        return css
    if len(css.encode()) > MAX_CUSTOM_CSS_BYTES:
        raise ValueError("El CSS és massa gran (màxim 32 KB)")
    # <style> és un "raw text element" HTML: el navegador el parseja de
    # forma literal fins que veu el tancament, i React no escapa el
    # contingut d'un dangerouslySetInnerHTML dins d'un <style> (no pot,
    # trencaria CSS vàlid). Un "</style>" literal dins d'aquest text seria
    # una fuga real de l'etiqueta cap a HTML/script arbitrari — aquesta
    # comprovació és la que protegeix de veritat, independent del que
    # detecti el parser de CSS de sota.
    if "</style" in css.lower():
        raise ValueError("El CSS conté una seqüència no permesa")
    rules = tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True)
    for rule in rules:
        if rule.type == "at-rule":
            # @import/@media/@font-face... tots fora en v1 — més senzill
            # que intentar validar quins @media són "segurs" ara mateix;
            # s'afegeix suport concret si algun tenant el demana de debò.
            raise ValueError(f"La regla '@{rule.lower_at_keyword}' no està permesa en aquest camp")
        if rule.type == "error":
            raise ValueError("El CSS no és vàlid")
    return css
