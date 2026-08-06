"""Importa posts de Blogger a la taula `posts`.

Pot llegir directament del blog públic (sense baixar res) o d'un fitxer XML exportat.

Ús:
    # Importar directament des del blog (recomanat, sense baixar cap fitxer)
    docker compose exec api python -m scripts.import_blogger --from-blog https://ultralocalrecords.blogspot.com/

    # Prova en sec primer (no guarda res)
    docker compose exec api python -m scripts.import_blogger --from-blog https://ultralocalrecords.blogspot.com/ --dry-run

    # Des d'un fitxer XML exportat manualment
    docker cp blog-export.xml rcordshop-api-1:/tmp/blog.xml
    docker compose exec api python -m scripts.import_blogger /tmp/blog.xml

    # Reimportar sobreescrivint posts existents (per netejar contingut)
    docker compose exec api python -m scripts.import_blogger --from-blog https://ultralocalrecords.blogspot.com/ --overwrite

Idempotent per `legacy_blogger_url`: si el post ja existeix, es salta (o actualitza amb --overwrite).
"""

import argparse
import re
import sys
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET

import httpx

from app.database import SessionLocal
from app.models import Post
from sqlalchemy import select

# Namespaces de l'Atom feed de Blogger
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "gd":   "http://schemas.google.com/g/2005",
}

KIND_POST    = "http://schemas.google.com/blogger/2008/kind#post"
KIND_COMMENT = "http://schemas.google.com/blogger/2008/kind#comment"


# ---------------------------------------------------------------------------
# Helpers de parsing
# ---------------------------------------------------------------------------

def _kind(entry: ET.Element) -> str | None:
    for cat in entry.findall("atom:category", NS):
        scheme = cat.get("scheme", "")
        if "kind" in scheme:
            return cat.get("term", "")
    return None


def _alternate_url(entry: ET.Element) -> str | None:
    for link in entry.findall("atom:link", NS):
        if link.get("rel") == "alternate" and link.get("type") == "text/html":
            return link.get("href")
    return None


def _slug_from_url(url: str) -> str:
    """Extreu el slug de la URL de Blogger.

    https://blog.blogspot.com/2023/04/el-meu-post.html → 2023-04-el-meu-post
    """
    m = re.search(r"/(\d{4})/(\d{2})/([^/]+?)(?:\.html)?$", url)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # Fallback: últim segment sense extensió
    part = url.rstrip("/").split("/")[-1]
    return re.sub(r"\.html?$", "", part) or "post"


def _parse_date(iso: str) -> datetime:
    """Parseja la data ISO 8601 de Blogger (pot portar offset de zona horària)."""
    iso = iso.strip()
    # Python 3.11+ suporta fromisoformat amb offsets; per <3.11, normalizem
    iso = re.sub(r"(\+\d{2}):(\d{2})$", r"+\1\2", iso)  # +02:00 → +0200
    try:
        dt = datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Neteja de contingut HTML
# ---------------------------------------------------------------------------

def clean_html(html: str) -> str:
    """Neteja mínima del contingut HTML de Blogger."""

    # Blogger afegeix divs wrapper amb dir="ltr" o style="text-align:..."
    # Els deixem però eliminem estils inline de font-size i font-family
    html = re.sub(r'\s*style="[^"]*font-(?:size|family)[^"]*"', "", html)

    # Imatges de Blogger: s1600 → bona qualitat, però sovint porten width/height fixes
    # Eliminamos atributs width/height de les imatges (el CSS s'en farà càrrec)
    html = re.sub(r'\s+(?:width|height)="\d+"', "", html)

    # Blogger usa "imageanchor" wrappers — els deixem (no fan mal)

    # Google Sheets / Forms embeds (ja no funcionen en la majoria de casos)
    # Els substituïm per un comentari informatiu
    html = re.sub(
        r'<iframe[^>]+src="https?://docs\.google\.com/[^"]*"[^>]*>.*?</iframe>',
        "<!-- [embed Google Docs eliminat en la migració] -->",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # Blogspot scripts antics
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)

    # Espais en blanc excessius al final
    html = html.strip()

    return html


