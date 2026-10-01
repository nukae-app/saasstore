"""Copias de seguridad y restauración del CATÁLOGO de un tenant (nunca de toda la base de datos).

Una copia es una foto, comprimida, de las tablas del catálogo de ese tenant: `releases`, `release_records`,
`items`, `record_stock_details` (vínculo con Discogs) y `channel_listings`. Se hace a demanda y, sola,
antes de las operaciones que cambian el catálogo en bloque (carga inicial, reprecio masivo) y antes de
restaurar (para poder deshacer la propia restauración).

RESTAURAR no es "pisar todo con la foto": primero se calcula EXACTAMENTE qué cambiaría (filas a insertar, a
actualizar —con el valor actual y el de la copia— y a borrar) y se enseña. Y nunca toca lo que ya no es
seguro tocar: un item que se ha vendido, está reservado o tiene pedidos, devoluciones, peticiones o
asignaciones POSTERIORES a la copia se salta y se lista como conflicto (si no, volvería a ponerse a la venta
algo ya vendido). Lo que sí se aplica se hace en una sola transacción: o entra todo o no entra nada."""

import gzip
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
import enum

import sqlalchemy as sa
from sqlalchemy import delete, insert, select, update
from sqlalchemy.orm import Session

from ..models import (
    CHANNEL_DISCOGS, Assignacio, CartItem, ChannelBackup, ChannelListing, DevolucionCompra, DevolucionVenta, Item,
    ItemStatus, Order, OrderItem, PeticionCliente, RecordProduct, RecordStockDetail, Release, SolicitudCompraLinea,
    StockHold, VentaExterna,
)
from ..models.channels import BACKUP_CATALOG
from .channel_events import record_event

log = logging.getLogger(__name__)

# Orden de inserción (padres antes que hijos); el de borrado es el inverso.
TABLES = ["releases", "release_records", "items", "record_stock_details", "channel_listings"]
MODELS = {
    "releases": Release, "release_records": RecordProduct, "items": Item,
    "record_stock_details": RecordStockDetail, "channel_listings": ChannelListing,
}
PK = {"releases": "id", "release_records": "release_id", "items": "id", "record_stock_details": "item_id", "channel_listings": "id"}
# Columna que apunta al item (para saltar los hijos de un item en conflicto)
ITEM_COL = {"items": "id", "record_stock_details": "item_id", "channel_listings": "item_id"}
# Columnas con restricción de unicidad que pueden cambiar de dueño (se anulan antes de reasignar)
UNIQUE_MOVABLE = {"record_stock_details": ["codi_discogs"], "channel_listings": ["external_id"]}
IGNORED_IN_DIFF = {"updated_at"}  # cambia sola en cada UPDATE: no es una diferencia real
AUTO_KEEP = 15  # copias automáticas que se conservan por tenant (las manuales no se borran solas)
SAMPLE_LIMIT = 60
CHUNK = 500


class RestoreError(Exception):
    """La restauración no se ha podido aplicar (no se ha cambiado nada)."""


# --- (de)serialización según el tipo de columna ----------------------------------------------

def _ser(value):
    if isinstance(value, enum.Enum):
        return value.value
    if value is None or isinstance(value, (bool, int, float, str, list, dict)):
        return value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _de(column, value):
    if value is None:
        return None
    t = column.type
    if isinstance(t, sa.Uuid):
        return uuid.UUID(value)
    if isinstance(t, sa.DateTime):
        return datetime.fromisoformat(value)
    if isinstance(t, sa.Date):
        return date.fromisoformat(value)
    if isinstance(t, sa.Float):
        return value
    if isinstance(t, sa.Numeric):
        return Decimal(value)
    if isinstance(t, sa.Enum) and t.enum_class is not None:
        return t.enum_class(value)
    return value


def _dump(db: Session, tenant_id, name: str) -> dict[str, dict]:
    """Filas actuales de una tabla del tenant, por clave primaria (como cadena), ya serializadas."""
    table = MODELS[name].__table__
    out = {}
    for row in db.execute(select(table).where(table.c.tenant_id == tenant_id)).mappings():
        data = {c.name: _ser(row[c.name]) for c in table.columns}
        out[str(data[PK[name]])] = data
    return out


# --- crear / leer copias ------------------------------------------------------------------------

