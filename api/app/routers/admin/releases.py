import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import and_, func, literal, or_, select
from sqlalchemy.orm import Session, selectinload

from ...database import get_db
from ...models import (
    CondicionItem,
    ComandaLinea,
    Etiqueta,
    Item,
    ItemStatus,
    Proveedor,
    RecordProduct,
    RecordStockDetail,
    Release,
    ReleaseEtiqueta,
    ReleaseFloristeria,
    ReleaseImage,
    Seccio,
)
from ...schemas import ReleaseIn
from ...services import discogs
from ...services.discogs_sync import get_discogs_token_if_enabled
from ...services.security import require_admin
from ._shared import require_discogs_enabled

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


# --- Listado completo de releases (admin, con y sin stock) ---

SORT_KEYS = ("artista", "titulo", "anio", "precio", "creacion", "sello", "formato", "ean", "recepcion")


def _ultima_recepcion(release: Release):
    """Fecha en que entró la última unidad (también de copias ya vendidas):
    `entry_date` si la hay, si no `created_at`, como en el resto del ERP."""
    fechas = [i.entry_date or i.created_at for i in release.items if (i.entry_date or i.created_at)]
    return max(fechas).isoformat() if fechas else None


def _item_disponible():
    # Mismo criterio que el catálogo público: en `nou` el status se queda en
    # 'disponible' aunque no quede ninguna unidad libre.
    return and_(
        Item.status == ItemStatus.disponible,
        or_(Item.condition != CondicionItem.nou, Item.quantity > Item.reserved_quantity),
    )


def _token_in(column, values: list[str]):
    """OR de coincidencia exacta de token en un campo "A, B, C" (genero/estilos)."""
    padded = literal(", ") + column + literal(", ")
    return or_(*[padded.ilike(f"%, {v.strip()}, %") for v in values if v.strip()])


def _release_filters(
    *, q, artista, sello, formato, genero, estilo, pais, anio, anio_min, anio_max, etiqueta, seccio,
    status, condicion, estado_disco, precio_min, precio_max, con_stock, stock_bajo,
    sin_imagen, sin_discogs, sin_seccio,
) -> list:
    filters = []
    # Cada palabra de `q` debe aparecer en alguno de los campos (AND entre
    # palabras, OR entre campos): "Miles Davis Kind of Blue" casa aunque el
    # artista y el título estén en columnas distintas.
    for word in (q or "").split():
        like = f"%{word}%"
        filters.append(
            or_(RecordProduct.artista.ilike(like), Release.title.ilike(like), RecordProduct.sello.ilike(like), Release.ean.ilike(like))
        )
    if artista:
        filters.append(or_(*[RecordProduct.artista.ilike(f"%{v}%") for v in artista]))
    if sello:
        filters.append(or_(*[RecordProduct.sello.ilike(f"%{v}%") for v in sello]))
    if formato:
        filters.append(or_(*[RecordProduct.formato.ilike(v) for v in formato]))
    if genero:
        filters.append(_token_in(RecordProduct.genero, genero))
    if estilo:
        filters.append(_token_in(RecordProduct.estilos, estilo))
    if pais:
        filters.append(or_(*[RecordProduct.pais.ilike(v) for v in pais]))
    if anio:
        filters.append(RecordProduct.anio.in_(anio))
    if anio_min is not None:
        filters.append(RecordProduct.anio >= anio_min)
    if anio_max is not None:
        filters.append(RecordProduct.anio <= anio_max)
    if etiqueta:
        filters.append(
            select(ReleaseEtiqueta.release_id)
            .join(Etiqueta, Etiqueta.id == ReleaseEtiqueta.etiqueta_id)
            .where(ReleaseEtiqueta.release_id == Release.id, Etiqueta.slug.in_(etiqueta))
            .exists()
        )
    if seccio:
        filters.append(
            select(Seccio.id).where(Seccio.id == Release.section_id, Seccio.slug.in_(seccio)).exists()
        )
    if sin_seccio is not None:
        filters.append(Release.section_id.is_(None) if sin_seccio else Release.section_id.isnot(None))
    if sin_discogs is not None:
        filters.append(
            RecordProduct.discogs_release_id.is_(None) if sin_discogs else RecordProduct.discogs_release_id.isnot(None)
        )
    if sin_imagen is not None:
        sin = and_(
            or_(Release.image_url.is_(None), Release.image_url == ""),
            ~select(ReleaseImage.id).where(ReleaseImage.release_id == Release.id).exists(),
        )
        filters.append(sin if sin_imagen else ~sin)

    # Todas las condiciones sobre copias se evalúan sobre la MISMA fila `item`
    # (un solo EXISTS): "segona_ma + disponible + <20€" es una copia que cumple
    # las tres, no tres copias distintas.
    item_conds = []
    if status:
        item_conds.append(Item.status.in_(status))
    if condicion:
        item_conds.append(Item.condition.in_(condicion))
    if estado_disco:
        item_conds.append(
            Item.id.in_(
                select(RecordStockDetail.item_id).where(
                    or_(*[RecordStockDetail.estado_disco.ilike(f"%{v}%") for v in estado_disco])
                )
            )
        )
    if precio_min is not None:
        item_conds.append(Item.price >= precio_min)
    if precio_max is not None:
        item_conds.append(Item.price <= precio_max)
    if item_conds:
        filters.append(select(Item.id).where(Item.release_id == Release.id, *item_conds).exists())
    if con_stock is not None:
        hay = select(Item.id).where(Item.release_id == Release.id, _item_disponible()).exists()
        filters.append(hay if con_stock else ~hay)
    if stock_bajo:
        # Solo `nou` con alarma configurada, igual que /catalog/stock-alerts.
        filters.append(
            select(Item.id)
            .where(
                Item.release_id == Release.id,
                Item.condition == CondicionItem.nou,
                Item.status == ItemStatus.disponible,
                Item.min_stock_alert.isnot(None),
                (Item.quantity - Item.reserved_quantity) <= Item.min_stock_alert,
            )
            .exists()
        )
    return filters