def _detect_embeds(html: str) -> set[str]:
    """Detecta quins tipus d'embeds conté el post (per estadístiques)."""
    embeds = set()
    checks = {
        "mixcloud":  r"mixcloud\.com",
        "bandcamp":  r"bandcamp\.com",
        "youtube":   r"youtube\.com/embed|youtu\.be",
        "soundcloud": r"soundcloud\.com",
        "spotify":   r"open\.spotify\.com",
        "google_docs": r"docs\.google\.com",
        "discogs":   r"discogs\.com",
    }
    for name, pattern in checks.items():
        if re.search(pattern, html, re.IGNORECASE):
            embeds.add(name)
    return embeds


# ---------------------------------------------------------------------------
# Fetch del feed Atom de Blogger (paginat)
# ---------------------------------------------------------------------------

FEED_BASE = "feeds/posts/default"
USER_AGENT = "UltraLocalRecords/1.0 (blog import)"


def _feed_url(blog_url: str, start: int = 1, max_results: int = 500) -> str:
    base = blog_url.rstrip("/")
    return f"{base}/{FEED_BASE}?alt=atom&max-results={max_results}&start-index={start}"


def fetch_all_entries(blog_url: str) -> list[ET.Element]:
    """Descarrega totes les pàgines del feed Atom i retorna les entrades."""
    all_entries: list[ET.Element] = []
    url = _feed_url(blog_url, start=1, max_results=500)

    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True) as client:
        page = 0
        while url:
            page += 1
            print(f"  Descarregant pàgina {page}: {url}")
            try:
                r = client.get(url)
                r.raise_for_status()
            except httpx.HTTPError as e:
                print(f"Error baixant el feed: {e}", file=sys.stderr)
                sys.exit(1)

            try:
                root = ET.fromstring(r.content)
            except ET.ParseError as e:
                print(f"Error parsejant XML: {e}", file=sys.stderr)
                sys.exit(1)

            entries = root.findall("atom:entry", NS)
            all_entries.extend(entries)
            print(f"  → {len(entries)} entrades (total: {len(all_entries)})")

            # Buscar link 'next' per paginar
            url = None
            for link in root.findall("atom:link", NS):
                if link.get("rel") == "next":
                    url = link.get("href")
                    time.sleep(0.5)  # cortesia amb els servidors de Google
                    break

    return all_entries


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("xml_file", nargs="?", help="Ruta al fitxer XML exportat de Blogger")
    group.add_argument("--from-blog", metavar="URL",
                       help="URL del blog de Blogger (importa directament sense baixar cap fitxer)")
    parser.add_argument("--dry-run", action="store_true", help="No guarda res a la BD")
    parser.add_argument("--overwrite", action="store_true", help="Actualitza posts que ja existeixen")
    parser.add_argument("--idioma", default="ca", help="Idioma dels posts (per defecte: ca)")
    args = parser.parse_args()

    if args.from_blog:
        print(f"Connectant al blog: {args.from_blog}")
        all_entries = fetch_all_entries(args.from_blog)
        root = None  # no fem servir tree.getroot()
    else:
        xml_path = Path(args.xml_file)
        if not xml_path.exists():
            print(f"Error: fitxer no trobat: {xml_path}", file=sys.stderr)
            sys.exit(1)
        print(f"Llegint {xml_path} …")
        try:
            tree = ET.parse(xml_path)
        except ET.ParseError as e:
            print(f"Error parsejant XML: {e}", file=sys.stderr)
            sys.exit(1)
        root = tree.getroot()
        all_entries = root.findall("atom:entry", NS)

    print(f"Total d'entrades trobades: {len(all_entries)}")

    # Filtrar posts publicats.
    # - En l'XML exportat: les entrades tenen <category scheme="...kind..."> que les
    #   classifica com a post/comment/template. Només volem KIND_POST.
    # - En el feed live /feeds/posts/default: totes les entrades SÓN posts (el feed
    #   ja filtra per tipus), però no porten la category kind. Si _kind() retorna None
    #   tractarem l'entrada com a post igualment.
    posts_entries = []
    for entry in all_entries:
        k = _kind(entry)
        if k is not None and k != KIND_POST:
            continue  # és un comentari, template, o configuració → saltar
        url = _alternate_url(entry)
        if url:  # sense URL alternate = esborrany → saltar
            posts_entries.append((entry, url))

    print(f"Posts publicats trobats: {len(posts_entries)}")
    if not posts_entries:
        print("Res a importar.")
        return

    db = SessionLocal()

    stats = {"importats": 0, "actualitzats": 0, "saltats": 0, "errors": 0}
    embed_counts: dict[str, int] = {}
    slug_conflicts: list[str] = []

    for entry, blogger_url in posts_entries:
        title_el = entry.find("atom:title", NS)
        content_el = entry.find("atom:content", NS)
        published_el = entry.find("atom:published", NS)

        title = title_el.text.strip() if title_el is not None and title_el.text else "(sense títol)"
        content_raw = content_el.text or "" if content_el is not None else ""
        published_str = published_el.text or "" if published_el is not None else ""

        published_at = _parse_date(published_str) if published_str else None
        content = clean_html(content_raw)
        slug = _slug_from_url(blogger_url)

        # Estadístiques d'embeds
        for embed_type in _detect_embeds(content_raw):
            embed_counts[embed_type] = embed_counts.get(embed_type, 0) + 1

        # Comprovar si ja existeix (per blogger_url o per slug)
        existing_by_url  = db.scalar(select(Post).where(Post.legacy_blogger_url == blogger_url))
        existing_by_slug = db.scalar(select(Post).where(Post.slug == slug))

        if existing_by_url:
            if args.overwrite:
                existing_by_url.titulo = title
                existing_by_url.contenido = content
                existing_by_url.publicado_at = published_at
                existing_by_url.slug = slug
                if not args.dry_run:
                    db.commit()
                stats["actualitzats"] += 1
                print(f"  ↺ {slug}")
            else:
                stats["saltats"] += 1
            continue

        if existing_by_slug:
            # Conflicte de slug: afegim un sufix numèric
            base_slug = slug
            n = 2
            while db.scalar(select(Post).where(Post.slug == f"{base_slug}-{n}")):
                n += 1
            slug = f"{base_slug}-{n}"
            slug_conflicts.append(blogger_url)

        post = Post(
            slug=slug,
            titulo=title,
            contenido=content,
            idioma=args.idioma,
            publicado_at=published_at,
            legacy_blogger_url=blogger_url,
        )
        if not args.dry_run:
            db.add(post)
            if stats["importats"] % 50 == 0:
                db.commit()

        stats["importats"] += 1
        print(f"  + {slug}")

    if not args.dry_run:
        db.commit()
    db.close()

    # Resum
    print()
    print("=" * 60)
    mode = "DRY-RUN — " if args.dry_run else ""
    print(f"{mode}Resultat:")
    print(f"  Importats:    {stats['importats']}")
    print(f"  Actualitzats: {stats['actualitzats']}")
    print(f"  Saltats:      {stats['saltats']}")
    print(f"  Errors:       {stats['errors']}")

    if embed_counts:
        print()
        print("Embeds detectats al contingut:")
        for k, v in sorted(embed_counts.items(), key=lambda x: -x[1]):
            print(f"  {k:20s} {v} posts")

    if slug_conflicts:
        print()
        print(f"Conflicts de slug resolts ({len(slug_conflicts)}):")
        for url in slug_conflicts[:10]:
            print(f"  {url}")
        if len(slug_conflicts) > 10:
            print(f"  … i {len(slug_conflicts) - 10} més")


if __name__ == "__main__":
    main()