def create_snapshot(db: Session, *, label: str | None = None, trigger: str = "manual", actor: str | None = None) -> ChannelBackup:
    """Guarda una foto del catálogo del tenant de la sesión. Hace flush, no commit."""
    tenant_id = db.info["tenant_id"]
    tables = {name: list(_dump(db, tenant_id, name).values()) for name in TABLES}
    raw = gzip.compress(json.dumps(
        {"version": 1, "taken_at": datetime.now(timezone.utc).isoformat(), "tables": tables},
        ensure_ascii=False, separators=(",", ":"),
    ).encode())
    backup = ChannelBackup(
        id=uuid.uuid4().hex, channel=CHANNEL_DISCOGS, kind=BACKUP_CATALOG, trigger=trigger, label=label,
        summary={name: len(rows) for name, rows in tables.items()}, size_bytes=len(raw), payload=raw,
        created_by=actor or "sistema",
    )
    db.add(backup)
    db.flush()
    _prune_automatic(db)
    return backup


def _prune_automatic(db: Session) -> None:
    antiguas = db.scalars(
        select(ChannelBackup).where(ChannelBackup.kind == BACKUP_CATALOG, ChannelBackup.trigger != "manual")
        .order_by(ChannelBackup.created_at.desc()).offset(AUTO_KEEP)
    ).all()
    for b in antiguas:
        db.delete(b)


def load_payload(backup: ChannelBackup) -> dict:
    return json.loads(gzip.decompress(backup.payload))


# --- plan de restauración -------------------------------------------------------------------------

@dataclass
class RestorePlan:
    inserts: dict[str, list[dict]] = field(default_factory=dict)
    updates: dict[str, list[tuple[dict, dict]]] = field(default_factory=dict)   # (fila de la copia, {col: [actual, copia]})
    deletes: dict[str, list[str]] = field(default_factory=dict)                 # pks actuales
    conflicts: list[dict] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)

    def counts(self) -> dict[str, dict[str, int]]:
        return {
            name: {"insert": len(self.inserts.get(name, [])), "update": len(self.updates.get(name, [])),
                   "delete": len(self.deletes.get(name, []))}
            for name in TABLES
        }

    def total(self) -> int:
        return sum(sum(c.values()) for c in self.counts().values())


def _chunks(seq, n=CHUNK):
    seq = list(seq)
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _item_blockers(db: Session, item_ids: set[str], taken_at: datetime | None) -> dict[str, str]:
    """Items que NO se pueden tocar y por qué. Con `taken_at`, solo cuenta lo posterior a la copia (ventas,
    devoluciones, peticiones...); con None (borrados), cualquier dependiente impide borrar. Las reservas
    actuales (estado reservado, carritos, retenciones) siempre bloquean."""
    ids = {uuid.UUID(i) for i in item_ids}
    reasons: dict[str, str] = {}

    def mark(rows, text):
        for (iid,) in rows:
            reasons.setdefault(str(iid), text)

    for chunk in _chunks(ids):
        oi = select(OrderItem.item_id).join(Order, Order.id == OrderItem.order_id).where(OrderItem.item_id.in_(chunk))
        if taken_at is not None:
            oi = oi.where(Order.created_at > taken_at)
        mark(db.execute(oi).all(), "té vendes o comandes" + (" posteriors a la còpia" if taken_at else ""))
        for model, col, text in (
            (VentaExterna, VentaExterna.item_id, "té vendes de mostrador"),
            (DevolucionVenta, DevolucionVenta.item_id, "té devolucions de venda"),
            (DevolucionCompra, DevolucionCompra.item_id, "té devolucions de compra"),
            (PeticionCliente, PeticionCliente.item_id, "té peticions de client"),
            (Assignacio, Assignacio.item_id, "té assignacions"),
            (SolicitudCompraLinea, SolicitudCompraLinea.item_resuelto_id, "està en una sol·licitud de compra"),
        ):
            stmt = select(col).where(col.in_(chunk))
            if taken_at is not None:
                stmt = stmt.where(model.created_at > taken_at)
            mark(db.execute(stmt).all(), text + (" posteriors a la còpia" if taken_at else ""))
        mark(db.execute(select(StockHold.item_id).where(StockHold.item_id.in_(chunk))).all(), "té una retenció d'estoc activa")
        mark(db.execute(select(CartItem.item_id).where(CartItem.item_id.in_(chunk))).all(), "és en un carretó")
        mark(db.execute(select(Item.id).where(Item.id.in_(chunk), Item.status == ItemStatus.reservado)).all(), "està reservat")
    return reasons


