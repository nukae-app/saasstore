"""Sincronització amb el Marketplace de Discogs.

Events que disparen accions:
- Item creat (POST /admin/items): si el release té discogs_release_id → push listing
- Item venut (checkout/confirm o venta_externa): si té codi_discogs → delete listing
- Venda feta directament al Marketplace de Discogs: pull periòdic de comandes (sync_discogs_orders)
  que crea/actualitza Order+OrderItem amb origen='discogs' — mateix model que les vendes web.
- Quan marquem una comanda d'origen Discogs com "enviado": push de l'estat + seguiment cap a Discogs.
- Release vinculat a Discogs (a mà des de l'admin, o pel script find_discogs_matches):
  enrich_release_from_discogs porta tracklist, crèdits i altres metadades.

Les crides són best-effort: un error de Discogs no bloqueja l'operació local.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    ChannelEvent, CondicionItem, ConfiguracioBotiga, Item, ItemStatus, Order, OrderItem, OrderOrigen, OrderStatus,
    RecordStockDetail, Release, TenantFeature,
)
from ..config import get_settings
from ..tenant_secrets import TenantSecrets, get_tenant_secrets
from .channel_alerts import raise_alert
from .channel_events import record_event
from .channel_listings import was_published
from .channel_settings import auto_publish_allowed
from .discogs import ReadOnlyToken, _client, _throttle, get_release, is_read_only
from .iva import compute_iva_venda


def resolve_discogs_token(secrets: TenantSecrets) -> str | None:
    """Token de Discogs efectiu del tenant: `discogs_token_prod` o
    `discogs_token_dev` segons `Settings.discogs_token_env`, i si aquell camp
    no hi és, el `discogs_token` antic."""
    specific = secrets.discogs_token_dev if get_settings().discogs_token_env == "dev" else secrets.discogs_token_prod
    return specific or secrets.discogs_token


def get_discogs_token_if_enabled(db: Session, tenant_id: uuid.UUID) -> str | None:
    """Punto único de decisión (Fase 4, sección D): `discogs_habilitat`
    puede estar en False aunque el tenant tenga un `discogs_token` presente
    en secretos (p. ej. lo tuvo activo antes) — sin este chequeo, cualquier
    llamador que solo mirara el token seguiría sincronizando con Discogs
    pese al interruptor apagado. Las funciones de este módulo que reciben
    `token: str | None` ya hacen `if not token: return` sin más, así que
    sustituir aquí `get_tenant_secrets(...).discogs_token` por esta función
    basta para que todos esos call sites respeten el interruptor.

    Con `discogs_solo_lectura` activo (migración por pasos, docs/
    PLAN_CANAL_DISCOGS.md) devuelve un `ReadOnlyToken`: solo permite bajar
    datos de Discogs, cualquier escritura queda bloqueada."""
    config = db.scalar(select(ConfiguracioBotiga))
    if not config or not config.discogs_habilitat:
        return None
    token = resolve_discogs_token(get_tenant_secrets(tenant_id))
    if token and config.discogs_solo_lectura:
        return ReadOnlyToken(token)
    return token

log = logging.getLogger(__name__)

# Marca per tenant: la primera sincronització "Discogs mana" (scripts/
# sync_discogs_inventory.py) ja s'ha fet. A partir d'aquí la font de veritat
# d'estoc i preus és l'app (docs/PLAN_CANAL_DISCOGS.md §8) i aquell mode no
# es pot relançar sense una confirmació explícita. Es guarda a `tenant_features`
# (clau lliure en codi, sense migració); `config` porta data i resum.
ADOPCIO_FEATURE_KEY = "discogs_adopcio_feta"


def adopcio_feta(db: Session) -> dict | None:
    """Dades de la marca d'adopció del tenant de la sessió, o None si encara no s'ha fet."""
    feature = db.scalar(select(TenantFeature).where(TenantFeature.feature_key == ADOPCIO_FEATURE_KEY))
    if feature is None or not feature.enabled:
        return None
    return feature.config or {}


def marcar_adopcio_feta(db: Session, resum: dict) -> None:
    """Registra (sense fer commit) que l'adopció inicial s'ha completat."""
    config = {"fet_el": datetime.now(timezone.utc).isoformat(), **resum}
    feature = db.scalar(select(TenantFeature).where(TenantFeature.feature_key == ADOPCIO_FEATURE_KEY))
    if feature is None:
        db.add(TenantFeature(feature_key=ADOPCIO_FEATURE_KEY, enabled=True, config=config))
    else:
        feature.enabled = True
        feature.config = config

# Mapeig d'estat de comanda de Discogs (seller-side) → el nostre OrderStatus.
# No hi ha equivalent de "entregado" del costat venedor de Discogs: és un estat
# només intern nostre, i el pull mai el sobreescriu (vegeu sync_discogs_orders).
DISCOGS_ORDER_STATUS_MAP: dict[str, OrderStatus] = {
    "New Order": OrderStatus.pendiente_pago,
    "Buyer Contacted": OrderStatus.pendiente_pago,
    "Invoice Sent": OrderStatus.pendiente_pago,
    "Payment Pending": OrderStatus.pendiente_pago,
    "Payment Received": OrderStatus.pagado,
    # "In Progress": el vendedor ya está preparando el pedido (cobrado, aún sin enviar).
    # Estaba ausente del mapa y esos pedidos se ignoraban; ver docs/PLAN_CANAL_DISCOGS.md §2.
    "In Progress": OrderStatus.pagado,
    "Shipped": OrderStatus.enviado,
    "Refund Sent": OrderStatus.cancelado,
    "Cancelled (Non-Paying Buyer)": OrderStatus.cancelado,
    "Cancelled (Item Unavailable)": OrderStatus.cancelado,
    "Cancelled (Per Buyer's Request)": OrderStatus.cancelado,
    "Cancelled (Refund Requested)": OrderStatus.cancelado,
}
# Estats locals que el pull mai ha de tocar (decisió nostra, no de Discogs)
_TERMINAL_LOCAL_STATUSES = {OrderStatus.entregado, OrderStatus.cancelado}

# Mapeig de grading de Discogs (text) → codi de condició per a l'API
CONDITION_MAP: dict[str, str] = {
    "Mint (M)": "M",
    "Near Mint (NM or M-)": "NM",
    "Very Good Plus (VG+)": "VG+",
    "Very Good (VG)": "VG",
    "Good Plus (G+)": "G+",
    "Good (G)": "G",
    "Fair (F)": "F",
    "Poor (P)": "P",
}
# Prefix matching per si el grading porta text extra
_CONDITION_PREFIXES = [
    ("Mint", "M"),
    ("Near Mint", "NM"),
    ("Very Good Plus", "VG+"),
    ("Very Good", "VG"),
    ("Good Plus", "G+"),
    ("Good", "G"),
    ("Fair", "F"),
    ("Poor", "P"),
]


def _map_condition(grading: str | None) -> str:
    if not grading:
        return "VG+"
    code = CONDITION_MAP.get(grading.strip())
    if code:
        return code
    for prefix, code in _CONDITION_PREFIXES:
        if grading.strip().startswith(prefix):
            return code
    return "VG+"


def _listing_body(
    precio: float, release_discogs_id: int, estado_disco: str | None, estado_funda: str | None,
    notas: str | None, es_nou: bool,
) -> dict:
    """Cuerpo del listing (crear/editar). `es_nou=True` (stock agregado): Discogs no té un
    grading de "nou", el conveni del mercat és fer servir "Mint (M)" tant per al disc com per
    a la funda, sense comentaris de grading."""
    if es_nou:
        condition = sleeve = "M"
        comments_parts = [notas] if notas else []
    else:
        condition = _map_condition(estado_disco)
        sleeve = _map_condition(estado_funda) if estado_funda else condition
        comments_parts = []
        if estado_disco:
            comments_parts.append(f"Disc: {estado_disco}")
        if estado_funda:
            comments_parts.append(f"Funda: {estado_funda}")
        if notas:
            comments_parts.append(notas)
    return {
        "release_id": release_discogs_id,
        "condition": condition,
        "sleeve_condition": sleeve,
        "price": round(float(precio), 2),
        "status": "For Sale",
        "comments": " | ".join(comments_parts) or None,
    }


READ_ONLY_REASON = "mode només lectura"


def push_listing(
    token: str | None, item_id, release_discogs_id: int, precio: float, estado_disco: str | None,
    estado_funda: str | None, notas: str | None = None, es_nou: bool = False,
    *, db: Session | None = None, actor: str | None = None,
) -> tuple[int | None, str | None]:
    """Crea un listing al Marketplace. Retorna `(listing_id, error)`: `error` explica el
    fallo (o és None si ha anat bé / no hi havia token). Amb `db`, deixa constància al
    registre d'activitat (channel_events)."""
    if not token:
        log.warning("discogs_sync: sense token, no es pot fer push")
        return None, "sense token"
    body = _listing_body(precio, release_discogs_id, estado_disco, estado_funda, notas, es_nou)
    detalle = {"release_id": release_discogs_id, "price": body["price"]}
    if is_read_only(token):
        log.info("discogs_sync: mode només lectura, no es publica l'item %s", item_id)
        record_event(db, "publish", "skipped", item_id=item_id, actor=actor, detail={**detalle, "motiu": READ_ONLY_REASON})
        return None, READ_ONLY_REASON

    try:
        _throttle()
        with _client(token) as c:
            r = c.post("/marketplace/listings", json=body)
            if r.status_code in (400, 422):
                log.warning("discogs_sync push 4xx: %s — %s", r.status_code, r.text[:200])
                err = f"Discogs {r.status_code}: {r.text[:300]}"
                record_event(db, "publish", "error", item_id=item_id, actor=actor, detail=detalle, error=err)
                return None, err
            r.raise_for_status()
            listing_id = r.json().get("listing_id")
            log.info("discogs_sync: listing creat %s per item %s", listing_id, item_id)
            record_event(db, "publish", "ok", item_id=item_id, external_id=listing_id, actor=actor, detail=detalle)
            return listing_id, None
    except Exception as exc:
        log.warning("discogs_sync push error per item %s: %s", item_id, exc)
        record_event(db, "publish", "error", item_id=item_id, actor=actor, detail=detalle, error=str(exc))
        return None, str(exc)


