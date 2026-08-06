"""Panel de administración: gestión del catálogo y de los pedidos.

El flujo de alta pensado para el día a día:
1. GET /admin/discogs/search?q=artista+titulo  -> resultados con metadatos
2. POST /admin/releases con los datos autocompletados (o a mano)
3. POST /admin/items con precio + grading -> la copia sale a la venta
"""

import csv
import io
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from ..config import get_settings
from ..database import get_db
from ..models import (
    CajaMovimiento, CajaSession, ComandaLinea, CondicionItem, DevolucionVenta, Etiqueta, Event,
    Item, ItemStatus, Order, OrderItem, OrderOrigen, OrderStatus, Pagina, Payment, Post, PostPagina,
    Release, ReleaseEtiqueta, ReleaseImage, StockHold, TipoMovimiento, User,
)
from ..schemas import (
    CatalogAgingItemsOut, CatalogAgingOut, EtiquetaIn, EtiquetaOut, ItemIn, ItemUpdate,
    OrderMarcarPagadoTiendaIn, OrderPendentTiendaItemOut, OrderPendentTiendaOut, OrderStatusUpdate,
    ReleaseImageOut, ReleaseIn,
)
from ..services import discogs
from ..services.discogs_sync import (
    enrich_release_from_discogs, push_item_to_discogs, push_shipped_status,
    remove_item_from_discogs, sync_discogs_orders, sync_stock_listing,
)
from ..services.discogs import get_release_image, get_listing
from ..services.emailer import render_email_html, send_email
from ..services.sanitize import sanitize_rich_html
from ..services.i18n import translate
from ..services.iva import compute_iva_venda
from ..services.orders import finalize_payment
from ..services.reservations import release_expired, release_items, release_stock_hold
from ..services.security import require_admin

UPLOADS_DIR = "/app/uploads"

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
            or_(Release.artista.ilike(like), Release.titulo.ilike(like), Release.sello.ilike(like), Release.ean.ilike(like))
        )

    count_stmt = select(func.count(Release.id))
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = db.scalar(count_stmt)

    stmt = (
        select(Release)
        .options(
            selectinload(Release.items),
            selectinload(Release.etiquetes),
            selectinload(Release.images),
        )
        .order_by(Release.artista, Release.titulo)
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
                "titulo": r.titulo,
                "sello": r.sello,
                "referencia": r.referencia,
                "ean": r.ean,
                "formato": r.formato,
                "anio": r.anio,
                "genero": r.genero,
                "imagen_url": r.imagen_url,
                "properament": r.properament,
                "data_disponibilitat": r.data_disponibilitat.isoformat() if r.data_disponibilitat else None,
                "esta_sonant": r.esta_sonant,
                "discogs_release_id": r.discogs_release_id,
                "seccio_id": r.seccio_id,
                "items": [
                    {
                        "id": i.id,
                        "precio": str(i.precio),
                        "coste_adquisicion": str(i.coste_adquisicion) if i.coste_adquisicion is not None else None,
                        "compra_id": str(i.compra_id) if i.compra_id else None,
                        "condicion": i.condicion,
                        "estado_disco": i.estado_disco,
                        "estado_funda": i.estado_funda,
                        "status": i.status,
                        "codi_discogs": i.codi_discogs,
                        "cantidad": i.cantidad,
                        "cantidad_reservada": i.cantidad_reservada,
                    }
                    for i in r.items
                ],
                "etiquetes": [{"id": e.id, "slug": e.slug, "nom_ca": e.nom_ca, "nom_es": e.nom_es,
                               "color": e.color, "activa": e.activa, "posicio": e.posicio}
                              for e in r.etiquetes],
                "images": [{"id": img.id, "url": img.url, "posicio": img.posicio,
                            "tipus": img.tipus, "font": img.font}
                           for img in sorted(r.images, key=lambda x: x.posicio)],
            }
            for r in releases
        ],
    }


# --- Alta asistida por Discogs ---

@router.get("/discogs/search")
def discogs_search(q: str = Query(min_length=3)):
    try:
        return discogs.search_releases(q)
    except Exception as exc:
        raise HTTPException(502, f"Error consultando Discogs: {exc}")


@router.get("/discogs/release/{release_id}")
def discogs_get_release(release_id: int):
    """Dades completes d'un release de Discogs: tracklist, crèdits, país, estils."""
    try:
        return discogs.get_release(release_id)
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
        conditions.append(Release.discogs_release_id == discogs_release_id)
    if ean:
        conditions.append(Release.ean == ean)
    if artista and titulo:
        conditions.append((Release.artista.ilike(artista)) & (Release.titulo.ilike(titulo)))
    if not conditions:
        return []

    stmt = select(Release).options(selectinload(Release.items)).where(or_(*conditions))
    if exclude_id:
        stmt = stmt.where(Release.id != exclude_id)

    return [
        {
            "id": r.id,
            "artista": r.artista,
            "titulo": r.titulo,
            "sello": r.sello,
            "ean": r.ean,
            "formato": r.formato,
            "anio": r.anio,
            "imagen_url": r.imagen_url,
            "num_items": len(r.items),
        }
        for r in db.scalars(stmt).all()
    ]


@router.post("/releases", status_code=201)
def create_release(payload: ReleaseIn, db: Session = Depends(get_db)):
    release = Release(**payload.model_dump())
    db.add(release)
    db.commit()
    db.refresh(release)
    return {"id": release.id}


@router.put("/releases/{release_id}")
def update_release(release_id: uuid.UUID, payload: ReleaseIn, db: Session = Depends(get_db)):
    release = db.get(Release, release_id)
    if release is None:
        raise HTTPException(404, "Release no encontrado")
    for field, value in payload.model_dump().items():
        setattr(release, field, value)
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


@router.post("/items", status_code=201)
def create_item(payload: ItemIn, db: Session = Depends(get_db)):
    release = db.get(Release, payload.release_id)
    if release is None:
        raise HTTPException(404, "Release no encontrado")

    if payload.condicion == CondicionItem.nou.value:
        # Stock agregado: si ya hay línea nou para este release, se suma en
        # vez de duplicar (mismo criterio que la recepción de comandas, ver
        # erp.py::recibir_comanda).
        agregado = db.scalar(
            select(Item).where(Item.release_id == payload.release_id, Item.condicion == CondicionItem.nou)
        )
        if agregado is not None:
            coste_anterior = agregado.coste_adquisicion or Decimal("0")
            coste_nuevo = payload.coste_adquisicion if payload.coste_adquisicion is not None else coste_anterior
            agregado.coste_adquisicion = (
                agregado.cantidad * coste_anterior + payload.cantidad * coste_nuevo
            ) / (agregado.cantidad + payload.cantidad)
            agregado.cantidad += payload.cantidad
            agregado.precio = payload.precio
            sync_stock_listing(db, agregado)
            db.commit()
            db.refresh(agregado)
            return {"id": agregado.id, "codi_discogs": agregado.codi_discogs}

    item = Item(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)

    if item.condicion == CondicionItem.nou:
        sync_stock_listing(db, item)
        db.commit()
    # Opció B: push automàtic a Discogs si el release té discogs_release_id (segona_ma)
    elif release.discogs_release_id and not item.codi_discogs:
        listing_id = push_item_to_discogs(
            item_id=item.id,
            release_discogs_id=release.discogs_release_id,
            precio=float(item.precio),
            estado_disco=item.estado_disco,
            estado_funda=item.estado_funda,
        )
        if listing_id:
            item.codi_discogs = listing_id
            db.commit()

    return {"id": item.id, "codi_discogs": item.codi_discogs}


