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
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import CondicionItem, Item, ItemStatus, Order, OrderItem, OrderOrigen, OrderStatus, Release
from .discogs import _client, _throttle, get_release
from .iva import compute_iva_venda

log = logging.getLogger(__name__)

# Mapeig d'estat de comanda de Discogs (seller-side) → el nostre OrderStatus.
# No hi ha equivalent de "entregado" del costat venedor de Discogs: és un estat
# només intern nostre, i el pull mai el sobreescriu (vegeu sync_discogs_orders).
DISCOGS_ORDER_STATUS_MAP: dict[str, OrderStatus] = {
    "New Order": OrderStatus.pendiente_pago,
    "Buyer Contacted": OrderStatus.pendiente_pago,
    "Invoice Sent": OrderStatus.pendiente_pago,
    "Payment Pending": OrderStatus.pendiente_pago,
    "Payment Received": OrderStatus.pagado,
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


def push_item_to_discogs(
    item_id,
    release_discogs_id: int,
    precio: float,
    estado_disco: str | None,
    estado_funda: str | None,
    notas: str | None = None,
    es_nou: bool = False,
) -> int | None:
    """Crea un listing al Marketplace de Discogs.

    `es_nou=True` (stock agregado): Discogs no té un grading de "nou", el
    conveni del mercat és fer servir "Mint (M)" tant per al disc com per a
    la funda, sense comentaris de grading (abans, per a nou, `estado_disco`
    sempre era None i queia per defecte a "VG+", incorrecte).

    Retorna el listing_id (codi_discogs) o None si falla.
    """
    if not get_settings().discogs_token:
        log.warning("discogs_sync: sense token, no es pot fer push")
        return None

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

    body = {
        "release_id": release_discogs_id,
        "condition": condition,
        "sleeve_condition": sleeve,
        "price": round(float(precio), 2),
        "status": "For Sale",
        "comments": " | ".join(comments_parts) or None,
    }

    try:
        _throttle()
        with _client() as c:
            r = c.post("/marketplace/listings", json=body)
            if r.status_code in (400, 422):
                log.warning("discogs_sync push 4xx: %s — %s", r.status_code, r.text[:200])
                return None
            r.raise_for_status()
            listing_id = r.json().get("listing_id")
            log.info("discogs_sync: listing creat %s per item %s", listing_id, item_id)
            return listing_id
    except Exception as exc:
        log.warning("discogs_sync push error per item %s: %s", item_id, exc)
        return None


def remove_item_from_discogs(codi_discogs: int) -> bool:
    """Elimina un listing del Marketplace de Discogs (disc venut o retirat).

    Retorna True si s'ha eliminat (o ja no existia), False si ha fallat.
    """
    if not get_settings().discogs_token:
        return False
    try:
        _throttle()
        with _client() as c:
            r = c.delete(f"/marketplace/listings/{codi_discogs}")
            if r.status_code in (200, 204, 404):
                log.info("discogs_sync: listing %s eliminat", codi_discogs)
                return True
            log.warning("discogs_sync delete %s → %s", codi_discogs, r.status_code)
            return False
    except Exception as exc:
        log.warning("discogs_sync delete error %s: %s", codi_discogs, exc)
        return False


def sync_stock_listing(db: Session, item: Item) -> None:
    """Mantiene el listing de Discogs de una línea `nou` en "stock virtual
    de 1": como mucho 1 listing activo mientras `item.cantidad > 0`. Hay que
    llamarla después de CUALQUIER cambio de `item.cantidad` en una línea nou
    (recepción, alta admin, venta TPV/web/club, devolución) — no se llama
    sola, no hay un trigger de BBDD para esto.

    No hace nada si el release no está vinculado a Discogs (no hay
    `codi_discogs` que gestionar) o si el item no es `nou`."""
    if item.condicion != CondicionItem.nou:
        return
    if item.cantidad <= 0:
        if item.codi_discogs:
            remove_item_from_discogs(item.codi_discogs)
            item.codi_discogs = None
        return

    # Se busca por release_id (no vía item.release) para funcionar también
    # con un Item recién creado/todavía sin flush, donde la relación
    # perezosa no siempre resuelve.
    release = db.get(Release, item.release_id)
    if item.codi_discogs is None and release is not None and release.discogs_release_id:
        listing_id = push_item_to_discogs(
            item_id=item.id,
            release_discogs_id=release.discogs_release_id,
            precio=float(item.precio),
            estado_disco=None,
            estado_funda=None,
            es_nou=True,
        )
        if listing_id:
            item.codi_discogs = listing_id


# ---------------------------------------------------------------------------
# Comandes del Marketplace (pull: Discogs → nosaltres)
# ---------------------------------------------------------------------------

def fetch_open_discogs_orders() -> list[dict]:
    """Llista les comandes del Marketplace (com a venedors). Best-effort: si falla,
    retorna llista buida i deixa traça al log (no s'ha de trencar el polling per un 5xx puntual)."""
    if not get_settings().discogs_token:
        return []
    orders: list[dict] = []
    try:
        page = 1
        while True:
            _throttle()
            with _client() as c:
                r = c.get("/marketplace/orders", params={"page": page, "per_page": 50, "sort": "created", "sort_order": "desc"})
                r.raise_for_status()
                data = r.json()
            orders.extend(data.get("orders", []))
            pagination = data.get("pagination", {})
            if page >= pagination.get("pages", 1):
                break
            page += 1
    except Exception as exc:
        log.warning("discogs_sync: error llistant comandes: %s", exc)
    return orders


def sync_discogs_orders(db: Session) -> dict:
    """Pull de comandes del Marketplace: crea/actualitza Order+OrderItem amb origen='discogs'.

    Idempotent per discogs_order_id. Mai sobreescriu un estat local terminal
    (entregado/cancelado) amb el que digui Discogs — això és decisió nostra, no seva.
    """
    creats = actualitzats = sense_match = errors = 0

    for raw in fetch_open_discogs_orders():
        discogs_id = str(raw.get("id"))
        discogs_status = raw.get("status", "")
        nou_status = DISCOGS_ORDER_STATUS_MAP.get(discogs_status)
        if nou_status is None:
            log.warning("discogs_sync: estat de comanda desconegut '%s' (ordre %s)", discogs_status, discogs_id)
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
        items = db.scalars(select(Item).where(Item.codi_discogs.in_(listing_ids))).all() if listing_ids else []
        if not items:
            log.warning("discogs_sync: comanda %s sense items locals coincidents (listings %s)", discogs_id, listing_ids)
            sense_match += 1
            continue

        try:
            buyer = (raw.get("buyer") or {}).get("username")
            total_raw = (raw.get("total") or {}).get("value")
            total = Decimal(str(total_raw)) if total_raw is not None else sum((i.precio for i in items), Decimal("0"))
            order = Order(
                email_contacto=f"{buyer or 'comprador'}@discogs-buyer.local",
                status=nou_status,
                total=total,
                metodo_envio="envio",
                direccion_envio={"raw": raw.get("shipping_address")} if raw.get("shipping_address") else None,
                origen=OrderOrigen.discogs,
                discogs_order_id=discogs_id,
                discogs_buyer=buyer,
            )
            db.add(order)
            db.flush()
            for item in items:
                tipus_iva_id, iva_pct, iva_import = compute_iva_venda(item, item.precio, db)
                db.add(OrderItem(
                    order_id=order.id, item_id=item.id, precio=item.precio, cantidad=1,
                    condicion=item.condicion,
                    tipus_iva_id=tipus_iva_id, iva_pct=iva_pct, iva_import=iva_import,
                ))
                if item.condicion == CondicionItem.nou:
                    # "Stock virtual de 1": el listing vendido ya no existe en
                    # Discogs; se descuenta 1 unidad y, si queda stock, se
                    # publica un listing nuevo para mantener la regla.
                    item.cantidad = max(0, item.cantidad - 1)
                    item.codi_discogs = None
                    sync_stock_listing(db, item)
                elif item.status != ItemStatus.vendido:
                    item.status = ItemStatus.vendido
                    item.reserved_until = None
                    item.reserved_by_cart_id = None
            db.commit()
            creats += 1
        except Exception as exc:
            db.rollback()
            log.warning("discogs_sync: error creant comanda local per %s: %s", discogs_id, exc)
            errors += 1

    return {"creats": creats, "actualitzats": actualitzats, "sense_match": sense_match, "errors": errors}


def push_shipped_status(discogs_order_id: str, numero_seguiment: str | None, transportista: str | None) -> bool:
    """Marca la comanda com "Shipped" a Discogs i hi deixa el número de seguiment com a missatge
    (Discogs no té un camp estructurat de tracking a l'API de comandes)."""
    if not get_settings().discogs_token:
        return False
    missatge = None
    if numero_seguiment:
        missatge = f"Enviat. Seguiment: {numero_seguiment}" + (f" ({transportista})" if transportista else "")
    try:
        _throttle()
        with _client() as c:
            body = {"status": "Shipped"}
            if missatge:
                body["message"] = missatge
            r = c.post(f"/marketplace/orders/{discogs_order_id}/messages", json=body)
            if r.status_code in (200, 201):
                log.info("discogs_sync: comanda %s marcada Shipped a Discogs", discogs_order_id)
                return True
            log.warning("discogs_sync push status %s → %s: %s", discogs_order_id, r.status_code, r.text[:200])
            return False
    except Exception as exc:
        log.warning("discogs_sync push status error %s: %s", discogs_order_id, exc)
        return False


def enrich_release_from_discogs(release: Release, db: Session) -> bool:
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
        data = get_release(release.discogs_release_id)
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
    if not release.imagen_url and data.get("imagen_url"):
        release.imagen_url = data["imagen_url"]
    if not release.sello and data.get("sello"):
        release.sello = data["sello"]
    db.commit()
    return True