def push_item_to_discogs(
    token: str | None,
    item_id,
    release_discogs_id: int,
    precio: float,
    estado_disco: str | None,
    estado_funda: str | None,
    notas: str | None = None,
    es_nou: bool = False,
    *,
    db: Session | None = None,
    actor: str | None = None,
) -> int | None:
    """Crea un listing al Marketplace de Discogs. Retorna el listing_id (codi_discogs) o None
    si falla (versió sense motiu de `push_listing`)."""
    return push_listing(
        token, item_id, release_discogs_id, precio, estado_disco, estado_funda, notas, es_nou, db=db, actor=actor,
    )[0]


def update_listing(
    token: str | None, listing_id: int, item_id, release_discogs_id: int, precio: float,
    estado_disco: str | None, estado_funda: str | None, notas: str | None = None, es_nou: bool = False,
    *, db: Session | None = None, actor: str | None = None,
) -> tuple[bool, str | None, bool]:
    """Edita un listing existent (preu i grading). Retorna `(ok, error, gone)`; `gone`=True
    si Discogs diu que el listing ja no existeix (404). Registra l'activitat si hi ha `db`."""
    if not token:
        return False, "sense token", False
    body = _listing_body(precio, release_discogs_id, estado_disco, estado_funda, notas, es_nou)
    detalle = {"release_id": release_discogs_id, "price": body["price"]}
    if is_read_only(token):
        record_event(db, "update", "skipped", item_id=item_id, external_id=listing_id, actor=actor,
                     detail={**detalle, "motiu": READ_ONLY_REASON})
        return False, READ_ONLY_REASON, False
    try:
        _throttle()
        with _client(token) as c:
            r = c.post(f"/marketplace/listings/{listing_id}", json=body)
            if r.status_code in (200, 204):
                record_event(db, "update", "ok", item_id=item_id, external_id=listing_id, actor=actor, detail=detalle)
                return True, None, False
            err = f"Discogs {r.status_code}: {r.text[:300]}"
            log.warning("discogs_sync update %s → %s", listing_id, r.status_code)
            record_event(db, "update", "error", item_id=item_id, external_id=listing_id, actor=actor,
                         detail=detalle, error=err)
            return False, err, r.status_code == 404
    except Exception as exc:
        log.warning("discogs_sync update error %s: %s", listing_id, exc)
        record_event(db, "update", "error", item_id=item_id, external_id=listing_id, actor=actor,
                     detail=detalle, error=str(exc))
        return False, str(exc), False