def plan_restore(db: Session, backup: ChannelBackup) -> RestorePlan:
    """Calcula qué cambiaría restaurar esta copia. No modifica nada."""
    tenant_id = db.info["tenant_id"]
    payload = load_payload(backup)
    taken_at = datetime.fromisoformat(payload["taken_at"])
    snap = {name: {str(r[PK[name]]): r for r in payload["tables"].get(name, [])} for name in TABLES}
    cur = {name: _dump(db, tenant_id, name) for name in TABLES}
    plan = RestorePlan()

    # Etiquetas legibles ("artista — título") a partir de la copia y del estado actual
    titulos = {pk: r.get("title") for src in (snap["releases"], cur["releases"]) for pk, r in src.items()}
    artistas = {pk: r.get("artista") for src in (snap["release_records"], cur["release_records"]) for pk, r in src.items()}
    items_rel = {pk: r.get("release_id") for src in (snap["items"], cur["items"]) for pk, r in src.items()}

    def label(name: str, row: dict) -> str:
        rid = row["id"] if name == "releases" else row["release_id"] if name == "release_records" else items_rel.get(str(row.get(ITEM_COL.get(name, "id"))))
        if name == "channel_listings" and not rid:
            rid = items_rel.get(str(row.get("item_id")))
        titulo = titulos.get(str(rid)) or "—"
        art = artistas.get(str(rid))
        return f"{art} — {titulo}" if art else titulo

    candidates: dict[str, dict[str, str]] = {}   # item pk -> motivo (se rellena abajo)
    for name in TABLES:
        s, c = snap[name], cur[name]
        plan.inserts[name] = [s[pk] for pk in s if pk not in c]
        plan.deletes[name] = [pk for pk in c if pk not in s]
        ups = []
        for pk in s:
            if pk in c:
                changed = {
                    col: [c[pk].get(col), s[pk][col]] for col in s[pk]
                    if col not in IGNORED_IN_DIFF and c[pk].get(col) != s[pk][col]
                }
                if changed:
                    ups.append((s[pk], changed))
        plan.updates[name] = ups
        for row in plan.inserts[name]:
            plan.labels[f"{name}:{row[PK[name]]}"] = label(name, row)
        for pk in plan.deletes[name]:
            plan.labels[f"{name}:{pk}"] = label(name, c[pk])
        for row, _ in ups:
            plan.labels[f"{name}:{row[PK[name]]}"] = label(name, row)

    # Conflictos a nivel de item: los afectados (por actualizar o borrar) que ya no son seguros de tocar
    def item_of(name: str, row: dict) -> str | None:
        col = ITEM_COL.get(name)
        return str(row[col]) if col else None

    to_update = {item_of(n, r) for n in ITEM_COL for r, _ in plan.updates[n] if item_of(n, r)}
    to_delete = {pk if n == "items" else item_of(n, cur[n][pk]) for n in ITEM_COL for pk in plan.deletes[n]}
    blocked = _item_blockers(db, to_update - to_delete, taken_at) if to_update - to_delete else {}
    blocked.update(_item_blockers(db, to_delete, None) if to_delete else {})
    for iid, reason in blocked.items():
        row = cur["items"].get(iid) or snap["items"].get(iid) or {"id": iid}
        plan.conflicts.append({"table": "items", "pk": iid, "label": label("items", row), "reason": reason})

    # Quitar de las operaciones todo lo que cuelga de un item en conflicto
    for name in ITEM_COL:
        plan.updates[name] = [(r, ch) for r, ch in plan.updates[name] if item_of(name, r) not in blocked]
        plan.deletes[name] = [pk for pk in plan.deletes[name]
                              if (pk if name == "items" else item_of(name, cur[name][pk])) not in blocked]
    # No se borra una release que aún tiene items (porque alguno quedó en conflicto)
    sobreviven = {r["release_id"] for r in cur["items"].values() if r["id"] not in set(plan.deletes["items"])}
    for name in ("releases", "release_records"):
        guardadas = []
        for pk in plan.deletes[name]:
            rid = pk
            if rid in sobreviven:
                plan.conflicts.append({"table": name, "pk": pk, "label": label(name, cur[name][pk]),
                                       "reason": "encara té items que no es poden restaurar"})
            else:
                guardadas.append(pk)
        plan.deletes[name] = guardadas
    return plan


