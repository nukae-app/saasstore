"""Blog, agenda i pàgines CMS — endpoints públics."""

import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import extract, func, select, text
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Event, Pagina, Post, PostPagina
from ..schemas import EventOut

router = APIRouter(tags=["blog"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_IMG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
_TEXT_RE = re.compile(r'<[^>]+>')


def _extract_thumbnail(html: str) -> str | None:
    m = _IMG_RE.search(html)
    if not m:
        return None
    url = m.group(1)
    url = re.sub(r'/s\d+(-c)?/', '/s800/', url)
    return url


def _excerpt(html: str, max_chars: int = 160) -> str:
    text_content = _TEXT_RE.sub(' ', html).replace('\xa0', ' ')
    text_content = re.sub(r'\s+', ' ', text_content).strip()
    if len(text_content) <= max_chars:
        return text_content
    return text_content[:max_chars].rsplit(' ', 1)[0] + '…'


def _post_out(post: Post) -> dict:
    return {
        "slug": post.slug,
        "titulo": post.titulo,
        "contenido": post.contenido,
        "idioma": post.idioma,
        "publicado_at": post.publicado_at.isoformat() if post.publicado_at else None,
        "thumbnail_url": _extract_thumbnail(post.contenido),
        "excerpt": _excerpt(post.contenido),
        "legacy_blogger_url": post.legacy_blogger_url,
        "pagines": [{"id": p.id, "slug": p.slug, "nom": p.nom} for p in post.pagines],
    }


# ---------------------------------------------------------------------------
# Pàgines CMS (públic)
# ---------------------------------------------------------------------------

@router.get("/pagines")
def list_pagines(db: Session = Depends(get_db)):
    """Llista de pàgines visibles al menú, ordenades per posició."""
    return [
        {
            "id": p.id,
            "slug": p.slug,
            "nom": p.nom,
            "tipus": p.tipus,
            "posicio": p.posicio,
        }
        for p in db.scalars(
            select(Pagina)
            .where(Pagina.visible_menu == True)
            .order_by(Pagina.posicio)
        ).all()
    ]


@router.get("/pagines/{slug}")
def get_pagina(slug: str, db: Session = Depends(get_db)):
    """Retorna la info d'una pàgina (per renderitzar el seu contingut)."""
    pagina = db.scalar(select(Pagina).where(Pagina.slug == slug))
    if pagina is None:
        raise HTTPException(404, "Pàgina no trobada")
    return {
        "id": pagina.id,
        "slug": pagina.slug,
        "nom": pagina.nom,
        "tipus": pagina.tipus,
        "contingut": pagina.contingut,
    }


# ---------------------------------------------------------------------------
# Posts
# ---------------------------------------------------------------------------

@router.get("/posts")
def list_posts(
    db: Session = Depends(get_db),
    page: int = 1,
    page_size: int = 6,
    year: int | None = None,
    month: int | None = None,
    pagina: str | None = None,  # slug de la pàgina per filtrar
):
    stmt = (
        select(Post)
        .where(Post.publicado_at.is_not(None))
    )
    if pagina:
        pg = db.scalar(select(Pagina).where(Pagina.slug == pagina))
        if pg:
            stmt = stmt.join(PostPagina, PostPagina.post_id == Post.id).where(
                PostPagina.pagina_id == pg.id
            )
        else:
            return []
    if year:
        stmt = stmt.where(extract("year", Post.publicado_at) == year)
    if month:
        stmt = stmt.where(extract("month", Post.publicado_at) == month)
    stmt = stmt.order_by(Post.publicado_at.desc()).offset((page - 1) * page_size).limit(page_size)
    return [_post_out(p) for p in db.scalars(stmt).all()]


@router.get("/posts/archive")
def posts_archive(
    db: Session = Depends(get_db),
    pagina: str | None = None,
):
    """Recompte de posts per any i mes, opcionalment filtrat per pàgina."""
    stmt = (
        select(
            extract("year", Post.publicado_at).label("year"),
            extract("month", Post.publicado_at).label("month"),
            func.count(Post.slug).label("count"),
        )
        .where(Post.publicado_at.is_not(None))
    )
    if pagina:
        pg = db.scalar(select(Pagina).where(Pagina.slug == pagina))
        if pg:
            stmt = stmt.join(PostPagina, PostPagina.post_id == Post.id).where(
                PostPagina.pagina_id == pg.id
            )
    stmt = (
        stmt
        .group_by(text("year"), text("month"))
        .order_by(text("year desc"), text("month desc"))
    )
    rows = db.execute(stmt).all()

    MESOS_CA = ["", "Gener", "Febrer", "Març", "Abril", "Maig", "Juny",
                "Juliol", "Agost", "Setembre", "Octubre", "Novembre", "Desembre"]
    return [
        {
            "year": int(r.year),
            "month": int(r.month),
            "count": r.count,
            "label": f"{MESOS_CA[int(r.month)]} {int(r.year)}",
        }
        for r in rows
    ]


@router.get("/posts/{slug}")
def get_post(slug: str, db: Session = Depends(get_db)):
    post = db.scalar(select(Post).where(Post.slug == slug))
    if post is None or post.publicado_at is None:
        raise HTTPException(404, "Post no trobat")
    return _post_out(post)


# ---------------------------------------------------------------------------
# Agenda
# ---------------------------------------------------------------------------

@router.get("/events", response_model=list[EventOut])
def list_events(db: Session = Depends(get_db)):
    return db.scalars(
        select(Event)
        .where(Event.fecha >= datetime.now(timezone.utc))
        .order_by(Event.fecha)
    ).all()