def remove_listing(
    token: str | None, codi_discogs: int, *, db: Session | None = None, item_id=None, actor: str | None = None,
) -> tuple[bool, str | None]:
    """Elimina un listing. Retorna `(ok, error)`; ok també si ja no existia (404)."""
    if not token:
        return False, "sense token"
    if is_read_only(token):
        log.info("discogs_sync: mode només lectura, no s'elimina el listing %s", codi_discogs)
        record_event(db, "remove", "skipped", item_id=item_id, external_id=codi_discogs, actor=actor,
                     detail={"motiu": READ_ONLY_REASON})
        return False, READ_ONLY_REASON
    try:
        _throttle()
        with _client(token) as c:
            r = c.delete(f"/marketplace/listings/{codi_discogs}")
            if r.status_code in (200, 204, 404):
                log.info("discogs_sync: listing %s eliminat", codi_discogs)
                record_event(db, "remove", "ok", item_id=item_id, external_id=codi_discogs, actor=actor,
                             detail={"http": r.status_code})
                return True, None
            log.warning("discogs_sync delete %s → %s", codi_discogs, r.status_code)
            err = f"Discogs {r.status_code}"
            record_event(db, "remove", "error", item_id=item_id, external_id=codi_discogs, actor=actor, error=err)
            return False, err
    except Exception as exc:
        log.warning("discogs_sync delete error %s: %s", codi_discogs, exc)
        record_event(db, "remove", "error", item_id=item_id, external_id=codi_discogs, actor=actor, error=str(exc))
        return False, str(exc)


