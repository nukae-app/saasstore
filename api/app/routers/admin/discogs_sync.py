import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from ...database import get_db
from ...models import Item, ItemStatus, RecordProduct, Release
from ...services import discogs
from ...services.discogs import get_listing, get_release_image
from ...services.discogs_sync import (
    enrich_release_from_discogs, push_item_to_discogs, remove_item_from_discogs,
    sync_discogs_orders,
)
from ...services.security import require_admin
from ...tenant_secrets import get_tenant_secrets
from ._shared import require_discogs_enabled

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.post("/discogs/sync/orders", dependencies=[Depends(require_discogs_enabled)])
def sync_orders(request: Request, db: Session = Depends(get_db)):
    """Pull manual de comandes del Marketplace (el mateix que fa el cron periòdic)."""
    return sync_discogs_orders(db, get_tenant_secrets(request.state.tenant.id).discogs_token)


# --- Discogs Sync (gestió manual) ---

def _release_needs_sync(release: Release) -> bool:
    """Un release necessita re-sincronitzar-se amb Discogs si li falta caràtula
    en alta qualitat, gènere, EAN, tracklist o format."""
    return (
        not release.image_url
        or "h:150" in release.image_url
        or not release.genero
        or not release.ean
        or not release.tracklist
        or not release.formato
    )


@router.get("/discogs/sync/stats", dependencies=[Depends(require_discogs_enabled)])
def discogs_sync_stats(db: Session = Depends(get_db)):
    """Resum d'estat de sincronització de dades amb Discogs (caràtula, gènere, EAN...)."""
    items = db.scalars(
        select(Item)
        .options(selectinload(Item.release))
        .where(Item.status.in_([ItemStatus.disponible, ItemStatus.reservado]))
    ).all()

    total = len(items)
    listed = sum(1 for i in items if i.codi_discogs)
    has_release_id = sum(1 for i in items if not i.codi_discogs and i.release.discogs_release_id)
    no_release_id = sum(1 for i in items if not i.codi_discogs and not i.release.discogs_release_id)
    amb_caratula = sum(1 for i in items if i.release.image_url)
    sense_caratula = total - amb_caratula
    sense_genere = sum(1 for i in items if not i.release.genero)
    sense_ean = sum(1 for i in items if not i.release.ean)
    sense_format = sum(1 for i in items if not i.release.formato)

    return {
        "total_actius": total,
        "listed_discogs": listed,
        "pot_listar": has_release_id,
        "sense_release_id": no_release_id,
        "amb_caratula": amb_caratula,
        "sense_caratula": sense_caratula,
        "sense_genere": sense_genere,
        "sense_ean": sense_ean,
        "sense_format": sense_format,
    }