def _order_by(sort: str, direction: str):
    if sort == "titulo":
        col = Release.title
    elif sort == "anio":
        col = RecordProduct.anio
    elif sort == "sello":
        col = RecordProduct.sello
    elif sort == "formato":
        col = RecordProduct.formato
    elif sort == "ean":
        col = Release.ean
    elif sort == "recepcion":
        col = (
            select(func.max(func.coalesce(Item.entry_date, Item.created_at)))
            .where(Item.release_id == Release.id)
            .correlate(Release)
            .scalar_subquery()
        )
    elif sort == "creacion":
        col = Release.created_at
    elif sort == "precio":
        col = (
            select(func.min(Item.price))
            .where(Item.release_id == Release.id, _item_disponible())
            .correlate(Release)
            .scalar_subquery()
        )
    else:
        col = RecordProduct.artista
    primary = col.desc() if direction == "desc" else col.asc()
    # NULLs siempre al final, como en useSortFilter del front.
    return [col.is_(None), primary, RecordProduct.artista, Release.title]


@router.get("/releases/facets")
def release_facets(db: Session = Depends(get_db)):
    """Valores distintos de sello, formato y año de TODO el catálogo (con y sin
    stock), para poblar los desplegables de filtro de la tabla sin tener que
    cargar todas las filas. Los nulos no se ofrecen."""
    def distinct(col):
        return [v for (v,) in db.execute(select(col).where(col.isnot(None), col != "").distinct().order_by(col)).all()]

    anios = db.scalars(
        select(RecordProduct.anio).where(RecordProduct.anio.isnot(None)).distinct().order_by(RecordProduct.anio)
    ).all()
    def tokens(col):
        # genero/estilos guardan listas "A, B, C": se parten para ofrecer cada valor suelto.
        vals = {t.strip() for v in distinct(col) for t in v.split(",") if t.strip()}
        return sorted(vals, key=str.casefold)

    def sellos():
        # "Sello – CATNO, Otro – CATNO2": una opción por nombre de sello, sin el nº de catálogo.
        names = {
            part.split(" – ")[0].split(" - ")[0].strip()
            for v in distinct(RecordProduct.sello) for part in v.split(",")
        }
        return sorted((n for n in names if n), key=str.casefold)

    return {
        "sello": sellos(),
        "formato": distinct(RecordProduct.formato),
        "anio": list(anios),
        "genero": tokens(RecordProduct.genero),
        "estilo": tokens(RecordProduct.estilos),
        "pais": distinct(RecordProduct.pais),
        "etiqueta": [
            {"slug": e.slug, "nom": e.name_ca}
            for e in db.scalars(select(Etiqueta).order_by(Etiqueta.position, Etiqueta.name_ca)).all()
        ],
        "seccio": [
            {"slug": s.slug, "nom": s.name_ca}
            for s in db.scalars(select(Seccio).order_by(Seccio.position, Seccio.name_ca)).all()
        ],
    }