def remove_item_from_discogs(
    token: str | None, codi_discogs: int, *, db: Session | None = None, item_id=None, actor: str | None = None,
) -> bool:
    """Elimina un listing del Marketplace de Discogs (disc venut o retirat). Retorna True si
    s'ha eliminat (o ja no existia), False si ha fallat."""
    return remove_listing(token, codi_discogs, db=db, item_id=item_id, actor=actor)[0]


def sync_stock_listing(db: Session, item: Item, token: str | None) -> None:
    """Mantiene el listing de Discogs de una línea `nou` en "stock virtual
    de 1": como mucho 1 listing activo mientras `item.quantity > 0`. Hay que
    llamarla después de CUALQUIER cambio de `item.quantity` en una línea nou
    (recepción, alta admin, venta TPV/web/club, devolución) — no se llama
    sola, no hay un trigger de BBDD para esto.

    No hace nada si el release no está vinculado a Discogs (no hay
    `codi_discogs` que gestionar) o si el item no es `nou`."""
    if item.condition != CondicionItem.nou:
        return
    if is_read_only(token):
        # Sin tocar `codi_discogs`: borrar el vínculo local con el listing
        # aún vivo en Discogs dejaría un listing huérfano.
        return
    if item.quantity <= 0:
        if item.codi_discogs:
            remove_item_from_discogs(token, item.codi_discogs, db=db, item_id=item.id)
            item.codi_discogs = None
        return

    # Se busca por release_id (no vía item.release) para funcionar también
    # con un Item recién creado/todavía sin flush, donde la relación
    # perezosa no siempre resuelve.
    release = db.get(Release, item.release_id)
    if item.codi_discogs is None and release is not None and release.discogs_release_id:
        # Publicación manual (por defecto): un item que NUNCA se ha publicado queda "pendent" en el
        # centro de control hasta que se apruebe. Reponer el listing de una línea que ya se
        # publicó antes (p. ej. tras una venta en Discogs) sí es automático: es continuidad.
        if not auto_publish_allowed(db) and not was_published(db, item.id):
            return
        listing_id = push_item_to_discogs(
            token,
            item_id=item.id,
            release_discogs_id=release.discogs_release_id,
            precio=float(item.price),
            estado_disco=None,
            estado_funda=None,
            es_nou=True,
            db=db,
        )
        if listing_id:
            item.codi_discogs = listing_id


# ---------------------------------------------------------------------------
# Comandes del Marketplace (pull: Discogs → nosaltres)
# ---------------------------------------------------------------------------

