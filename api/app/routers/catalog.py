"""Catálogo público: listado con filtros y ficha de disco."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..tenant_secrets import get_tenant_secrets
from ..models import CondicionItem, Etiqueta, Item, ItemStatus, RecordProduct, Release, ReleaseEtiqueta, Seccio
from ..schemas import CatalogPage, EtiquetaOut, GeneroFacetOut, ReleaseOut, SeccioOut
from ..services import spotify as spotify_svc

log = logging.getLogger(__name__)

router = APIRouter(prefix="/catalog", tags=["catalog"])

# Trams alfabètics per l'artista, com els separadors físics d'una cubeta
# real (veure mode "remena" del catàleg). "0-9" (None) acull tot el que no
# comença per lletra (números, símbols...): artista < "A".
RANGS_ALFABET: dict[str, tuple[str, str] | None] = {
    "0-9": None,
    "A-D": ("A", "D"),
    "E-H": ("E", "H"),
    "I-L": ("I", "L"),
    "M-P": ("M", "P"),
    "Q-T": ("Q", "T"),
    "U-Z": ("U", "Z"),
}


@router.get("/etiquetes", response_model=list[EtiquetaOut])
def list_public_etiquetes(db: Session = Depends(get_db)):
    """Etiquetes actives, per al filtre del catàleg públic."""
    stmt = select(Etiqueta).where(Etiqueta.active.is_(True)).order_by(Etiqueta.position, Etiqueta.name_ca)
    return db.scalars(stmt).all()


@router.get("/seccions", response_model=list[SeccioOut])
def list_public_seccions(db: Session = Depends(get_db)):
    """Seccions (cubetes) actives, per al mode 'remena' del catàleg."""
    stmt = select(Seccio).where(Seccio.active.is_(True)).order_by(Seccio.position, Seccio.name_ca)
    return db.scalars(stmt).all()


@router.get("/generes", response_model=list[GeneroFacetOut])
def list_public_generes(db: Session = Depends(get_db), limit: int = Query(6, ge=1, le=24)):
    """Gèneres reals amb almenys una còpia disponible, ordenats per
    freqüència — alimenta el bloc "genre_grid" del home (ver
    blocks/registry.py) perquè mai enllaci a un gènere buit."""
    item_disponible = and_(
        Item.status == ItemStatus.disponible,
        or_(Item.condition != CondicionItem.nou, Item.quantity > Item.reserved_quantity),
    )
    n_releases = func.count(func.distinct(Release.id))
    stmt = (
        select(RecordProduct.genero, n_releases.label("n"))
        .join(Release, Release.id == RecordProduct.release_id)
        .where(RecordProduct.genero.isnot(None), RecordProduct.genero != "")
        .where(
            select(Item.id).where(Item.release_id == Release.id).where(item_disponible).exists()
        )
        .group_by(RecordProduct.genero)
        .order_by(n_releases.desc())
        .limit(limit)
    )
    return [{"genero": genero, "count": n} for genero, n in db.execute(stmt).all()]


@router.get("", response_model=CatalogPage)
def list_catalog(
    db: Session = Depends(get_db),
    q: str | None = Query(None, description="búsqueda libre en artista/título/sello"),
    artista: str | None = None,
    sello: str | None = None,
    formato: str | None = None,
    genero: str | None = None,
    etiqueta: str | None = Query(None, description="slug de l'etiqueta, p.ex. novetat"),
    seccio: str | None = Query(None, description="slug de la secció/cubeta, o 'sense-classificar'"),
    rang: str | None = Query(None, description="tram alfabètic de l'artista, p.ex. 'A-D' (veure RANGS_ALFABET)"),
    esta_sonant: bool | None = None,
    precio_min: float | None = None,
    precio_max: float | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
):
    # Solo releases con al menos una copia disponible. Para nou (stock
    # agregado), `status` se queda en 'disponible' aunque no quede ninguna
    # unidad libre (cantidad - cantidad_reservada): hace falta comprobarlo
    # aparte, si no una línea nou agotada seguiría listando el release.
    item_disponible = and_(
        Item.status == ItemStatus.disponible,
        or_(Item.condition != CondicionItem.nou, Item.quantity > Item.reserved_quantity),
    )
    # Usem EXISTS en comptes de JOIN+DISTINCT perquè DISTINCT falla amb columnes JSON.
    # LEFT OUTER (no INNER): un release del vertical floristry no té fila a
    # RecordProduct i tot i així ha d'aparèixer al catàleg — ver
    # docs/ARQUITECTURA_CORE_VERTICAL.md, Fase 2.
    stmt = (
        select(Release)
        .outerjoin(RecordProduct, RecordProduct.release_id == Release.id)
        .where(
            select(Item.id)
            .where(Item.release_id == Release.id)
            .where(item_disponible)
            .exists()
        )
    )
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(RecordProduct.artista.ilike(like), Release.title.ilike(like), RecordProduct.sello.ilike(like), Release.ean.ilike(like))
        )
    if artista:
        stmt = stmt.where(RecordProduct.artista.ilike(f"%{artista}%"))
    if sello:
        stmt = stmt.where(RecordProduct.sello.ilike(f"%{sello}%"))
    if formato:
        stmt = stmt.where(RecordProduct.formato.ilike(f"%{formato}%"))
    if genero:
        stmt = stmt.where(RecordProduct.genero.ilike(f"%{genero}%"))
    if etiqueta:
        stmt = stmt.where(
            select(ReleaseEtiqueta.release_id)
            .join(Etiqueta, Etiqueta.id == ReleaseEtiqueta.etiqueta_id)
            .where(ReleaseEtiqueta.release_id == Release.id)
            .where(Etiqueta.slug == etiqueta)
            .exists()
        )
    if seccio == "sense-classificar":
        stmt = stmt.where(Release.section_id.is_(None))
    elif seccio:
        stmt = stmt.where(
            select(Seccio.id).where(Seccio.id == Release.section_id).where(Seccio.slug == seccio).exists()
        )
    if rang is not None and rang in RANGS_ALFABET:
        bounds = RANGS_ALFABET[rang]
        artista_upper = func.upper(RecordProduct.artista)
        if bounds is None:
            stmt = stmt.where(artista_upper < "A")
        else:
            letra_min, letra_max = bounds
            stmt = stmt.where(artista_upper >= letra_min, artista_upper < chr(ord(letra_max) + 1))
    if esta_sonant:
        stmt = stmt.where(RecordProduct.esta_sonant.is_(True))
    if precio_min is not None:
        stmt = stmt.where(
            select(Item.id).where(Item.release_id == Release.id)
            .where(item_disponible)
            .where(Item.price >= precio_min).exists()
        )
    if precio_max is not None:
        stmt = stmt.where(
            select(Item.id).where(Item.release_id == Release.id)
            .where(item_disponible)
            .where(Item.price <= precio_max).exists()
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.options(
            selectinload(Release.items),
            selectinload(Release.etiquetes),
            selectinload(Release.images),
            selectinload(Release.seccio),
            selectinload(Release.floristeria),
            selectinload(Release.record),
        )
        .order_by(RecordProduct.artista, Release.title)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return CatalogPage(total=total, page=page, page_size=page_size, results=rows)


@router.get("/releases/{release_id}", response_model=ReleaseOut)
async def get_release(release_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    release = db.scalar(
        select(Release)
        .where(Release.id == release_id)
        .options(
            selectinload(Release.items),
            selectinload(Release.etiquetes),
            selectinload(Release.images),
            selectinload(Release.seccio),
            selectinload(Release.floristeria),
            selectinload(Release.record),
        )
    )
    if release is None:
        raise HTTPException(404, "Disco no encontrado")

    # Cerca (i desa) l'àlbum de Spotify la primera vegada que es visita cada
    # disc — "" vol dir que ja s'ha buscat i no s'ha trobat, per no tornar-ho
    # a intentar cada visita. Si falla la cerca, no bloqueja la fitxa de disc.
    if release.spotify_album_id is None:
        secrets_ = get_tenant_secrets(request.state.tenant.id)
        if secrets_.spotify_client_id and secrets_.spotify_client_secret:
            try:
                token = await spotify_svc.get_app_access_token(
                    secrets_.spotify_client_id, secrets_.spotify_client_secret
                )
                album_id = await spotify_svc.search_album(token, release.artista, release.title)
            except Exception:
                log.warning("Error cercant l'àlbum de Spotify per a %s", release_id, exc_info=True)
                album_id = None
            release.spotify_album_id = album_id or ""
            db.commit()

    return release