@router.put("/items/{item_id}")
def update_item(item_id: uuid.UUID, payload: ItemUpdate, db: Session = Depends(get_db)):
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "Ejemplar no encontrado")
    if item.status == ItemStatus.vendido:
        raise HTTPException(409, "No es pot editar: ja està venut (hi ha un pedido associat)")
    for field, value in payload.model_dump().items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return {"id": item.id}


@router.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: uuid.UUID, db: Session = Depends(get_db)):
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "Ejemplar no encontrado")
    if db.scalar(select(OrderItem.id).where(OrderItem.item_id == item_id).limit(1)):
        raise HTTPException(409, "No es pot eliminar: aquest exemplar té un pedido associat. Marca'l com a retirat en lloc d'eliminar-lo.")
    if item.codi_discogs:
        remove_item_from_discogs(item.codi_discogs)
    db.delete(item)
    db.commit()


@router.patch("/items/{item_id}/retirar")
def retire_item(item_id: uuid.UUID, db: Session = Depends(get_db)):
    """Vendido en tienda física o en Discogs: lo quitamos de la web."""
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "Ejemplar no encontrado")
    if item.status == ItemStatus.vendido:
        raise HTTPException(409, "Ya está vendido en la web (hay un pedido)")
    item.status = ItemStatus.retirado
    item.reserved_until = None
    item.reserved_by_cart_id = None
    db.commit()
    return {"status": item.status}


# --- Catálogo: export/import CSV (repreus i baixes massives) ---

CATALOG_CSV_FIELDS = [
    "item_id", "release_id", "artista", "titulo", "discogs_release_id",
    "sello", "formato", "anio", "genero",
    "precio", "condicion", "estado_disco", "estado_funda",
    "status", "codi_discogs", "eliminar",
]
# Editables des del CSV: camps d'item + camps de release que no trenquen el
# vincle amb Discogs (artista/titulo/discogs_release_id es deixen de banda).
CATALOG_CSV_RELEASE_FIELDS = ["sello", "formato", "anio", "genero"]
CATALOG_CSV_ITEM_FIELDS = ["precio", "condicion", "estado_disco", "estado_funda"]


@router.get("/catalog/export.csv")
def export_catalog_csv(db: Session = Depends(get_db)):
    items = db.scalars(
        select(Item).options(selectinload(Item.release)).order_by(Item.created_at)
    ).all()

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CATALOG_CSV_FIELDS)
    writer.writeheader()
    for i in items:
        r = i.release
        writer.writerow({
            "item_id": i.id, "release_id": r.id, "artista": r.artista, "titulo": r.titulo,
            "discogs_release_id": r.discogs_release_id or "",
            "sello": r.sello or "", "formato": r.formato or "", "anio": r.anio or "",
            "genero": r.genero or "",
            "precio": i.precio, "condicion": i.condicion,
            "estado_disco": i.estado_disco or "", "estado_funda": i.estado_funda or "",
            "status": i.status, "codi_discogs": i.codi_discogs or "", "eliminar": "",
        })

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=catalog.csv"},
    )


def _row_value(row: dict, key: str) -> str | None:
    v = (row.get(key) or "").strip()
    return v or None


def _item_field_changes(item: Item, row: dict) -> dict:
    """Camps d'item (preu/condició/grading) que difereixen del que hi ha al CSV."""
    changes = {}
    for field in CATALOG_CSV_ITEM_FIELDS:
        value = _row_value(row, field)
        if value is None:
            continue
        new_value = Decimal(value) if field == "precio" else value
        if getattr(item, field) != new_value:
            changes[field] = new_value
    return changes


def _apply_release_changes(release: Release, row: dict) -> bool:
    """Aplica els canvis de sello/formato/anio/genero (no toca artista/titulo/discogs_release_id)."""
    changed = False
    for field in CATALOG_CSV_RELEASE_FIELDS:
        value = _row_value(row, field)
        new_value = int(value) if field == "anio" and value else value
        if getattr(release, field) != new_value:
            setattr(release, field, new_value)
            changed = True
    return changed


@router.post("/catalog/import")
async def import_catalog_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Reimporta el CSV generat per /catalog/export.csv amb canvis fets a mà
    (preu, condició, grading, dades de release que no trenquen el vincle amb
    Discogs) i la columna 'eliminar' marcada amb una X per donar de baixa l'item."""
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))

    actualitzats = 0
    eliminats = 0
    sense_canvis = 0
    errors: list[dict] = []
    releases_vistos: set[uuid.UUID] = set()

    for n, row in enumerate(reader, start=2):  # fila 1 és la capçalera
        item_id_raw = _row_value(row, "item_id")
        if not item_id_raw:
            errors.append({"fila": n, "motiu": "Falta item_id"})
            continue
        try:
            item_id = uuid.UUID(item_id_raw)
        except ValueError:
            errors.append({"fila": n, "item_id": item_id_raw, "motiu": "item_id invàlid"})
            continue

        item = db.scalar(select(Item).options(selectinload(Item.release)).where(Item.id == item_id))
        if item is None:
            errors.append({"fila": n, "item_id": item_id_raw, "motiu": "Item no trobat"})
            continue

        if (_row_value(row, "eliminar") or "").upper() == "X":
            if db.scalar(select(OrderItem.id).where(OrderItem.item_id == item.id).limit(1)):
                errors.append({"fila": n, "item_id": item_id_raw, "motiu": "Venut, no es pot eliminar"})
                continue
            if item.codi_discogs:
                remove_item_from_discogs(item.codi_discogs)
            db.delete(item)
            eliminats += 1
            continue

        try:
            item_changes = _item_field_changes(item, row)
        except (InvalidOperation, ValueError):
            errors.append({"fila": n, "item_id": item_id_raw, "motiu": "Preu invàlid"})
            continue
        if item_changes and item.status == ItemStatus.vendido:
            errors.append({"fila": n, "item_id": item_id_raw, "motiu": "Venut, no es pot editar"})
            continue
        for field, value in item_changes.items():
            setattr(item, field, value)
        item_changed = bool(item_changes)

        release_changed = False
        if item.release_id not in releases_vistos:
            release_changed = _apply_release_changes(item.release, row)
            releases_vistos.add(item.release_id)

        if item_changed or release_changed:
            actualitzats += 1
        else:
            sense_canvis += 1

    db.commit()
    return {
        "actualitzats": actualitzats,
        "eliminats": eliminats,
        "sense_canvis": sense_canvis,
        "errors": errors,
    }


# --- Antiguitat de l'estoc (rotació) ---

_AGING_BUCKETS = [
    ("0_30", "0-30 dies", 0, 30),
    ("31_90", "31-90 dies", 31, 90),
    ("91_180", "91-180 dies", 91, 180),
    ("181_365", "181-365 dies", 181, 365),
    ("366_730", "1-2 anys", 366, 730),
    ("730_plus", "+2 anys", 731, None),
]
_AGING_BUCKET_KEYS = {k for k, *_ in _AGING_BUCKETS} | {"sin_fecha"}


def _aging_bucket_for_dias(dias: int) -> str:
    for key, _, lo, hi in _AGING_BUCKETS:
        if dias >= lo and (hi is None or dias <= hi):
            return key
    return _AGING_BUCKETS[-1][0]