@router.get("/releases")
def list_releases(
    q: str | None = None,
    artista: list[str] | None = Query(None),
    sello: list[str] | None = Query(None),
    formato: list[str] | None = Query(None),
    genero: list[str] | None = Query(None),
    estilo: list[str] | None = Query(None),
    pais: list[str] | None = Query(None),
    anio: list[int] | None = Query(None, description="años exactos"),
    anio_min: int | None = None,
    anio_max: int | None = None,
    etiqueta: list[str] | None = Query(None, description="slugs de etiqueta"),
    seccio: list[str] | None = Query(None, description="slugs de sección"),
    status: list[ItemStatus] | None = Query(None, description="alguna copia con este status"),
    condicion: list[CondicionItem] | None = Query(None),
    estado_disco: list[str] | None = Query(None, description="p. ej. 'Near Mint'"),
    precio_min: float | None = None,
    precio_max: float | None = None,
    con_stock: bool | None = Query(None, description="true: con copias a la venta; false: sin ninguna"),
    stock_bajo: bool | None = Query(None, description="nou con alarma de stock mínimo alcanzada"),
    sin_imagen: bool | None = None,
    sin_discogs: bool | None = Query(None, description="true: sin vincular a Discogs"),
    sin_seccio: bool | None = None,
    sort: str = Query("artista", pattern=f"^({'|'.join(SORT_KEYS)})$"),
    dir: str = Query("asc", pattern="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    filters = _release_filters(
        q=q, artista=artista, sello=sello, formato=formato, genero=genero, estilo=estilo, pais=pais,
        anio=anio, anio_min=anio_min, anio_max=anio_max, etiqueta=etiqueta, seccio=seccio, status=status,
        condicion=condicion, estado_disco=estado_disco, precio_min=precio_min, precio_max=precio_max,
        con_stock=con_stock, stock_bajo=stock_bajo, sin_imagen=sin_imagen, sin_discogs=sin_discogs,
        sin_seccio=sin_seccio,
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
            selectinload(Release.suggested_supplier),
        )
        .order_by(*_order_by(sort, dir))
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
                "estilos": r.estilos,
                "pais": r.pais,
                "creado": r.created_at.isoformat() if r.created_at else None,
                "ultima_recepcion": _ultima_recepcion(r),
                "proveedor_sugerido_id": r.suggested_supplier_id,
                "proveedor_sugerido_nombre": r.suggested_supplier.name if r.suggested_supplier else None,
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
def discogs_search(request: Request, q: str = Query(min_length=3), db: Session = Depends(get_db)):
    token = get_discogs_token_if_enabled(db, request.state.tenant.id)
    try:
        return discogs.search_releases(token, q)
    except Exception as exc:
        raise HTTPException(502, f"Error consultando Discogs: {exc}")


@router.get("/discogs/release/{release_id}", dependencies=[Depends(require_discogs_enabled)])
def discogs_get_release(release_id: int, request: Request, db: Session = Depends(get_db)):
    """Dades completes d'un release de Discogs: tracklist, crèdits, país, estils."""
    token = get_discogs_token_if_enabled(db, request.state.tenant.id)
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


def _check_supplier(db: Session, supplier_id: uuid.UUID | None) -> None:
    if supplier_id is not None and db.get(Proveedor, supplier_id) is None:
        raise HTTPException(422, "Proveedor no encontrado")


@router.post("/releases", status_code=201)
def create_release(payload: ReleaseIn, request: Request, db: Session = Depends(get_db)):
    data = payload.model_dump()
    _check_supplier(db, payload.suggested_supplier_id)
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
    # El proveedor habitual solo se toca si el cliente lo envía: un PUT de un
    # cliente anterior a este campo (o un flujo que no lo conoce) no debe borrarlo.
    if "suggested_supplier_id" in payload.model_fields_set:
        _check_supplier(db, payload.suggested_supplier_id)
    else:
        data.pop("suggested_supplier_id", None)
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

class ProveedorSugeridoIn(BaseModel):
    suggested_supplier_id: uuid.UUID | None = None


@router.patch("/releases/{release_id}/proveedor-sugerido")
def set_proveedor_sugerido(release_id: uuid.UUID, payload: ProveedorSugeridoIn, db: Session = Depends(get_db)):
    """Fija (o quita, con null) el proveïdor habitual d'un disc sense tocar la resta
    de camps: el PUT de /releases/{id} reemplaça la fitxa sencera i no serveix per això."""
    release = db.get(Release, release_id)
    if release is None:
        raise HTTPException(404, "Release no trobat")
    _check_supplier(db, payload.suggested_supplier_id)
    release.suggested_supplier_id = payload.suggested_supplier_id
    db.commit()
    return {"id": release.id, "suggested_supplier_id": release.suggested_supplier_id}


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