@router.get("/discogs/sync/items", dependencies=[Depends(require_discogs_enabled)])
def discogs_sync_items(
    sync_status: str | None = None,  # "listed" | "pending" | "no_release_id"
    image_status: str | None = None,  # "amb_caratula" | "sense_caratula"
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Llista d'items amb el seu estat de sincronització Discogs i caràtula."""
    stmt = (
        select(Item)
        .options(selectinload(Item.release).selectinload(Release.record), selectinload(Item.record_detail))
        .where(Item.status.in_([ItemStatus.disponible, ItemStatus.reservado]))
        .order_by(Item.created_at.desc())
    )
    if q:
        like = f"%{q}%"
        stmt = stmt.join(Item.release).outerjoin(RecordProduct, RecordProduct.release_id == Release.id).where(
            or_(RecordProduct.artista.ilike(like), Release.title.ilike(like))
        )
    items = db.scalars(stmt).all()

    if sync_status == "listed":
        items = [i for i in items if i.codi_discogs]
    elif sync_status == "pending":
        items = [i for i in items if not i.codi_discogs and i.release.discogs_release_id]
    elif sync_status == "no_release_id":
        items = [i for i in items if not i.codi_discogs and not i.release.discogs_release_id]

    if image_status == "amb_caratula":
        items = [i for i in items if i.release.image_url]
    elif image_status == "sense_caratula":
        items = [i for i in items if not i.release.image_url]

    total = len(items)
    page = items[offset : offset + limit]

    return {
        "total": total,
        "items": [
            {
                "item_id": i.id,
                "release_id": str(i.release_id),
                "artista": i.release.artista,
                "titulo": i.release.title,
                "formato": i.release.formato,
                "precio": str(i.price),
                "estado_disco": i.estado_disco,
                "estado_funda": i.estado_funda,
                "status": i.status,
                "codi_discogs": i.codi_discogs,
                "discogs_release_id": i.release.discogs_release_id,
                "imagen_url": i.release.image_url,
                "sync_status": (
                    "listed" if i.codi_discogs
                    else "pending" if i.release.discogs_release_id
                    else "no_release_id"
                ),
            }
            for i in page
        ],
    }


@router.post("/discogs/sync/items/{item_id}/push", dependencies=[Depends(require_discogs_enabled)])
def discogs_sync_push(item_id: uuid.UUID, db: Session = Depends(get_db)):
    """Puja manualment un item al Marketplace de Discogs."""
    item = db.scalar(
        select(Item).options(selectinload(Item.release)).where(Item.id == item_id)
    )
    if item is None:
        raise HTTPException(404, "Item no trobat")
    if item.codi_discogs:
        return {"codi_discogs": item.codi_discogs, "action": "already_listed"}
    if not item.release.discogs_release_id:
        raise HTTPException(422, "El release no té discogs_release_id — no es pot crear listing")
    if item.status not in (ItemStatus.disponible, ItemStatus.reservado):
        raise HTTPException(422, "L'item no és disponible")

    listing_id = push_item_to_discogs(
        get_tenant_secrets(item.tenant_id).discogs_token,
        item_id=item.id,
        release_discogs_id=item.release.discogs_release_id,
        precio=float(item.price),
        estado_disco=item.estado_disco,
        estado_funda=item.estado_funda,
    )
    if listing_id is None:
        raise HTTPException(502, "Error al crear el listing a Discogs (compte venedor configurat?)")

    item.codi_discogs = listing_id
    db.commit()
    return {"codi_discogs": listing_id, "action": "pushed"}


@router.delete("/discogs/sync/items/{item_id}/listing", dependencies=[Depends(require_discogs_enabled)])
def discogs_sync_remove(item_id: uuid.UUID, db: Session = Depends(get_db)):
    """Elimina manualment el listing de Discogs (sense canviar l'status de l'item)."""
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "Item no trobat")
    if not item.codi_discogs:
        return {"action": "nothing_to_remove"}

    ok = remove_item_from_discogs(get_tenant_secrets(item.tenant_id).discogs_token, item.codi_discogs)
    if ok:
        old = item.codi_discogs
        item.codi_discogs = None
        db.commit()
        return {"action": "removed", "codi_discogs_removed": old}
    raise HTTPException(502, "Error eliminant el listing de Discogs")


@router.post("/discogs/sync/releases/{release_id}/enrich", dependencies=[Depends(require_discogs_enabled)])
def discogs_sync_enrich_release(release_id: uuid.UUID, db: Session = Depends(get_db)):
    """Actualitza tracklist, crèdits i metadades d'un release des de Discogs.

    Útil després de vincular a mà un discogs_release_id a un release donat
    d'alta manualment (camp editable a l'admin) que ara ja està catalogat.
    """
    release = db.get(Release, release_id)
    if release is None:
        raise HTTPException(404, "Release no trobat")
    if not release.discogs_release_id:
        raise HTTPException(422, "El release no té discogs_release_id")

    ok = enrich_release_from_discogs(release, db, get_tenant_secrets(release.tenant_id).discogs_token)
    if not ok:
        raise HTTPException(502, "Error consultant Discogs")

    return {
        "id": release.id,
        "tracklist": release.tracklist,
        "credits": release.credits,
        "genero": release.genero,
        "pais": release.pais,
        "estilos": release.estilos,
        "formato": release.formato,
        "ean": release.ean,
        "imagen_url": release.image_url,
        "sello": release.sello,
    }