def _aging_dias_disponibles(db: Session) -> list[tuple[Item, int | None]]:
    """Cada item disponible amb els dies des de fecha_entrada (None si no se sap)."""
    items = db.scalars(
        select(Item)
        .options(selectinload(Item.release))
        .where(
            Item.status == ItemStatus.disponible,
            or_(Item.condicion != CondicionItem.nou, Item.cantidad > Item.cantidad_reservada),
        )
    ).all()

    ahora = datetime.now(timezone.utc)
    rows: list[tuple[Item, int | None]] = []
    for item in items:
        if item.fecha_entrada is None:
            rows.append((item, None))
            continue
        fecha_entrada = item.fecha_entrada
        if fecha_entrada.tzinfo is None:  # SQLite (tests) no conserva la timezone
            fecha_entrada = fecha_entrada.replace(tzinfo=timezone.utc)
        rows.append((item, max(0, (ahora - fecha_entrada).days)))
    return rows


def _aging_item_out(item: Item, dias: int | None) -> dict:
    return {
        "item_id": item.id,
        "release_id": item.release_id,
        "artista": item.release.artista,
        "titulo": item.release.titulo,
        "imagen_url": item.release.imagen_url,
        "dias": dias,
        "fecha_entrada": item.fecha_entrada,
        "precio": item.precio,
        "coste": item.coste_adquisicion,
        "condicion": item.condicion,
        "origen": "compra" if item.compra_id else ("discogs" if item.codi_discogs else "desconegut"),
    }