def preview(db: Session, backup: ChannelBackup) -> dict:
    plan = plan_restore(db, backup)
    sample = []
    for name in ("items", "releases", "release_records", "record_stock_details", "channel_listings"):
        for op, rows in (("update", [r for r, _ in plan.updates[name]]), ("insert", plan.inserts[name]),
                         ("delete", [{PK[name]: pk} for pk in plan.deletes[name]])):
            for row in rows:
                if len(sample) >= SAMPLE_LIMIT:
                    break
                key = f"{name}:{row[PK[name]]}"
                changes = dict(next((ch for r, ch in plan.updates[name] if r[PK[name]] == row[PK[name]]), {})) if op == "update" else None
                if changes is not None:
                    changes = {k: v for k, v in list(changes.items())[:6]}
                sample.append({"table": name, "op": op, "label": plan.labels.get(key, "—"), "changes": changes})
    return {
        "counts": plan.counts(), "total_changes": plan.total(), "conflicts": plan.conflicts[:200],
        "conflicts_total": len(plan.conflicts), "sample": sample,
        "backup": {"id": backup.id, "label": backup.label, "created_at": backup.created_at, "summary": backup.summary},
    }


# --- restauración ---------------------------------------------------------------------------------

def restore(db: Session, backup: ChannelBackup, *, actor: str | None = None) -> dict:
    """Restaura el catálogo al estado de la copia (salvo los conflictos). Antes guarda una copia automática del
    estado actual; después todo ocurre en una sola transacción."""
    plan = plan_restore(db, backup)
    if plan.total() == 0:
        return {"restored": False, "message": "El catàleg ja coincideix amb la còpia: no hi ha res a restaurar.",
                "conflicts": plan.conflicts}

    nombre = backup.label or backup.created_at.strftime("%Y-%m-%d %H:%M")
    previa = create_snapshot(db, label=f"Abans de restaurar «{nombre}»", trigger="pre_restore", actor=actor)
    db.commit()  # la copia previa queda aunque la restauración falle

    tenant_id = db.info["tenant_id"]
    try:
        _apply(db, plan, tenant_id)
        record_event(db, "restore", "ok", actor=actor, detail={
            "backup": backup.id, "counts": plan.counts(), "conflictes": len(plan.conflicts), "copia_previa": previa.id,
        })
        db.commit()
    except Exception as exc:  # noqa: BLE001 — atómico: nada a medias
        db.rollback()
        log.warning("catalog_backup: la restauración ha fallado", exc_info=True)
        raise RestoreError(f"No s'ha pogut restaurar (no s'ha canviat res): {exc}") from exc
    db.expire_all()
    return {"restored": True, "counts": plan.counts(), "conflicts": plan.conflicts, "copia_previa": previa.id}


def _apply(db: Session, plan: RestorePlan, tenant_id) -> None:
    def tbl(name):
        return MODELS[name].__table__

    def rows(name, items):
        t = tbl(name)
        return [{c.name: _de(c, r[c.name]) for c in t.columns} for r in items]

    def delete_rows(name, pks):
        t, pk_col = tbl(name), tbl(name).c[PK[name]]
        for chunk in _chunks(pks):
            vals = [_de(pk_col, v) for v in chunk]
            db.execute(delete(t).where(t.c.tenant_id == tenant_id, pk_col.in_(vals)))

    # 1) borrar lo creado después (hijos antes que padres)
    for name in reversed(TABLES):
        delete_rows(name, plan.deletes.get(name, []))
    # 2) reinsertar padres borrados
    for name in ("releases", "release_records"):
        if plan.inserts.get(name):
            db.execute(insert(tbl(name)), rows(name, plan.inserts[name]))
    # 3) actualizar. Los códigos únicos que cambian de dueño se anulan primero para no chocar entre sí.
    for name, cols in UNIQUE_MOVABLE.items():
        t = tbl(name)
        for r, changed in plan.updates.get(name, []):
            nulos = {c: None for c in cols if c in changed}
            if nulos:
                db.execute(update(t).where(t.c.tenant_id == tenant_id, t.c[PK[name]] == _de(t.c[PK[name]], r[PK[name]])).values(**nulos))
    for name in TABLES:
        t = tbl(name)
        for r, changed in plan.updates.get(name, []):
            values = {c.name: _de(c, r[c.name]) for c in t.columns if c.name in changed}
            db.execute(update(t).where(t.c.tenant_id == tenant_id, t.c[PK[name]] == _de(t.c[PK[name]], r[PK[name]])).values(**values))
    # 4) reinsertar items y sus hijos borrados
    for name in ("items", "record_stock_details", "channel_listings"):
        if plan.inserts.get(name):
            db.execute(insert(tbl(name)), rows(name, plan.inserts[name]))
