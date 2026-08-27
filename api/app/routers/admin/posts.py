from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from ...database import get_db
from ...models import Post, PostPagina
from ...services.sanitize import sanitize_rich_html
from ...services.security import require_admin

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class PostIn(BaseModel):
    slug: str
    title: str
    content: str
    language: str = "ca"
    published_at: str | None = None
    pagina_ids: list[int] = []  # pàgines a les que pertany


def _post_admin_out(post: Post) -> dict:
    return {
        "slug": post.slug,
        "title": post.title,
        "content": post.content,
        "language": post.language,
        "published_at": post.published_at.isoformat() if post.published_at else None,
        "created_at": post.created_at.isoformat(),
        "pagines": [{"id": p.id, "slug": p.slug, "name": p.name} for p in post.pagines],
    }


def _sync_pagines(db: Session, post: Post, pagina_ids: list[int]):
    """Actualitza la relació M2M post ↔ pagines."""
    db.execute(delete(PostPagina).where(PostPagina.post_id == post.id))
    for pid in pagina_ids:
        db.add(PostPagina(post_id=post.id, pagina_id=pid))


@router.get("/posts")
def admin_list_posts(q: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Post).options(selectinload(Post.pagines)).order_by(Post.created_at.desc())
    if q:
        stmt = stmt.where(Post.title.ilike(f"%{q}%"))
    return [_post_admin_out(p) for p in db.scalars(stmt).all()]


@router.get("/posts/{slug}")
def admin_get_post(slug: str, db: Session = Depends(get_db)):
    post = db.scalar(select(Post).options(selectinload(Post.pagines)).where(Post.slug == slug))
    if post is None:
        raise HTTPException(404, "Post no trobat")
    return _post_admin_out(post)


@router.post("/posts", status_code=201)
def admin_create_post(payload: PostIn, db: Session = Depends(get_db)):
    if db.scalar(select(Post).where(Post.slug == payload.slug)):
        raise HTTPException(409, "Ja existeix un post amb aquest slug")
    pub = datetime.fromisoformat(payload.published_at) if payload.published_at else None
    post = Post(slug=payload.slug, title=payload.title, content=sanitize_rich_html(payload.content),
                language=payload.language, published_at=pub)
    db.add(post)
    db.flush()
    _sync_pagines(db, post, payload.pagina_ids)
    db.commit()
    db.refresh(post)
    return _post_admin_out(post)


@router.put("/posts/{slug}")
def admin_update_post(slug: str, payload: PostIn, db: Session = Depends(get_db)):
    post = db.scalar(select(Post).options(selectinload(Post.pagines)).where(Post.slug == slug))
    if post is None:
        raise HTTPException(404, "Post no trobat")
    if payload.slug != slug and db.scalar(select(Post).where(Post.slug == payload.slug)):
        raise HTTPException(409, "Ja existeix un post amb el nou slug")
    post.slug = payload.slug
    post.title = payload.title
    post.content = sanitize_rich_html(payload.content)
    post.language = payload.language
    post.published_at = datetime.fromisoformat(payload.published_at) if payload.published_at else None
    _sync_pagines(db, post, payload.pagina_ids)
    db.commit()
    db.refresh(post)
    return _post_admin_out(post)


@router.delete("/posts/{slug}", status_code=204)
def admin_delete_post(slug: str, db: Session = Depends(get_db)):
    post = db.scalar(select(Post).where(Post.slug == slug))
    if post is None:
        raise HTTPException(404, "Post no trobat")
    db.delete(post)
    db.commit()