@router.get("/catalog/aging", response_model=CatalogAgingOut)
def catalog_aging(db: Session = Depends(get_db)):
    """Antiguitat de l'estoc disponible (dies des de fecha_entrada) per detectar
    còpies que porten molt de temps sense vendre's i decidir rebaixes/promocions.
    fecha_entrada ve de Compra.fecha (entrades via ERP) o del "posted" de Discogs
    (estoc anterior a l'app, sincronitzat per scripts.sync_discogs_inventory)."""
    rows = _aging_dias_disponibles(db)

    con_fecha = [(i, d) for i, d in rows if d is not None]
    sin_fecha_rows = [i for i, d in rows if d is None]

    # i.precio/i.coste_adquisicion son por unidad: una línea nou representa
    # i.cantidad unidades físicas, así que el valor real es precio*cantidad.
    valor_total = sum((i.precio * i.cantidad for i, _ in rows), Decimal("0"))
    coste_total = sum(((i.coste_adquisicion or Decimal("0")) * i.cantidad for i, _ in rows), Decimal("0"))
    valor_sin_fecha = sum((i.precio * i.cantidad for i in sin_fecha_rows), Decimal("0"))
    coste_sin_fecha = sum(((i.coste_adquisicion or Decimal("0")) * i.cantidad for i in sin_fecha_rows), Decimal("0"))

    buckets = []
    for key, label, lo, hi in _AGING_BUCKETS:
        en_bucket = [(i, d) for i, d in con_fecha if d >= lo and (hi is None or d <= hi)]
        buckets.append({
            "key": key, "label": label,
            "count": len(en_bucket),
            "valor": sum((i.precio * i.cantidad for i, _ in en_bucket), Decimal("0")),
            "coste": sum(((i.coste_adquisicion or Decimal("0")) * i.cantidad for i, _ in en_bucket), Decimal("0")),
        })
    buckets.append({
        "key": "sin_fecha", "label": "Sense data d'entrada",
        "count": len(sin_fecha_rows), "valor": valor_sin_fecha, "coste": coste_sin_fecha,
    })

    dias_ordenados = sorted(d for _, d in con_fecha)
    n = len(dias_ordenados)
    edad_media = round(sum(dias_ordenados) / n, 1) if n else None
    if n == 0:
        edad_mediana = None
    elif n % 2 == 1:
        edad_mediana = float(dias_ordenados[n // 2])
    else:
        edad_mediana = (dias_ordenados[n // 2 - 1] + dias_ordenados[n // 2]) / 2

    return {
        "total_disponible": len(rows),
        "con_fecha": len(con_fecha),
        "sin_fecha": len(sin_fecha_rows),
        "valor_total": valor_total,
        "valor_sin_fecha": valor_sin_fecha,
        "coste_total": coste_total,
        "coste_sin_fecha": coste_sin_fecha,
        "edad_media_dias": edad_media,
        "edad_mediana_dias": edad_mediana,
        "buckets": buckets,
    }


@router.get("/catalog/aging/items", response_model=CatalogAgingItemsOut)
def catalog_aging_items(
    bucket: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Llista paginada d'ítems disponibles d'un bucket d'antiguitat concret (o de
    tots si no se n'indica cap), per navegar els discs de cada grup."""
    if bucket is not None and bucket not in _AGING_BUCKET_KEYS:
        raise HTTPException(422, f"bucket ha de ser un de: {', '.join(sorted(_AGING_BUCKET_KEYS))}")

    rows = _aging_dias_disponibles(db)

    if bucket == "sin_fecha":
        filtrades = [(i, d) for i, d in rows if d is None]
    elif bucket is not None:
        filtrades = [(i, d) for i, d in rows if d is not None and _aging_bucket_for_dias(d) == bucket]
    else:
        filtrades = rows

    # Més antics primer; els que no tenen data coneguda, al final.
    filtrades.sort(key=lambda par: (par[1] is None, -(par[1] or 0)))

    total = len(filtrades)
    pagina = filtrades[offset:offset + limit]

    return {
        "total": total,
        "items": [_aging_item_out(item, dias) for item, dias in pagina],
    }


# --- Pedidos ---

@router.get("/orders")
def list_orders(
    db: Session = Depends(get_db),
    status: OrderStatus | None = None,
    metodo_envio: str | None = None,
    metodo_pago: str | None = None,
    origen: OrderOrigen | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    q: str | None = None,
):
    stmt = select(Order).order_by(Order.created_at.desc())
    if status:
        stmt = stmt.where(Order.status == status)
    if metodo_envio:
        stmt = stmt.where(Order.metodo_envio == metodo_envio)
    if metodo_pago:
        stmt = stmt.where(Order.metodo_pago == metodo_pago)
    if origen:
        stmt = stmt.where(Order.origen == origen)
    if desde:
        stmt = stmt.where(Order.created_at >= desde)
    if hasta:
        stmt = stmt.where(Order.created_at <= hasta)
    orders = list(db.scalars(
        stmt.options(
            selectinload(Order.items).selectinload(OrderItem.item).selectinload(Item.release),
            selectinload(Order.items).selectinload(OrderItem.release),
        )
    ))

    # Filtre de text lliure (client-friendly: fer-ho en Python, mateix patró
    # que list_ventas_externas): email, id de comanda a Discogs, o artista/
    # títol de qualsevol dels discos de la comanda.
    if q:
        ql = q.lower()
        def _matches(o):
            if ql in o.email_contacto.lower():
                return True
            if o.discogs_order_id and ql in o.discogs_order_id.lower():
                return True
            for oi in o.items:
                release = oi.item.release if oi.item else oi.release
                if release and (ql in release.artista.lower() or ql in release.titulo.lower()):
                    return True
            return False
        orders = [o for o in orders if _matches(o)]

    # Ordres amb alguna línia "de reserva" (petició pagada per endavant,
    # encara sense exemplar físic assignat — veure OrderItem.item_id).
    pendents_arribada = set(db.scalars(
        select(OrderItem.order_id)
        .where(OrderItem.order_id.in_([o.id for o in orders]), OrderItem.item_id.is_(None))
        .distinct()
    ))

    return [
        {
            "id": o.id,
            "email": o.email_contacto,
            "status": o.status,
            "total": str(o.total),
            "coste_envio": str(o.coste_envio),
            "metodo_envio": o.metodo_envio,
            "metodo_pago": o.metodo_pago,
            "numero_seguiment": o.numero_seguiment,
            "created_at": o.created_at,
            "origen": o.origen,
            "discogs_order_id": o.discogs_order_id,
            "pendent_arribada": o.id in pendents_arribada,
            "avisada_recollida_at": o.avisada_recollida_at,
        }
        for o in orders
    ]


@router.get("/orders/pendientes-tienda", response_model=list[OrderPendentTiendaOut])
def list_orders_pendientes_tienda(db: Session = Depends(get_db)):
    """Comandes web amb 'paga al recollir' (metodo_pago='tienda') encara
    pendents de pagar: equivalent a /peticiones/reserves-recollida però per
    a Order en comptes de PeticionCliente. El TPV les mostra a la pestanya
    'Reserves web' perquè el mostrador les trobi sense haver de saber-ne
    l'id de memòria; cobrar-la (i vendre l'ítem) es fa amb
    POST /admin/orders/{id}/marcar-pagado-tienda, no amb
    /admin/ventas-externas (l'ítem ja té el seu OrderItem amb el preu/IVA
    de compra web)."""
    release_expired(db)
    orders = db.scalars(
        select(Order)
        .where(Order.status == OrderStatus.pendiente_pago, Order.metodo_pago == "tienda")
        .options(
            selectinload(Order.items).selectinload(OrderItem.item).selectinload(Item.release),
        )
        .order_by(Order.created_at)
    ).all()
    result = []
    for o in orders:
        rows_amb_item = [oi for oi in o.items if oi.item is not None]
        if not rows_amb_item:
            continue
        reserved_untils = [oi.item.reserved_until for oi in rows_amb_item if oi.item.reserved_until]
        user = db.get(User, o.user_id) if o.user_id else None
        result.append(OrderPendentTiendaOut(
            order_id=o.id, email=o.email_contacto, total=o.total, created_at=o.created_at,
            reserved_until=min(reserved_untils) if reserved_untils else None,
            user_id=user.id if user else None, user_nombre=user.nombre if user else None,
            items=[
                OrderPendentTiendaItemOut(
                    item_id=oi.item.id, artista=oi.item.release.artista, titulo=oi.item.release.titulo,
                    imagen_url=oi.item.release.imagen_url, estado_disco=oi.item.estado_disco, precio=oi.item.precio,
                )
                for oi in rows_amb_item
            ],
        ))
    return result


@router.post("/orders/{order_id}/marcar-pagado-tienda")
def marcar_pagado_tienda(order_id: uuid.UUID, payload: OrderMarcarPagadoTiendaIn, db: Session = Depends(get_db)):
    """Cobra al mostrador una comanda web 'paga en recollir': ven l'estoc
    (finalize_payment, igual que faria un pagament Redsys) i, si es paga en
    efectiu, apunta un CajaMovimiento 'entrada' a la sessió de caixa oberta
    perquè el tancament del dia hi quadri. NO crea una VentaExterna (l'Order
    ja és el registre de venda, amb el seu propi OrderItem i IVA calculat al
    checkout); total_ventas_efectivo a cerrar_caja només compta VentaExterna,
    per això cal aquest apunt manual equivalent.

    `payload.precio`, si es dona, sobreescriu el preu (i recalcula l'IVA
    snapshot) del disc abans de vendre'l — mateix descompte manual que ja
    permet el diàleg de vendre una reserva de PeticionCliente al TPV."""
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(404, "Comanda no trobada")
    if order.status != OrderStatus.pendiente_pago or order.metodo_pago != "tienda":
        raise HTTPException(409, "Aquesta comanda no està pendent de pagar a botiga")

    if payload.precio is not None:
        rows_amb_item = [oi for oi in order.items if oi.item_id is not None]
        if len(rows_amb_item) != 1:
            raise HTTPException(422, "Només es pot canviar el preu en comandes d'un sol disc")
        order_item = rows_amb_item[0]
        item = db.get(Item, order_item.item_id)
        precio_total = payload.precio * order_item.cantidad
        tipus_iva_id, iva_pct, iva_import = compute_iva_venda(item, precio_total, db)
        order_item.precio = payload.precio
        order_item.tipus_iva_id = tipus_iva_id
        order_item.iva_pct = iva_pct
        order_item.iva_import = iva_import
        order.total = precio_total  # coste_envio sempre 0 amb recogida_tienda

    failed = finalize_payment(db, order)
    if failed:
        raise HTTPException(409, "No es pot cobrar: algun exemplar ja no està disponible")

    if payload.metodo_pago == "efectivo":
        sesion_activa = db.scalar(
            select(CajaSession).where(CajaSession.fecha_cierre.is_(None))
            .order_by(CajaSession.fecha_apertura.desc())
        )
        if sesion_activa:
            db.add(CajaMovimiento(
                session_id=sesion_activa.id,
                tipo=TipoMovimiento.entrada,
                concepto=f"Comanda web #{str(order.id)[:8]} — recollida i pagament a botiga",
                importe=order.total,
                fecha=datetime.now(timezone.utc),
            ))
            db.commit()

    return {"status": order.status}


@router.get("/orders/{order_id}")
def get_order_detail(order_id: uuid.UUID, db: Session = Depends(get_db)):
    order = db.scalar(
        select(Order)
        .options(
            selectinload(Order.items).selectinload(OrderItem.item).selectinload(Item.release),
            selectinload(Order.items).selectinload(OrderItem.release),
            selectinload(Order.payments),
        )
        .where(Order.id == order_id)
    )
    if order is None:
        raise HTTPException(404, "Pedido no encontrado")

    returned_ids = set(db.scalars(
        select(DevolucionVenta.order_item_id)
        .where(DevolucionVenta.order_item_id.in_([oi.id for oi in order.items]))
    ).all())

    return {
        "id": order.id,
        "email": order.email_contacto,
        "status": order.status,
        "total": str(order.total),
        "coste_envio": str(order.coste_envio),
        "metodo_envio": order.metodo_envio,
        "metodo_pago": order.metodo_pago,
        "direccion_envio": order.direccion_envio,
        "notas": order.notas,
        "numero_seguiment": order.numero_seguiment,
        "transportista": order.transportista,
        "created_at": order.created_at,
        "origen": order.origen,
        "discogs_order_id": order.discogs_order_id,
        "discogs_buyer": order.discogs_buyer,
        "avisada_recollida_at": order.avisada_recollida_at,
        "payments": [
            {
                "id": p.id,
                "proveedor": p.proveedor,
                "ds_order": p.ds_order,
                "estado": p.estado,
                "importe": str(p.importe),
                "ds_response_code": p.ds_response_code,
                "ds_authorisation_code": p.ds_authorisation_code,
                "created_at": p.created_at,
            }
            for p in sorted(order.payments, key=lambda p: p.created_at, reverse=True)
        ],
        "items": [
            {
                "order_item_id": oi.id,
                "item_id": oi.item_id,
                "artista": oi.item.release.artista if oi.item else (oi.release.artista if oi.release else None),
                "titulo": oi.item.release.titulo if oi.item else (oi.release.titulo if oi.release else None),
                "precio": str(oi.precio),
                "condicion": oi.item.condicion if oi.item else None,
                "estado_disco": oi.item.estado_disco if oi.item else None,
                "item_status": oi.item.status if oi.item else None,
                "pendent_arribada": oi.item_id is None,
                "devuelto": oi.id in returned_ids,
            }
            for oi in order.items
        ],
    }



# Un cop pagat, l'estoc ja està venut (no torna a canviar de mans en cap
# d'aquests tres): es poden moure lliurement entre ells en qualsevol
# direcció, per corregir errades ("s'ha marcat entregat per accident",
# "el lliurem en mà, sense pas per enviat"...) sense arriscar l'estoc.
_ESTATS_LOGISTICS = {OrderStatus.pagado, OrderStatus.enviado, OrderStatus.entregado}
# Cancel·lar allibera l'estoc: no té sentit un cop ja entregat (caldria una
# devolució, no una cancel·lació) ni reversible cap enrere (l'exemplar
# pot haver-se venut a algú altre mentre estava alliberat).
_ESTATS_CANCELABLES = {OrderStatus.pendiente_pago, OrderStatus.pagado, OrderStatus.enviado}


@router.patch("/orders/{order_id}/status")
def update_order_status(order_id: uuid.UUID, payload: OrderStatusUpdate, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(404, "Pedido no encontrado")

    if payload.metodo_envio is not None and payload.metodo_envio != order.metodo_envio:
        if order.status == OrderStatus.cancelado:
            raise HTTPException(409, "No es pot canviar el mètode d'una comanda cancel·lada")
        if payload.metodo_envio == "envio":
            if payload.direccion_envio is not None:
                order.direccion_envio = payload.direccion_envio.model_dump()
            elif order.direccion_envio is None:
                raise HTTPException(422, "Cal indicar una adreça d'enviament")
        order.metodo_envio = payload.metodo_envio

    if payload.numero_seguiment is not None:
        order.numero_seguiment = payload.numero_seguiment or None
    if payload.transportista is not None:
        order.transportista = payload.transportista or None

    if payload.status is not None:
        try:
            status = OrderStatus(payload.status)
        except ValueError:
            raise HTTPException(422, "Estat invàlid")

        if status == OrderStatus.pagado and order.status == OrderStatus.pendiente_pago:
            # Marcar como pagado a mano (p. ej. "paga al recoger" en tienda):
            # esto es lo que realmente vende los ejemplares, no un simple cambio
            # de campo (ver services/orders.finalize_payment).
            failed = finalize_payment(db, order)
            if failed:
                raise HTTPException(409, "No se puede marcar como pagado: algún ejemplar ya no está disponible")
        elif status == OrderStatus.cancelado:
            if order.status not in _ESTATS_CANCELABLES:
                raise HTTPException(409, f"No es pot cancel·lar una comanda en estat {order.status.value}")
            estaba_pagado = order.status in (OrderStatus.pagado, OrderStatus.enviado)
            order.status = status
            db.commit()
            # el ejemplar vuelve a la venta (les línies "de reserva" d'una
            # petició pagada per endavant encara no tenen item_id: no hi ha
            # res a alliberar, l'exemplar encara no existeix)
            rows_amb_item = [oi for oi in order.items if oi.item_id is not None]
            item_ids_segona = [oi.item_id for oi in rows_amb_item if oi.condicion != CondicionItem.nou]
            if item_ids_segona:
                release_items(db, item_ids_segona)
            rows_nou = [oi for oi in rows_amb_item if oi.condicion == CondicionItem.nou]
            if rows_nou and estaba_pagado:
                # Ya se había vendido (cantidad descontada, hold consumido):
                # cancelar repone el stock directamente.
                for oi in rows_nou:
                    db.execute(
                        update(Item).where(Item.id == oi.item_id)
                        .values(cantidad=Item.cantidad + oi.cantidad)
                        .execution_options(synchronize_session=False)
                    )
                db.commit()
                for oi in rows_nou:
                    item = db.get(Item, oi.item_id)
                    if item is not None:
                        sync_stock_listing(db, item)
                db.commit()
            elif rows_nou:
                # Pendiente de pago todavía: el hold puede estar en cart_id
                # (redsys) o ya reasignado a order_id (tienda, ver
                # checkout.py::confirm_checkout).
                for hold in db.scalars(
                    select(StockHold).where(or_(StockHold.order_id == order.id, StockHold.cart_id == order.cart_id))
                ):
                    release_stock_hold(db, hold.id)
        elif order.status in _ESTATS_LOGISTICS and status in _ESTATS_LOGISTICS:
            order.status = status
            db.commit()
        elif (
            order.origen == OrderOrigen.discogs
            and order.status == OrderStatus.pendiente_pago
            and status in _ESTATS_LOGISTICS
        ):
            # Discogs gestiona el cobrament fora del nostre sistema: l'ítem ja
            # es marca 'vendido' en sincronitzar la comanda (veure
            # discogs_sync.sync_discogs_orders), encara que el nostre estat
            # intern digui 'pendiente_pago' fins que Discogs ens informi que
            # ha cobrat de veritat.
            order.status = status
            db.commit()
        else:
            raise HTTPException(409, f"No es pot canviar de {order.status.value} a {status.value}")

        if status == OrderStatus.enviado and order.discogs_order_id:
            # best-effort: si falla, l'enviament local ja ha quedat registrat igualment
            push_shipped_status(order.discogs_order_id, order.numero_seguiment, order.transportista)
    else:
        db.commit()

    return {
        "status": order.status, "metodo_envio": order.metodo_envio,
        "numero_seguiment": order.numero_seguiment, "transportista": order.transportista,
    }


@router.post("/orders/{order_id}/avisar-recollida")
def avisar_recollida_order(order_id: uuid.UUID, db: Session = Depends(get_db)):
    """Avisa el client per email que la comanda ja es pot recollir a la
    botiga. Un cop avisada, la comanda apareix a la pestanya "Pendent de
    recollir" (abans només hi estava perquè estava pagada, encara que ningú
    l'hagués preparat de veritat)."""
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(404, "Pedido no encontrado")
    if order.metodo_envio != "recogida_tienda":
        raise HTTPException(422, "Aquesta comanda no és de recollida a botiga")
    if order.status != OrderStatus.pagado:
        raise HTTPException(409, "La comanda encara no està pagada")
    pendent = db.scalar(
        select(OrderItem.id).where(OrderItem.order_id == order.id, OrderItem.item_id.is_(None))
    )
    if pendent is not None:
        raise HTTPException(409, "Encara hi ha exemplars pendents d'arribar")

    order.avisada_recollida_at = datetime.now(timezone.utc)
    db.commit()

    lang = order.idioma
    order_short = str(order.id)[:8]
    comanda_url = f"{get_settings().frontend_url}/{lang}/compte/comandes/{order.id}"
    send_email(
        order.email_contacto,
        translate(db, "email.order_ready_pickup.subject", lang),
        translate(db, "email.order_ready_pickup.body_text", lang, order_short=order_short, link=comanda_url),
        html=render_email_html(
            translate(db, "email.order_ready_pickup.heading", lang),
            translate(db, "email.order_ready_pickup.body_html", lang, order_short=order_short),
            cta=(translate(db, "email.order_ready_pickup.cta", lang), comanda_url),
        ),
    )

    return {"avisada_recollida_at": order.avisada_recollida_at}


@router.post("/discogs/sync/orders")
def sync_orders(db: Session = Depends(get_db)):
    """Pull manual de comandes del Marketplace (el mateix que fa el cron periòdic)."""
    return sync_discogs_orders(db)


# --- Discogs Sync (gestió manual) ---

def _release_needs_sync(release: Release) -> bool:
    """Un release necessita re-sincronitzar-se amb Discogs si li falta caràtula
    en alta qualitat, gènere, EAN, tracklist o format."""
    return (
        not release.imagen_url
        or "h:150" in release.imagen_url
        or not release.genero
        or not release.ean
        or not release.tracklist
        or not release.formato
    )


@router.get("/discogs/sync/stats")
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
    amb_caratula = sum(1 for i in items if i.release.imagen_url)
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


@router.get("/discogs/sync/items")
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
        .options(selectinload(Item.release))
        .where(Item.status.in_([ItemStatus.disponible, ItemStatus.reservado]))
        .order_by(Item.created_at.desc())
    )
    if q:
        like = f"%{q}%"
        stmt = stmt.join(Item.release).where(
            or_(Release.artista.ilike(like), Release.titulo.ilike(like))
        )
    items = db.scalars(stmt).all()

    if sync_status == "listed":
        items = [i for i in items if i.codi_discogs]
    elif sync_status == "pending":
        items = [i for i in items if not i.codi_discogs and i.release.discogs_release_id]
    elif sync_status == "no_release_id":
        items = [i for i in items if not i.codi_discogs and not i.release.discogs_release_id]

    if image_status == "amb_caratula":
        items = [i for i in items if i.release.imagen_url]
    elif image_status == "sense_caratula":
        items = [i for i in items if not i.release.imagen_url]

    total = len(items)
    page = items[offset : offset + limit]

    return {
        "total": total,
        "items": [
            {
                "item_id": i.id,
                "release_id": str(i.release_id),
                "artista": i.release.artista,
                "titulo": i.release.titulo,
                "formato": i.release.formato,
                "precio": str(i.precio),
                "estado_disco": i.estado_disco,
                "estado_funda": i.estado_funda,
                "status": i.status,
                "codi_discogs": i.codi_discogs,
                "discogs_release_id": i.release.discogs_release_id,
                "imagen_url": i.release.imagen_url,
                "sync_status": (
                    "listed" if i.codi_discogs
                    else "pending" if i.release.discogs_release_id
                    else "no_release_id"
                ),
            }
            for i in page
        ],
    }


@router.post("/discogs/sync/items/{item_id}/push")
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
        item_id=item.id,
        release_discogs_id=item.release.discogs_release_id,
        precio=float(item.precio),
        estado_disco=item.estado_disco,
        estado_funda=item.estado_funda,
    )
    if listing_id is None:
        raise HTTPException(502, "Error al crear el listing a Discogs (compte venedor configurat?)")

    item.codi_discogs = listing_id
    db.commit()
    return {"codi_discogs": listing_id, "action": "pushed"}


@router.delete("/discogs/sync/items/{item_id}/listing")
def discogs_sync_remove(item_id: uuid.UUID, db: Session = Depends(get_db)):
    """Elimina manualment el listing de Discogs (sense canviar l'status de l'item)."""
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "Item no trobat")
    if not item.codi_discogs:
        return {"action": "nothing_to_remove"}

    ok = remove_item_from_discogs(item.codi_discogs)
    if ok:
        old = item.codi_discogs
        item.codi_discogs = None
        db.commit()
        return {"action": "removed", "codi_discogs_removed": old}
    raise HTTPException(502, "Error eliminant el listing de Discogs")


@router.post("/discogs/sync/releases/{release_id}/enrich")
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

    ok = enrich_release_from_discogs(release, db)
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
        "imagen_url": release.imagen_url,
        "sello": release.sello,
    }


@router.post("/discogs/sync/items/{item_id}/enrich-image")
def enrich_item_image(item_id: uuid.UUID, db: Session = Depends(get_db)):
    """Obté i guarda la caràtula d'un item consultant Discogs."""
    item = db.scalar(
        select(Item).options(selectinload(Item.release)).where(Item.id == item_id)
    )
    if item is None:
        raise HTTPException(404, "Item no trobat")

    release = item.release
    imagen_url = None

    try:
        if release.discogs_release_id:
            imagen_url = get_release_image(release.discogs_release_id)
        elif item.codi_discogs:
            info = get_listing(item.codi_discogs)
            if info:
                if info.get("discogs_release_id"):
                    release.discogs_release_id = info["discogs_release_id"]
                    imagen_url = get_release_image(info["discogs_release_id"])
                if not imagen_url:
                    imagen_url = info.get("imagen_url")
    except Exception as exc:
        raise HTTPException(502, f"Error consultant Discogs: {exc}")

    if not imagen_url:
        raise HTTPException(404, "No s'ha trobat caràtula a Discogs per aquest disc")

    release.imagen_url = imagen_url
    db.commit()
    return {"imagen_url": imagen_url, "release_id": str(release.id)}


@router.post("/discogs/sync/images/start")
def start_bulk_sync(db: Session = Depends(get_db)):
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

    threading.Thread(target=_run_bulk_in_new_sessions, args=(work,), daemon=True).start()
    return {"message": f"Sincronitzant {len(work)} discs amb Discogs en segon pla", "pending": len(work)}


def _run_bulk_in_new_sessions(work: list):
    """Executa la sincronització completa en sessions de BD independents."""
    import logging
    from ..database import SessionLocal

    log = logging.getLogger(__name__)
    for release_id, discogs_release_id, codi_discogs in work:
        try:
            with SessionLocal() as session:
                rel = session.get(Release, release_id)
                if rel is None or not _release_needs_sync(rel):
                    continue

                rel_id = discogs_release_id
                fallback_imagen = None
                if not rel_id and codi_discogs:
                    info = get_listing(codi_discogs)
                    if info:
                        rel_id = info.get("discogs_release_id")
                        fallback_imagen = info.get("imagen_url")
                        if rel_id:
                            rel.discogs_release_id = rel_id

                if rel_id:
                    data = discogs.get_release(rel_id)
                    if not rel.imagen_url or "h:150" in rel.imagen_url:
                        rel.imagen_url = data.get("imagen_url") or rel.imagen_url
                    rel.genero = data.get("genero") or rel.genero
                    rel.estilos = data.get("estilos") or rel.estilos
                    rel.pais = data.get("pais") or rel.pais
                    rel.sello = rel.sello or data.get("sello")
                    rel.ean = data.get("ean") or rel.ean
                    rel.tracklist = data.get("tracklist") or rel.tracklist
                    rel.credits = data.get("credits") or rel.credits
                    rel.formato = rel.formato or data.get("formato")
                elif fallback_imagen and (not rel.imagen_url or "h:150" in rel.imagen_url):
                    rel.imagen_url = fallback_imagen
                else:
                    continue

                session.commit()
                log.info("discogs sync: %s (%s)", release_id, rel.titulo)
        except Exception as exc:
            log.warning("discogs sync error %s: %s", release_id, exc)


# --- Etiquetes ---

@router.get("/etiquetes", response_model=list[EtiquetaOut])
def list_etiquetes(db: Session = Depends(get_db)):
    return db.scalars(select(Etiqueta).order_by(Etiqueta.posicio, Etiqueta.id)).all()


@router.post("/etiquetes", response_model=EtiquetaOut, status_code=201)
def create_etiqueta(payload: EtiquetaIn, db: Session = Depends(get_db)):
    if db.scalar(select(Etiqueta).where(Etiqueta.slug == payload.slug)):
        raise HTTPException(409, f"Ja existeix una etiqueta amb el slug '{payload.slug}'")
    etiqueta = Etiqueta(**payload.model_dump())
    db.add(etiqueta)
    db.commit()
    db.refresh(etiqueta)
    return etiqueta


@router.put("/etiquetes/{etiqueta_id}", response_model=EtiquetaOut)
def update_etiqueta(etiqueta_id: int, payload: EtiquetaIn, db: Session = Depends(get_db)):
    etiqueta = db.get(Etiqueta, etiqueta_id)
    if etiqueta is None:
        raise HTTPException(404, "Etiqueta no trobada")
    conflict = db.scalar(
        select(Etiqueta).where(Etiqueta.slug == payload.slug, Etiqueta.id != etiqueta_id)
    )
    if conflict:
        raise HTTPException(409, f"Ja existeix una etiqueta amb el slug '{payload.slug}'")
    for k, v in payload.model_dump().items():
        setattr(etiqueta, k, v)
    db.commit()
    db.refresh(etiqueta)
    return etiqueta


@router.delete("/etiquetes/{etiqueta_id}", status_code=204)
def delete_etiqueta(etiqueta_id: int, db: Session = Depends(get_db)):
    etiqueta = db.get(Etiqueta, etiqueta_id)
    if etiqueta is None:
        raise HTTPException(404, "Etiqueta no trobada")
    db.delete(etiqueta)
    db.commit()


@router.get("/releases/{release_id}/etiquetes", response_model=list[EtiquetaOut])
def get_release_etiquetes(release_id: uuid.UUID, db: Session = Depends(get_db)):
    release = db.scalar(
        select(Release).options(selectinload(Release.etiquetes)).where(Release.id == release_id)
    )
    if release is None:
        raise HTTPException(404, "Release no trobat")
    return release.etiquetes


class _EtiquetaIdsBody(BaseModel):
    etiqueta_ids: list[int] = []

@router.put("/releases/{release_id}/etiquetes")
def set_release_etiquetes(release_id: uuid.UUID, body: _EtiquetaIdsBody, db: Session = Depends(get_db)):
    """Substitueix totes les etiquetes del release per la llista donada."""
    if not db.get(Release, release_id):
        raise HTTPException(404, "Release no trobat")
    db.execute(delete(ReleaseEtiqueta).where(ReleaseEtiqueta.release_id == release_id))
    for eid in body.etiqueta_ids:
        if db.get(Etiqueta, eid):
            db.add(ReleaseEtiqueta(release_id=release_id, etiqueta_id=eid))
    db.commit()
    return {"etiqueta_ids": body.etiqueta_ids}


# --- Galeria d'imatges ---

@router.get("/releases/{release_id}/images", response_model=list[ReleaseImageOut])
def get_release_images(release_id: uuid.UUID, db: Session = Depends(get_db)):
    return db.scalars(
        select(ReleaseImage)
        .where(ReleaseImage.release_id == release_id)
        .order_by(ReleaseImage.posicio)
    ).all()


@router.post("/releases/{release_id}/images", response_model=ReleaseImageOut, status_code=201)
async def upload_release_image(
    release_id: uuid.UUID,
    file: UploadFile = File(...),
    tipus: str = "altre",
    db: Session = Depends(get_db),
):
    if not db.get(Release, release_id):
        raise HTTPException(404, "Release no trobat")

    ext = os.path.splitext(file.filename or "")[-1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        raise HTTPException(422, "Només s'accepten imatges JPG, PNG o WebP")

    os.makedirs(UPLOADS_DIR, exist_ok=True)
    filename = f"{uuid.uuid4()}{ext}"
    filepath = os.path.join(UPLOADS_DIR, filename)
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    posicio = (db.scalar(
        select(ReleaseImage.posicio)
        .where(ReleaseImage.release_id == release_id)
        .order_by(ReleaseImage.posicio.desc())
        .limit(1)
    ) or 0) + 1

    img = ReleaseImage(
        release_id=release_id,
        url=f"/uploads/{filename}",
        posicio=posicio,
        tipus=tipus,
        font="upload",
    )
    db.add(img)
    db.commit()
    db.refresh(img)
    return img


@router.delete("/releases/{release_id}/images/{image_id}", status_code=204)
def delete_release_image(release_id: uuid.UUID, image_id: int, db: Session = Depends(get_db)):
    img = db.scalar(
        select(ReleaseImage).where(
            ReleaseImage.id == image_id, ReleaseImage.release_id == release_id
        )
    )
    if img is None:
        raise HTTPException(404, "Imatge no trobada")
    # Elimina el fitxer local si és un upload
    if img.font == "upload" and img.url.startswith("/uploads/"):
        filepath = os.path.join(UPLOADS_DIR, os.path.basename(img.url))
        if os.path.exists(filepath):
            os.remove(filepath)
    db.delete(img)
    db.commit()


@router.patch("/releases/{release_id}/images/{image_id}/posicio")
def reorder_release_image(release_id: uuid.UUID, image_id: int, posicio: int, db: Session = Depends(get_db)):
    img = db.scalar(
        select(ReleaseImage).where(
            ReleaseImage.id == image_id, ReleaseImage.release_id == release_id
        )
    )
    if img is None:
        raise HTTPException(404, "Imatge no trobada")
    img.posicio = posicio
    db.commit()
    return {"id": img.id, "posicio": img.posicio}


# --- Properament (pre-venda) ---

@router.patch("/releases/{release_id}/properament")
def set_properament(
    release_id: uuid.UUID,
    properament: bool,
    data_disponibilitat: str | None = None,
    db: Session = Depends(get_db),
):
    from datetime import date
    release = db.get(Release, release_id)
    if release is None:
        raise HTTPException(404, "Release no trobat")
    release.properament = properament
    if data_disponibilitat:
        release.data_disponibilitat = date.fromisoformat(data_disponibilitat)
    elif not properament:
        release.data_disponibilitat = None
    db.commit()
    return {"properament": release.properament, "data_disponibilitat": release.data_disponibilitat}


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
        db.query(Release).filter(Release.id != release_id).update({"esta_sonant": False})
    release.esta_sonant = esta_sonant
    db.commit()
    db.refresh(release)
    return {"esta_sonant": release.esta_sonant}


# --- Blog ---

class PostIn(BaseModel):
    slug: str
    titulo: str
    contenido: str
    idioma: str = "ca"
    publicado_at: str | None = None
    pagina_ids: list[int] = []  # pàgines a les que pertany


def _post_admin_out(post: Post) -> dict:
    return {
        "slug": post.slug,
        "titulo": post.titulo,
        "contenido": post.contenido,
        "idioma": post.idioma,
        "publicado_at": post.publicado_at.isoformat() if post.publicado_at else None,
        "created_at": post.created_at.isoformat(),
        "pagines": [{"id": p.id, "slug": p.slug, "nom": p.nom} for p in post.pagines],
    }


def _sync_pagines(db: Session, post: Post, pagina_ids: list[int]):
    """Actualitza la relació M2M post ↔ pagines."""
    db.execute(
        __import__('sqlalchemy', fromlist=['delete']).delete(PostPagina).where(PostPagina.post_id == post.id)
    )
    for pid in pagina_ids:
        db.add(PostPagina(post_id=post.id, pagina_id=pid))


@router.get("/posts")
def admin_list_posts(q: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Post).options(selectinload(Post.pagines)).order_by(Post.created_at.desc())
    if q:
        stmt = stmt.where(Post.titulo.ilike(f"%{q}%"))
    return [_post_admin_out(p) for p in db.scalars(stmt).all()]


@router.get("/posts/{slug}")
def admin_get_post(slug: str, db: Session = Depends(get_db)):
    post = db.scalar(select(Post).options(selectinload(Post.pagines)).where(Post.slug == slug))
    if post is None:
        raise HTTPException(404, "Post no trobat")
    return _post_admin_out(post)


@router.post("/posts", status_code=201)
def admin_create_post(payload: PostIn, db: Session = Depends(get_db)):
    from datetime import datetime
    if db.scalar(select(Post).where(Post.slug == payload.slug)):
        raise HTTPException(409, "Ja existeix un post amb aquest slug")
    pub = datetime.fromisoformat(payload.publicado_at) if payload.publicado_at else None
    post = Post(slug=payload.slug, titulo=payload.titulo, contenido=sanitize_rich_html(payload.contenido),
                idioma=payload.idioma, publicado_at=pub)
    db.add(post)
    db.flush()
    _sync_pagines(db, post, payload.pagina_ids)
    db.commit()
    db.refresh(post)
    return _post_admin_out(post)


@router.put("/posts/{slug}")
def admin_update_post(slug: str, payload: PostIn, db: Session = Depends(get_db)):
    from datetime import datetime
    post = db.scalar(select(Post).options(selectinload(Post.pagines)).where(Post.slug == slug))
    if post is None:
        raise HTTPException(404, "Post no trobat")
    if payload.slug != slug and db.scalar(select(Post).where(Post.slug == payload.slug)):
        raise HTTPException(409, "Ja existeix un post amb el nou slug")
    post.slug = payload.slug
    post.titulo = payload.titulo
    post.contenido = sanitize_rich_html(payload.contenido)
    post.idioma = payload.idioma
    post.publicado_at = datetime.fromisoformat(payload.publicado_at) if payload.publicado_at else None
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


# --- Agenda ---

class EventIn(BaseModel):
    titulo: str
    descripcion: str | None = None
    fecha: str  # ISO datetime
    lugar: str = "Ultra-Local Records, Pujades 113, Barcelona"
    link: str | None = None


class EventAdminOut(BaseModel):
    id: uuid.UUID
    titulo: str
    descripcion: str | None
    fecha: str
    lugar: str
    link: str | None
    created_at: str

    model_config = {"from_attributes": True}


@router.get("/events", response_model=list[EventAdminOut])
def admin_list_events(upcoming_only: bool = False, db: Session = Depends(get_db)):
    from datetime import datetime, timezone
    stmt = select(Event).order_by(Event.fecha.desc())
    if upcoming_only:
        stmt = stmt.where(Event.fecha >= datetime.now(timezone.utc))
    events = db.scalars(stmt).all()
    return [
        EventAdminOut(
            id=e.id, titulo=e.titulo, descripcion=e.descripcion,
            fecha=e.fecha.isoformat(), lugar=e.lugar, link=e.link,
            created_at=e.created_at.isoformat(),
        )
        for e in events
    ]


@router.post("/events", status_code=201, response_model=EventAdminOut)
def admin_create_event(payload: EventIn, db: Session = Depends(get_db)):
    from datetime import datetime
    event = Event(
        titulo=payload.titulo,
        descripcion=payload.descripcion,
        fecha=datetime.fromisoformat(payload.fecha),
        lugar=payload.lugar,
        link=payload.link,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return EventAdminOut(
        id=event.id, titulo=event.titulo, descripcion=event.descripcion,
        fecha=event.fecha.isoformat(), lugar=event.lugar, link=event.link,
        created_at=event.created_at.isoformat(),
    )


@router.put("/events/{event_id}", response_model=EventAdminOut)
def admin_update_event(event_id: uuid.UUID, payload: EventIn, db: Session = Depends(get_db)):
    from datetime import datetime
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(404, "Esdeveniment no trobat")
    event.titulo = payload.titulo
    event.descripcion = payload.descripcion
    event.fecha = datetime.fromisoformat(payload.fecha)
    event.lugar = payload.lugar
    event.link = payload.link
    db.commit()
    db.refresh(event)
    return EventAdminOut(
        id=event.id, titulo=event.titulo, descripcion=event.descripcion,
        fecha=event.fecha.isoformat(), lugar=event.lugar, link=event.link,
        created_at=event.created_at.isoformat(),
    )


@router.delete("/events/{event_id}", status_code=204)
def admin_delete_event(event_id: uuid.UUID, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(404, "Esdeveniment no trobat")
    db.delete(event)
    db.commit()


# --- Pàgines CMS ---

class PaginaIn(BaseModel):
    slug: str
    nom: str
    tipus: str = "llista-posts"  # 'llista-posts' | 'estatica' | 'agenda'
    posicio: int = 0
    visible_menu: bool = True
    contingut: str | None = None


@router.get("/pagines")
def admin_list_pagines(db: Session = Depends(get_db)):
    return [
        {
            "id": p.id, "slug": p.slug, "nom": p.nom, "tipus": p.tipus,
            "posicio": p.posicio, "visible_menu": p.visible_menu,
            "contingut": p.contingut,
        }
        for p in db.scalars(select(Pagina).order_by(Pagina.posicio)).all()
    ]


@router.post("/pagines", status_code=201)
def admin_create_pagina(payload: PaginaIn, db: Session = Depends(get_db)):
    if db.scalar(select(Pagina).where(Pagina.slug == payload.slug)):
        raise HTTPException(409, "Ja existeix una pàgina amb aquest slug")
    data = payload.model_dump()
    data["contingut"] = sanitize_rich_html(data["contingut"])
    pagina = Pagina(**data)
    db.add(pagina)
    db.commit()
    db.refresh(pagina)
    return {"id": pagina.id, "slug": pagina.slug, "nom": pagina.nom, "tipus": pagina.tipus,
            "posicio": pagina.posicio, "visible_menu": pagina.visible_menu}


@router.put("/pagines/{pagina_id}")
def admin_update_pagina(pagina_id: int, payload: PaginaIn, db: Session = Depends(get_db)):
    pagina = db.get(Pagina, pagina_id)
    if pagina is None:
        raise HTTPException(404, "Pàgina no trobada")
    if payload.slug != pagina.slug and db.scalar(select(Pagina).where(Pagina.slug == payload.slug)):
        raise HTTPException(409, "Ja existeix una pàgina amb aquest slug")
    for k, v in payload.model_dump().items():
        setattr(pagina, k, sanitize_rich_html(v) if k == "contingut" else v)
    db.commit()
    db.refresh(pagina)
    return {"id": pagina.id, "slug": pagina.slug, "nom": pagina.nom, "tipus": pagina.tipus,
            "posicio": pagina.posicio, "visible_menu": pagina.visible_menu}


@router.delete("/pagines/{pagina_id}", status_code=204)
def admin_delete_pagina(pagina_id: int, db: Session = Depends(get_db)):
    pagina = db.get(Pagina, pagina_id)
    if pagina is None:
        raise HTTPException(404, "Pàgina no trobada")
    db.delete(pagina)
    db.commit()


@router.patch("/pagines/reorder")
def admin_reorder_pagines(order: list[dict], db: Session = Depends(get_db)):
    """Rep [{id, posicio}, ...] i actualitza l'ordre del menú."""
    for item in order:
        pagina = db.get(Pagina, item["id"])
        if pagina:
            pagina.posicio = item["posicio"]
    db.commit()
    return {"ok": True}
