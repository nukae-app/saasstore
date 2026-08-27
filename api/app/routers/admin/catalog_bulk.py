import csv
import io
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from ...database import get_db
from ...models import CondicionItem, Item, ItemStatus, OrderItem
from ...schemas import CatalogAgingItemsOut, CatalogAgingOut
from ...services.discogs_sync import remove_item_from_discogs
from ...services.security import require_admin
from ...tenant_secrets import get_tenant_secrets

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


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
            "item_id": i.id, "release_id": r.id, "artista": r.artista, "titulo": r.title,
            "discogs_release_id": r.discogs_release_id or "",
            "sello": r.sello or "", "formato": r.formato or "", "anio": r.anio or "",
            "genero": r.genero or "",
            "precio": i.price, "condicion": i.condition,
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


_CSV_ITEM_FIELD_TO_ATTR = {"precio": "price", "condicion": "condition"}


def _item_field_changes(item: Item, row: dict) -> dict:
    """Camps d'item (preu/condició/grading) que difereixen del que hi ha al CSV."""
    changes = {}
    for field in CATALOG_CSV_ITEM_FIELDS:
        value = _row_value(row, field)
        if value is None:
            continue
        new_value = Decimal(value) if field == "precio" else value
        attr = _CSV_ITEM_FIELD_TO_ATTR.get(field, field)
        if getattr(item, attr) != new_value:
            changes[attr] = new_value
    return changes


def _apply_release_changes(release, row: dict) -> bool:
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
                remove_item_from_discogs(get_tenant_secrets(item.tenant_id).discogs_token, item.codi_discogs)
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
            or_(Item.condition != CondicionItem.nou, Item.quantity > Item.reserved_quantity),
        )
    ).all()

    ahora = datetime.now(timezone.utc)
    rows: list[tuple[Item, int | None]] = []
    for item in items:
        if item.entry_date is None:
            rows.append((item, None))
            continue
        fecha_entrada = item.entry_date
        if fecha_entrada.tzinfo is None:  # SQLite (tests) no conserva la timezone
            fecha_entrada = fecha_entrada.replace(tzinfo=timezone.utc)
        rows.append((item, max(0, (ahora - fecha_entrada).days)))
    return rows


def _aging_item_out(item: Item, dias: int | None) -> dict:
    return {
        "item_id": item.id,
        "release_id": item.release_id,
        "artista": item.release.artista,
        "titulo": item.release.title,
        "imagen_url": item.release.image_url,
        "dias": dias,
        "fecha_entrada": item.entry_date,
        "precio": item.price,
        "coste": item.acquisition_cost,
        "condicion": item.condition,
        "origen": "compra" if item.compra_id else ("discogs" if item.codi_discogs else "desconegut"),
    }


@router.get("/catalog/aging", response_model=CatalogAgingOut)
def catalog_aging(db: Session = Depends(get_db)):
    """Antiguitat de l'estoc disponible (dies des de fecha_entrada) per detectar
    còpies que porten molt de temps sense vendre's i decidir rebaixes/promocions.
    fecha_entrada ve de Compra.date (entrades via ERP) o del "posted" de Discogs
    (estoc anterior a l'app, sincronitzat per scripts.sync_discogs_inventory)."""
    rows = _aging_dias_disponibles(db)

    con_fecha = [(i, d) for i, d in rows if d is not None]
    sin_fecha_rows = [i for i, d in rows if d is None]

    # i.price/i.acquisition_cost son por unidad: una línea nou representa
    # i.quantity unidades físicas, así que el valor real es price*quantity.
    valor_total = sum((i.price * i.quantity for i, _ in rows), Decimal("0"))
    coste_total = sum(((i.acquisition_cost or Decimal("0")) * i.quantity for i, _ in rows), Decimal("0"))
    valor_sin_fecha = sum((i.price * i.quantity for i in sin_fecha_rows), Decimal("0"))
    coste_sin_fecha = sum(((i.acquisition_cost or Decimal("0")) * i.quantity for i in sin_fecha_rows), Decimal("0"))

    buckets = []
    for key, label, lo, hi in _AGING_BUCKETS:
        en_bucket = [(i, d) for i, d in con_fecha if d >= lo and (hi is None or d <= hi)]
        buckets.append({
            "key": key, "label": label,
            "count": len(en_bucket),
            "valor": sum((i.price * i.quantity for i, _ in en_bucket), Decimal("0")),
            "coste": sum(((i.acquisition_cost or Decimal("0")) * i.quantity for i, _ in en_bucket), Decimal("0")),
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