@router.post("/discogs/sync/items/{item_id}/enrich-image", dependencies=[Depends(require_discogs_enabled)])
def enrich_item_image(item_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    """Obté i guarda la caràtula d'un item consultant Discogs."""
    item = db.scalar(
        select(Item).options(selectinload(Item.release)).where(Item.id == item_id)
    )
    if item is None:
        raise HTTPException(404, "Item no trobat")

    release = item.release
    imagen_url = None
    token = get_tenant_secrets(request.state.tenant.id).discogs_token

    try:
        if release.discogs_release_id:
            imagen_url = get_release_image(token, release.discogs_release_id)
        elif item.codi_discogs:
            info = get_listing(token, item.codi_discogs)
            if info:
                if info.get("discogs_release_id"):
                    release.discogs_release_id = info["discogs_release_id"]
                    imagen_url = get_release_image(token, info["discogs_release_id"])
                if not imagen_url:
                    imagen_url = info.get("imagen_url")
    except Exception as exc:
        raise HTTPException(502, f"Error consultant Discogs: {exc}")

    if not imagen_url:
        raise HTTPException(404, "No s'ha trobat caràtula a Discogs per aquest disc")

    release.image_url = imagen_url
    db.commit()
    return {"imagen_url": imagen_url, "release_id": str(release.id)}


@router.post("/discogs/sync/images/start", dependencies=[Depends(require_discogs_enabled)])
def start_bulk_sync(request: Request, db: Session = Depends(get_db)):
    """Inicia la sincronització completa amb Discogs en segon pla (best-effort):
    caràtula, gènere, estils, país, tracklist, crèdits i EAN — una sola crida
    a Discogs per release (GET /releases/{id} ja ho torna tot alhora).

    Processa els releases que els falta alguna d'aquestes dades.
    """
    import threading

    items_data = db.scalars(
        select(Item)
        .options(selectinload(Item.release))
        .where(Item.status.in_([ItemStatus.disponible, ItemStatus.reservado]))
    ).all()

    seen: set = set()
    work = []
    for i in items_data:
        rid = i.release_id
        if rid in seen or not _release_needs_sync(i.release):
            continue
        seen.add(rid)
        work.append((rid, i.release.discogs_release_id, i.codi_discogs))

    if not work:
        return {"message": "Tots els releases ja estan sincronitzats amb Discogs", "pending": 0}

    threading.Thread(
        target=_run_bulk_in_new_sessions, args=(work, request.state.tenant.id), daemon=True
    ).start()
    return {"message": f"Sincronitzant {len(work)} discs amb Discogs en segon pla", "pending": len(work)}


def _run_bulk_in_new_sessions(work: list, tenant_id: uuid.UUID):
    """Executa la sincronització completa en sessions de BD independents."""
    import logging
    from ...database import SessionLocal
    from ...tenancy import scoped_to
    from ...tenant_secrets import get_tenant_secrets

    log = logging.getLogger(__name__)
    # `work` ya viene filtrado al tenant correcto desde start_bulk_sync (la
    # query de Items ahí sí pasa por get_db) — pero cada release_id se busca
    # aquí en una sesión nueva sin tenant_id en session.info, así que el
    # filtro automático no aplicaría de todos modos si hiciera falta.
    # scoped_to sí hace falta para que el token de Discogs sea el de este
    # tenant, no uno global.
    token = get_tenant_secrets(tenant_id).discogs_token
    for release_id, discogs_release_id, codi_discogs in work:
        try:
            with SessionLocal() as session, scoped_to(session, tenant_id):
                rel = session.get(Release, release_id)
                if rel is None or not _release_needs_sync(rel):
                    continue

                rel_id = discogs_release_id
                fallback_imagen = None
                if not rel_id and codi_discogs:
                    info = get_listing(token, codi_discogs)
                    if info:
                        rel_id = info.get("discogs_release_id")
                        fallback_imagen = info.get("imagen_url")
                        if rel_id:
                            rel.discogs_release_id = rel_id

                if rel_id:
                    data = discogs.get_release(token, rel_id)
                    if not rel.image_url or "h:150" in rel.image_url:
                        rel.image_url = data.get("imagen_url") or rel.image_url
                    rel.genero = data.get("genero") or rel.genero
                    rel.estilos = data.get("estilos") or rel.estilos
                    rel.pais = data.get("pais") or rel.pais
                    rel.sello = rel.sello or data.get("sello")
                    rel.ean = data.get("ean") or rel.ean
                    rel.tracklist = data.get("tracklist") or rel.tracklist
                    rel.credits = data.get("credits") or rel.credits
                    rel.formato = rel.formato or data.get("formato")
                elif fallback_imagen and (not rel.image_url or "h:150" in rel.image_url):
                    rel.image_url = fallback_imagen
                else:
                    continue

                session.commit()
                log.info("discogs sync: %s (%s)", release_id, rel.title)
        except Exception as exc:
            log.warning("discogs sync error %s: %s", release_id, exc)