def fetch_open_discogs_orders(
    token: str | None, since: datetime | None = None, *, raise_errors: bool = False, max_pages: int = 40,
    first_pull_days: int = 60,
) -> list[dict]:
    """Llista les comandes del Marketplace (com a venedors), de la de darrera activitat més recent
    a la més antiga. Amb `since` és INCREMENTAL: s'atura en trobar una comanda amb activitat
    anterior (menys un marge) en comptes de recórrer tot l'historial. Sense `since` (primera
    vegada) només demana les dels darrers `first_pull_days` dies.

    Per defecte és best-effort (un 5xx puntual retorna llista buida i deixa traça al log);
    amb `raise_errors=True` propaga l'excepció, perquè el sondeig programat la pugui registrar."""
    if not token:
        return []
    orders: list[dict] = []
    params: dict = {"per_page": 50, "sort": "last_activity", "sort_order": "desc"}
    if since is None:
        params["created_after"] = (datetime.now(timezone.utc) - timedelta(days=first_pull_days)).date().isoformat()
    stop_before = since - timedelta(minutes=15) if since is not None else None
    try:
        page = 1
        while page <= max_pages:
            _throttle()
            with _client(token) as c:
                r = c.get("/marketplace/orders", params={**params, "page": page})
                r.raise_for_status()
                data = r.json()
            batch = data.get("orders", [])
            orders.extend(batch)
            if stop_before is not None and batch:
                last = _parse_iso(batch[-1].get("last_activity"))
                if last is not None and last < stop_before:
                    break
            if page >= (data.get("pagination") or {}).get("pages", 1):
                break
            page += 1
    except Exception as exc:
        if raise_errors:
            raise
        log.warning("discogs_sync: error llistant comandes: %s", exc)
    return orders


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _event_exists(db: Session, action: str, external_id: str, kind: str) -> bool:
    """Evita registrar cada ciclo del sondeo la misma incidencia (p. ej. un pedido sin coincidencia)."""
    for e in db.scalars(select(ChannelEvent).where(ChannelEvent.action == action, ChannelEvent.external_id == external_id)):
        if (e.detail or {}).get("kind") == kind:
            return True
    return False


