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
        "title": post.title,
        "content": post.content,
        "language": post.language,
        "published_at": post.published_at.isoformat() if post.published_at else None,
        "thumbnail_url": _extract_thumbnail(post.content),
        "excerpt": _excerpt(post.content),
        "legacy_blogger_url": post.legacy_blogger_url,
        "pagines": [{"id": p.id, "slug": p.slug, "name": p.name} for p in post.pagines],
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
            "name": p.name,
            "type": p.type,
            "position": p.position,
        }
        for p in db.scalars(
            select(Pagina)
            .where(Pagina.menu_visible == True)
            .order_by(Pagina.position)
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
        "name": pagina.name,
        "type": pagina.type,
        "content": pagina.content,
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
        .where(Post.published_at.is_not(None))
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
        stmt = stmt.where(extract("year", Post.published_at) == year)
    if month:
        stmt = stmt.where(extract("month", Post.published_at) == month)
    stmt = stmt.order_by(Post.published_at.desc()).offset((page - 1) * page_size).limit(page_size)
    return [_post_out(p) for p in db.scalars(stmt).all()]


@router.get("/posts/archive")
def posts_archive(
    db: Session = Depends(get_db),
    pagina: str | None = None,
):
    """Recompte de posts per any i mes, opcionalment filtrat per pàgina."""
    stmt = (
        select(
            extract("year", Post.published_at).label("year"),
            extract("month", Post.published_at).label("month"),
            func.count(Post.slug).label("count"),
        )
        .where(Post.published_at.is_not(None))
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
    if post is None or post.published_at is None:
        raise HTTPException(404, "Post no trobat")
    return _post_out(post)


# ---------------------------------------------------------------------------
# Agenda
# ---------------------------------------------------------------------------

@router.get("/events", response_model=list[EventOut])
def list_events(db: Session = Depends(get_db)):
    return db.scalars(
        select(Event)
        .where(Event.date >= datetime.now(timezone.utc))
        .order_by(Event.date)
    ).all()
