import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from ...database import get_db
from ...models import ComandaLinea, Item, RecordProduct, Release, ReleaseFloristeria
from ...schemas import ReleaseIn
from ...services import discogs
from ...services.security import require_admin
from ...tenant_secrets import get_tenant_secrets
from ._shared import require_discogs_enabled

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


# --- Listado completo de releases (admin, con y sin stock) ---

@router.get("/releases")
def list_releases(
    q: str | None = None,
    limit: int = Query(50, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    filters = []
    if q:
        like = f"%{q}%"
        filters.append(
            or_(RecordProduct.artista.ilike(like), Release.title.ilike(like), RecordProduct.sello.ilike(like), Release.ean.ilike(like))
        )

    # LEFT OUTER: un release del vertical floristry no té fila a
    # RecordProduct i tot i així ha d'aparèixer en aquest llistat.
    count_stmt = select(func.count(Release.id)).outerjoin(RecordProduct, RecordProduct.release_id == Release.id)
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = db.scalar(count_stmt)

    stmt = (
        select(Release)
        .outerjoin(RecordProduct, RecordProduct.release_id == Release.id)
        .options(
            selectinload(Release.items).selectinload(Item.record_detail),
            selectinload(Release.etiquetes),
            selectinload(Release.images),
            selectinload(Release.floristeria),
            selectinload(Release.record),
        )
        .order_by(RecordProduct.artista, Release.title)
        .offset(offset)
        .limit(limit)
    )
    if filters:
        stmt = stmt.where(*filters)
    releases = db.scalars(stmt).all()

    return {
        "total": total,
        "releases": [
            {
                "id": r.id,
                "artista": r.artista,
                "titulo": r.title,
                "sello": r.sello,
                "referencia": r.referencia,
                "ean": r.ean,
                "formato": r.formato,
                "anio": r.anio,
                "genero": r.genero,
                "imagen_url": r.image_url,
                "properament": r.coming_soon,
                "data_disponibilitat": r.available_at.isoformat() if r.available_at else None,
                "esta_sonant": r.esta_sonant,
                "discogs_release_id": r.discogs_release_id,
                "seccio_id": r.section_id,
                "color": r.floristeria.color if r.floristeria else None,
                "tipus_flor": r.floristeria.tipus_flor if r.floristeria else None,
                "durabilitat_dies": r.floristeria.durabilitat_dies if r.floristeria else None,
                "items": [
                    {
                        "id": i.id,
                        "precio": str(i.price),
                        "coste_adquisicion": str(i.acquisition_cost) if i.acquisition_cost is not None else None,
                        "compra_id": str(i.compra_id) if i.compra_id else None,
                        "condicion": i.condition,
                        "estado_disco": i.estado_disco,
                        "estado_funda": i.estado_funda,
                        "status": i.status,
                        "codi_discogs": i.codi_discogs,
                        "cantidad": i.quantity,
                        "cantidad_reservada": i.reserved_quantity,
                        "alerta_stock_minimo": i.min_stock_alert,
                    }
                    for i in r.items
                ],
                "etiquetes": [{"id": e.id, "slug": e.slug, "nom_ca": e.name_ca, "nom_es": e.name_es,
                               "color": e.color, "activa": e.active, "posicio": e.position}
                              for e in r.etiquetes],
                "images": [{"id": img.id, "url": img.url, "posicio": img.position,
                            "tipus": img.type, "font": img.source}
                           for img in sorted(r.images, key=lambda x: x.position)],
            }
            for r in releases
        ],
    }


# --- Alta asistida por Discogs ---

@router.get("/discogs/search", dependencies=[Depends(require_discogs_enabled)])
def discogs_search(request: Request, q: str = Query(min_length=3)):
    token = get_tenant_secrets(request.state.tenant.id).discogs_token
    try:
        return discogs.search_releases(token, q)
    except Exception as exc:
        raise HTTPException(502, f"Error consultando Discogs: {exc}")


@router.get("/discogs/release/{release_id}", dependencies=[Depends(require_discogs_enabled)])
def discogs_get_release(release_id: int, request: Request):
    """Dades completes d'un release de Discogs: tracklist, crèdits, país, estils."""
    token = get_tenant_secrets(request.state.tenant.id).discogs_token
    try:
        return discogs.get_release(token, release_id)
    except Exception as exc:
        raise HTTPException(502, f"Error consultando Discogs: {exc}")


# --- Catálogo ---

@router.get("/releases/check-duplicate")
def check_duplicate_release(
    discogs_release_id: int | None = None,
    ean: str | None = None,
    artista: str | None = None,
    titulo: str | None = None,
    exclude_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
):
    """Avisa si ja existeix un release semblant abans de donar-ne d'alta un altre.
    No bloqueja res: és informatiu (segona mà rara pot coincidir per error)."""
    conditions = []
    if discogs_release_id:
        conditions.append(RecordProduct.discogs_release_id == discogs_release_id)
    if ean:
        conditions.append(Release.ean == ean)
    if artista and titulo:
        conditions.append((RecordProduct.artista.ilike(artista)) & (Release.title.ilike(titulo)))
    if not conditions:
        return []

    stmt = (
        select(Release)
        .outerjoin(RecordProduct, RecordProduct.release_id == Release.id)
        .options(selectinload(Release.items), selectinload(Release.record))
        .where(or_(*conditions))
    )
    if exclude_id:
        stmt = stmt.where(Release.id != exclude_id)

    return [
        {
            "id": r.id,
            "artista": r.artista,
            "titulo": r.title,
            "sello": r.sello,
            "ean": r.ean,
            "formato": r.formato,
            "anio": r.anio,
            "imagen_url": r.image_url,
            "num_items": len(r.items),
        }
        for r in db.scalars(stmt).all()
    ]


FLORISTERIA_FIELDS = {"color", "tipus_flor", "durabilitat_dies"}
RECORD_FIELDS = {
    "artista", "sello", "referencia", "formato", "anio", "genero", "pais", "estilos",
    "tracklist", "credits", "discogs_release_id",
}
# Ningún campo de un vertical debe colarse por el payload de otro (antes,
# como ambos conjuntos se aceptaban siempre sin mirar el vertical del
# tenant, un tenant floristry podía acabar con una fila RecordProduct
# rellenada si el payload traía artista/sello — ver
# docs/ARQUITECTURA_CORE_VERTICAL.md §5 y Fase 3).
VERTICAL_EXTENSION_FIELDS = FLORISTERIA_FIELDS | RECORD_FIELDS


def _upsert_floristeria(db: Session, release_id: uuid.UUID, data: dict) -> None:
    """Ver plan de la Fase 4, sección C: extensión 1:1 de Release para el
    vertical floristeria — solo se toca si algún campo viene informado, un
    tenant que no sea floristry nunca los rellena y no genera fila vacía."""
    floristeria_data = {k: data[k] for k in FLORISTERIA_FIELDS}
    if all(v is None for v in floristeria_data.values()):
        return
    extension = db.get(ReleaseFloristeria, release_id)
    if extension is None:
        db.add(ReleaseFloristeria(release_id=release_id, **floristeria_data))
    else:
        for field, value in floristeria_data.items():
            setattr(extension, field, value)


def _upsert_record(db: Session, release_id: uuid.UUID, data: dict) -> None:
    """Extensión 1:1 de Release para el vertical records — mismo patrón que
    _upsert_floristeria (ver docs/ARQUITECTURA_CORE_VERTICAL.md §4.2).
    `spotify_album_id` no está en RECORD_FIELDS a propósito: no forma parte
    de ReleaseIn (se rellena aparte, vía el flujo de enrich de Discogs), y
    tratarlo aquí pisaría el valor existente con None en cada PUT."""
    record_data = {k: data[k] for k in RECORD_FIELDS}
    if all(v is None for v in record_data.values()):
        return
    extension = db.get(RecordProduct, release_id)
    if extension is None:
        db.add(RecordProduct(release_id=release_id, **record_data))
    else:
        for field, value in record_data.items():
            setattr(extension, field, value)


def _upsert_vertical_extension(db: Session, request: Request, release_id: uuid.UUID, data: dict) -> None:
    """Aplica solo la extensión que corresponde al vertical del tenant —
    aislamiento real server-side, no delegado al frontend (que hasta ahora
    era el único que decidía qué campos mostrar/enviar)."""
    vertical_id = request.state.tenant.vertical_id
    if vertical_id == "records":
        _upsert_record(db, release_id, data)
    elif vertical_id == "floristry":
        _upsert_floristeria(db, release_id, data)


@router.post("/releases", status_code=201)
def create_release(payload: ReleaseIn, request: Request, db: Session = Depends(get_db)):
    data = payload.model_dump()
    release_fields = {k: v for k, v in data.items() if k not in VERTICAL_EXTENSION_FIELDS}
    release = Release(**release_fields)
    db.add(release)
    db.flush()
    _upsert_vertical_extension(db, request, release.id, data)
    db.commit()
    db.refresh(release)
    return {"id": release.id}


@router.put("/releases/{release_id}")
def update_release(release_id: uuid.UUID, payload: ReleaseIn, request: Request, db: Session = Depends(get_db)):
    release = db.get(Release, release_id)
    if release is None:
        raise HTTPException(404, "Release no encontrado")
    data = payload.model_dump()
    for field, value in data.items():
        if field not in VERTICAL_EXTENSION_FIELDS:
            setattr(release, field, value)
    _upsert_vertical_extension(db, request, release.id, data)
    db.commit()
    db.refresh(release)
    return {"id": release.id}


@router.delete("/releases/{release_id}", status_code=204)
def delete_release(release_id: uuid.UUID, db: Session = Depends(get_db)):
    release = db.get(Release, release_id)
    if release is None:
        raise HTTPException(404, "Release no encontrado")
    if db.scalar(select(Item.id).where(Item.release_id == release_id).limit(1)):
        raise HTTPException(409, "No es pot eliminar: el release té còpies (items) associades. Elimina-les primer.")
    if db.scalar(select(ComandaLinea.id).where(ComandaLinea.release_id == release_id).limit(1)):
        raise HTTPException(409, "No es pot eliminar: el release té línies de comanda associades.")
    db.delete(release)
    db.commit()


# --- Properament (pre-venda) ---

@router.patch("/releases/{release_id}/properament")
def set_properament(
    release_id: uuid.UUID,
    properament: bool,
    data_disponibilitat: str | None = None,
    db: Session = Depends(get_db),
):
    release = db.get(Release, release_id)
    if release is None:
        raise HTTPException(404, "Release no trobat")
    release.coming_soon = properament
    if data_disponibilitat:
        release.available_at = date.fromisoformat(data_disponibilitat)
    elif not properament:
        release.available_at = None
    db.commit()
    return {"properament": release.coming_soon, "data_disponibilitat": release.available_at}


# --- Està sonant (portada) ---
# Nomes hi pot haver un disc "sonant" alhora: en marcar-ne un, es desmarquen
# la resta a nivell de servidor (no confiar en que l'admin en desmarqui cap).

@router.patch("/releases/{release_id}/esta-sonant")
def set_esta_sonant(
    release_id: uuid.UUID,
    esta_sonant: bool,
    db: Session = Depends(get_db),
):
    release = db.get(Release, release_id)
    if release is None:
        raise HTTPException(404, "Release no trobat")
    if esta_sonant:
        db.query(RecordProduct).filter(RecordProduct.release_id != release_id).update({"esta_sonant": False})
    release.esta_sonant = esta_sonant
    db.commit()
    db.refresh(release)
    return {"esta_sonant": release.esta_sonant}