def sync_discogs_orders(db: Session, token: str | None, orders: list[dict] | None = None) -> dict:
    """Pull de comandes del Marketplace: crea/actualitza Order+OrderItem amb origen='discogs'.

    Idempotent per discogs_order_id. Mai sobreescriu un estat local terminal
    (entregado/cancelado) amb el que digui Discogs — això és decisió nostra, no seva.
    `orders`: les comandes ja descarregades (sondeig incremental); si és None, les baixa totes.

    Les incidències queden al registre d'activitat (una sola vegada per cas): comanda SENSE
    coincidència amb cap item local, CONFLICTE (ven un item que ja no estava a la venda a
    l'app) i estat de comanda desconegut."""
    creats = actualitzats = sense_match = errors = conflictes = 0
    nous_pedidos: list[dict] = []
    estats_desconeguts: list[str] = []
    sense_match_ids: list[str] = []

    if orders is None:
        orders = fetch_open_discogs_orders(token)

    for raw in orders:
        discogs_id = str(raw.get("id"))
        discogs_status = raw.get("status", "")
        nou_status = DISCOGS_ORDER_STATUS_MAP.get(discogs_status)
        if nou_status is None:
            log.warning("discogs_sync: estat de comanda desconegut '%s' (ordre %s)", discogs_status, discogs_id)
            estats_desconeguts.append(discogs_status)
            if not _event_exists(db, "order_pull", discogs_id, f"estat_desconegut:{discogs_status}"):
                record_event(db, "order_pull", "skipped", external_id=discogs_id,
                             detail={"kind": f"estat_desconegut:{discogs_status}", "status": discogs_status})
                raise_alert(
                    db, "order_status_unknown", f"status:{discogs_status}",
                    f"Estat de comanda desconegut a Discogs: '{discogs_status}' (comanda {discogs_id}). "
                    "Cal afegir-lo al mapeig d'estats.", external_id=discogs_id, detail={"status": discogs_status},
                )
                db.commit()
            continue

        existing = db.scalar(select(Order).where(Order.discogs_order_id == discogs_id))
        if existing:
            if existing.status not in _TERMINAL_LOCAL_STATUSES and existing.status != nou_status:
                existing.status = nou_status
                db.commit()
                actualitzats += 1
            continue

        # Nova comanda: localitzar els items pels listing id (codi_discogs)
        raw_items = raw.get("items", [])
        listing_ids = [it.get("id") for it in raw_items if it.get("id")]
        items = (
            db.scalars(
                select(Item)
                .join(RecordStockDetail, RecordStockDetail.item_id == Item.id)
                .where(RecordStockDetail.codi_discogs.in_(listing_ids))
            ).all()
            if listing_ids
            else []
        )
        if not items:
            log.warning("discogs_sync: comanda %s sense items locals coincidents (listings %s)", discogs_id, listing_ids)
            sense_match += 1
            sense_match_ids.append(discogs_id)
            if not _event_exists(db, "order_pull", discogs_id, "sense_match"):
                record_event(
                    db, "order_pull", "error", external_id=discogs_id,
                    detail={"kind": "sense_match", "listings": listing_ids,
                            "buyer": (raw.get("buyer") or {}).get("username"),
                            "total": (raw.get("total") or {}).get("value")},
                    error="Comanda de Discogs sense cap item local coincident",
                )
                raise_alert(
                    db, "order_sense_match", f"order:{discogs_id}:sense_match",
                    f"Comanda {discogs_id} de Discogs sense cap item coincident a l'app (listings {listing_ids}).",
                    severity="error", external_id=discogs_id,
                    detail={"listings": listing_ids, "buyer": (raw.get("buyer") or {}).get("username")},
                )
                db.commit()
            continue

        try:
            # Conflicto: Discogs vende algo que la app ya no tenía a la venta (vendido en la web o en
            # tienda a la vez). El pedido se crea igualmente, pero queda constancia para revisarlo.
            no_disponibles = [str(i.id) for i in items if not _was_sellable(i)]
            buyer = (raw.get("buyer") or {}).get("username")
            total_raw = (raw.get("total") or {}).get("value")
            total = Decimal(str(total_raw)) if total_raw is not None else sum((i.price for i in items), Decimal("0"))
            order = Order(
                contact_email=f"{buyer or 'comprador'}@discogs-buyer.local",
                status=nou_status,
                total=total,
                shipping_method="envio",
                shipping_address={"raw": raw.get("shipping_address")} if raw.get("shipping_address") else None,
                origin=OrderOrigen.discogs,
                discogs_order_id=discogs_id,
                discogs_buyer=buyer,
            )
            db.add(order)
            db.flush()
            if no_disponibles:
                conflictes += 1
                record_event(
                    db, "order_pull", "error", order_id=order.id, external_id=discogs_id,
                    detail={"kind": "conflict", "items": no_disponibles, "buyer": buyer},
                    error="Discogs ha venut un item que ja no estava a la venda a l'app (possible doble venda)",
                )
                raise_alert(
                    db, "order_conflict", f"order:{discogs_id}:conflict",
                    f"Comanda {discogs_id} de Discogs: ha venut un item que ja no estava a la venda a l'app "
                    "(possible doble venda).", severity="error", order_id=order.id, external_id=discogs_id,
                    detail={"items": no_disponibles, "buyer": buyer},
                )
            for item in items:
                tipus_iva_id, iva_pct, iva_import = compute_iva_venda(item, item.price, db)
                db.add(OrderItem(
                    order_id=order.id, item_id=item.id, price=item.price, quantity=1,
                    condition=item.condition,
                    tipus_iva_id=tipus_iva_id, vat_pct=iva_pct, vat_amount=iva_import,
                ))
                if item.condition == CondicionItem.nou:
                    # "Stock virtual de 1": el listing vendido ya no existe en
                    # Discogs; se descuenta 1 unidad y, si queda stock, se
                    # publica un listing nuevo para mantener la regla.
                    item.quantity = max(0, item.quantity - 1)
                    item.codi_discogs = None
                    sync_stock_listing(db, item, token)
                elif item.status != ItemStatus.vendido:
                    item.status = ItemStatus.vendido
                    item.reserved_until = None
                    item.reserved_by_cart_id = None
            db.commit()
            creats += 1
            nous_pedidos.append({"id": discogs_id, "buyer": buyer, "total": float(total)})
        except Exception as exc:
            db.rollback()
            log.warning("discogs_sync: error creant comanda local per %s: %s", discogs_id, exc)
            errors += 1

    return {
        "creats": creats, "actualitzats": actualitzats, "sense_match": sense_match, "errors": errors,
        "conflictes": conflictes, "estats_desconeguts": sorted(set(estats_desconeguts)),
        "sense_match_ids": sense_match_ids[:50], "nous": nous_pedidos[:20],
    }


