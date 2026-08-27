from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import Pagina
from ...services.sanitize import sanitize_rich_html
from ...services.security import require_admin

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class PaginaIn(BaseModel):
    slug: str
    name: str
    type: str = "llista-posts"  # 'llista-posts' | 'estatica' | 'agenda'
    position: int = 0
    menu_visible: bool = True
    content: str | None = None


@router.get("/pagines")
def admin_list_pagines(db: Session = Depends(get_db)):
    return [
        {
            "id": p.id, "slug": p.slug, "name": p.name, "type": p.type,
            "position": p.position, "menu_visible": p.menu_visible,
            "content": p.content,
        }
        for p in db.scalars(select(Pagina).order_by(Pagina.position)).all()
    ]


@router.post("/pagines", status_code=201)
def admin_create_pagina(payload: PaginaIn, db: Session = Depends(get_db)):
    if db.scalar(select(Pagina).where(Pagina.slug == payload.slug)):
        raise HTTPException(409, "Ja existeix una pàgina amb aquest slug")
    data = payload.model_dump()
    data["content"] = sanitize_rich_html(data["content"])
    pagina = Pagina(**data)
    db.add(pagina)
    db.commit()
    db.refresh(pagina)
    return {"id": pagina.id, "slug": pagina.slug, "name": pagina.name, "type": pagina.type,
            "position": pagina.position, "menu_visible": pagina.menu_visible}


@router.put("/pagines/{pagina_id}")
def admin_update_pagina(pagina_id: int, payload: PaginaIn, db: Session = Depends(get_db)):
    pagina = db.get(Pagina, pagina_id)
    if pagina is None:
        raise HTTPException(404, "Pàgina no trobada")
    if payload.slug != pagina.slug and db.scalar(select(Pagina).where(Pagina.slug == payload.slug)):
        raise HTTPException(409, "Ja existeix una pàgina amb aquest slug")
    for k, v in payload.model_dump().items():
        setattr(pagina, k, sanitize_rich_html(v) if k == "content" else v)
    db.commit()
    db.refresh(pagina)
    return {"id": pagina.id, "slug": pagina.slug, "name": pagina.name, "type": pagina.type,
            "position": pagina.position, "menu_visible": pagina.menu_visible}


@router.delete("/pagines/{pagina_id}", status_code=204)
def admin_delete_pagina(pagina_id: int, db: Session = Depends(get_db)):
    pagina = db.get(Pagina, pagina_id)
    if pagina is None:
        raise HTTPException(404, "Pàgina no trobada")
    db.delete(pagina)
    db.commit()


@router.patch("/pagines/reorder")
def admin_reorder_pagines(order: list[dict], db: Session = Depends(get_db)):
    """Rep [{id, position}, ...] i actualitza l'ordre del menú."""
    for item in order:
        pagina = db.get(Pagina, item["id"])
        if pagina:
            pagina.position = item["position"]
    db.commit()
    return {"ok": True}
