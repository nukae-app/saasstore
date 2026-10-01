"""CRUD admin de `Page` (ver models/storefront.py::Page y
docs/ARQUITECTURA_DISENY_FIGMA.md §3) — el árbol de nodos genérico que
sustituye a `HomeBlock`. El aislamiento por tenant lo aplica automáticamente
`tenancy.py` (filtro por sesión), no hace falta filtrar `tenant_id` a mano
aquí, igual que en `home_blocks.py`.

`publish_page` valida los nodos protegidos de §3d: si `requires_nodes` pide
un tipo que no está en `draft_tree`, la publicación se rechaza con 422 en
vez de copiar un árbol roto a `published_tree`. Esto es la mitad backend de
§3d — la otra mitad (impedir borrar el nodo en el editor) es Fase 2, no
existe editor real todavía."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Page, Pagina
from ..schemas import PageCreateIn, PageOut, PagePublicOut, PageUpdateIn
from ..services.security import require_admin


def _node_types_in_tree(tree: dict) -> set[str]:
    """Recorre `draft_tree` recogiendo todos los `type` presentes, a
    cualquier profundidad — mismo recorrido que hace TreeRenderer.jsx en el
    frontend, aquí solo para comprobar presencia, no para renderizar."""
    types: set[str] = set()

    def walk(node):
        if not isinstance(node, dict):
            return
        node_type = node.get("type")
        if node_type:
            types.add(node_type)
        for child in node.get("children") or []:
            walk(child)

    walk(tree)
    return types

router = APIRouter(prefix="/admin/pages", tags=["pages"], dependencies=[Depends(require_admin)])
public_router = APIRouter(prefix="/config/public/pages", tags=["pages"])


@router.get("", response_model=list[PageOut])
def list_pages(db: Session = Depends(get_db)):
    return db.scalars(select(Page).order_by(Page.slug)).all()


def _check_slug_available(db: Session, slug: str, *, exclude_id: int | None = None) -> None:
    """La colisión con rutas Core (auth/blog/checkout...) ya la bloquea
    `PageCreateIn` (RESERVED_PAGE_SLUGS, no depende de la BD). Esto cubre lo
    que solo se sabe consultando la BD:
    - otra `Page` con el mismo slug (el `UniqueConstraint` ya lo impediría,
      pero un 409 explícito es mejor que un 500 crudo de IntegrityError).
    - colisión con `Pagina` (sistema de páginas estáticas ya existente,
      `models/cms.py` — mismo espacio de URL `/[locale]/[slug]`, hallazgo
      de esta sesión, ver conversación). Unificar del todo el routing entre
      ambos sistemas queda para cuando se aborde esa pieza de la Fase 1;
      aquí solo se evita crear la colisión mientras tanto."""
    query = select(Page.id).where(Page.slug == slug)
    if exclude_id is not None:
        query = query.where(Page.id != exclude_id)
    if db.scalar(query) is not None:
        raise HTTPException(409, f"Ja existeix una pàgina amb el slug '{slug}'")
    if db.scalar(select(Pagina.id).where(Pagina.slug == slug)) is not None:
        raise HTTPException(409, f"'{slug}' ja el fa servir una pàgina estàtica existent")


@router.post("", response_model=PageOut, status_code=201)
def create_page(payload: PageCreateIn, db: Session = Depends(get_db)):
    _check_slug_available(db, payload.slug)
    page = Page(
        slug=payload.slug,
        seo_title=payload.seo_title,
        seo_description=payload.seo_description,
        requires_nodes=payload.requires_nodes,
    )
    db.add(page)
    db.commit()
    db.refresh(page)
    return page


def _get_page_or_404(slug: str, db: Session) -> Page:
    page = db.scalar(select(Page).where(Page.slug == slug))
    if page is None:
        raise HTTPException(404, "Pàgina no trobada")
    return page


@router.get("/{slug}", response_model=PageOut)
def get_page(slug: str, db: Session = Depends(get_db)):
    return _get_page_or_404(slug, db)


@router.patch("/{slug}", response_model=PageOut)
def update_page(slug: str, payload: PageUpdateIn, db: Session = Depends(get_db)):
    page = _get_page_or_404(slug, db)
    if payload.draft_tree is not None:
        page.draft_tree = payload.draft_tree
    if payload.seo_title is not None:
        page.seo_title = payload.seo_title
    if payload.seo_description is not None:
        page.seo_description = payload.seo_description
    if payload.requires_nodes is not None:
        page.requires_nodes = payload.requires_nodes
    db.commit()
    db.refresh(page)
    return page


@router.delete("/{slug}", status_code=204)
def delete_page(slug: str, db: Session = Depends(get_db)):
    page = _get_page_or_404(slug, db)
    db.delete(page)
    db.commit()


@router.post("/{slug}/publish", response_model=PageOut)
def publish_page(slug: str, db: Session = Depends(get_db)):
    """Copia `draft_tree` -> `published_tree`, rechazando (422) si falta
    algún tipo de `requires_nodes` en el árbol — ver §3d. Evita publicar un
    checkout/carrito sin su nodo protegido por un error de edición."""
    page = _get_page_or_404(slug, db)
    if page.requires_nodes:
        missing = sorted(set(page.requires_nodes) - _node_types_in_tree(page.draft_tree))
        if missing:
            raise HTTPException(422, f"Falten nodes obligatoris per publicar: {', '.join(missing)}")
    page.published_tree = page.draft_tree
    db.commit()
    db.refresh(page)
    return page


@public_router.get("/{slug}", response_model=PagePublicOut)
def get_public_page(slug: str, db: Session = Depends(get_db)):
    """Lectura pública para el renderer SSR (`[locale]/[slug]/page.jsx`,
    todavía por construir) — nunca expone `draft_tree`: si aún no se ha
    publicado nada, es como si la página no existiera de cara al público."""
    page = db.scalar(select(Page).where(Page.slug == slug))
    if page is None or page.published_tree is None:
        raise HTTPException(404, "Pàgina no trobada")
    return page