def _was_sellable(item: Item) -> bool:
    """¿Estaba el item realmente a la venta justo antes de aplicar este pedido de Discogs?"""
    from .channel_reconciler import is_sellable

    return is_sellable(item)


def push_shipped_status(
    token: str | None, discogs_order_id: str, numero_seguiment: str | None, transportista: str | None,
    *, db: Session | None = None, order_id=None, actor: str | None = None,
) -> bool:
    """Marca la comanda com "Shipped" a Discogs i hi deixa el número de seguiment com a missatge
    (Discogs no té un camp estructurat de tracking a l'API de comandes). Amb `db`, deixa
    constància al registre d'activitat (channel_events)."""
    if not token:
        return False
    if is_read_only(token):
        log.info("discogs_sync: mode només lectura, no es marca Shipped la comanda %s", discogs_order_id)
        record_event(db, "ship", "skipped", order_id=order_id, external_id=discogs_order_id, actor=actor,
                     detail={"motiu": "mode només lectura"})
        return False
    missatge = None
    if numero_seguiment:
        missatge = f"Enviat. Seguiment: {numero_seguiment}" + (f" ({transportista})" if transportista else "")
    detalle = {"seguiment": numero_seguiment, "transportista": transportista}
    try:
        _throttle()
        with _client(token) as c:
            body = {"status": "Shipped"}
            if missatge:
                body["message"] = missatge
            r = c.post(f"/marketplace/orders/{discogs_order_id}/messages", json=body)
            if r.status_code in (200, 201):
                log.info("discogs_sync: comanda %s marcada Shipped a Discogs", discogs_order_id)
                record_event(db, "ship", "ok", order_id=order_id, external_id=discogs_order_id, actor=actor, detail=detalle)
                return True
            log.warning("discogs_sync push status %s → %s: %s", discogs_order_id, r.status_code, r.text[:200])
            record_event(db, "ship", "error", order_id=order_id, external_id=discogs_order_id, actor=actor,
                         detail=detalle, error=f"Discogs {r.status_code}: {r.text[:300]}")
            return False
    except Exception as exc:
        log.warning("discogs_sync push status error %s: %s", discogs_order_id, exc)
        record_event(db, "ship", "error", order_id=order_id, external_id=discogs_order_id, actor=actor,
                     detail=detalle, error=str(exc))
        return False


def enrich_release_from_discogs(release: Release, db: Session, token: str | None) -> bool:
    """Omple tracklist, crèdits i metadades d'un release des de Discogs.

    Cal que `release.discogs_release_id` ja estigui fixat (a mà des de
    l'admin, o pel script find_discogs_matches). Tracklist i crèdits sempre
    es refresquen (només vénen de Discogs); la resta de camps només s'omplen
    si estaven buits, per no trepitjar dades introduïdes a mà.
    Retorna False si falla la crida a Discogs (best-effort, no aixeca).
    """
    if not release.discogs_release_id:
        return False
    try:
        data = get_release(token, release.discogs_release_id)
    except Exception as exc:
        log.warning("enrich_release_from_discogs: error consultant release %s: %s", release.discogs_release_id, exc)
        return False

    release.tracklist = data.get("tracklist") or release.tracklist
    release.credits = data.get("credits") or release.credits
    release.pais = release.pais or data.get("pais")
    release.estilos = release.estilos or data.get("estilos")
    release.genero = release.genero or data.get("genero")
    release.ean = release.ean or data.get("ean")
    release.formato = release.formato or data.get("formato")
    if not release.image_url and data.get("imagen_url"):
        release.image_url = data["imagen_url"]
    if not release.sello and data.get("sello"):
        release.sello = data["sello"]
    db.commit()
    return True
