"""Plan de reconciliación item -> canal (Discogs): qué hay que hacer para que lo
publicado coincida con el stock y los precios de la app. SOLO CALCULA desde la caché
local (`channel_listings`): no llama a Discogs. Lo usan la pestaña Listings, el
resumen y el aplicador (services/channel_apply.py).

Regla de publicación (docs/PLAN_CANAL_DISCOGS.md §5, decidida 2026-10-01): se publica
mientras quede al menos una unidad real —no vendida ni retirada—, aunque esté
RESERVADA: una reserva (carrito, ~20 min) no retira el listing."""

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from ..models import (
    CHANNEL_DISCOGS, ChannelListing, CondicionItem, Item, ItemStatus, RecordProduct, Release,
)
from ..models.channels import LISTING_ERROR, LISTING_PUBLICAT, LISTING_RETIRAT

# Acciones del plan
PUBLICAR = "publicar"
ACTUALITZAR_PREU = "actualitzar_preu"
RETIRAR = "retirar"
VINCULAR = "vincular_release"
OK = "ok"
RES = "res"

# Estado de canal que se muestra por item
E_PUBLICAT, E_PENDENT, E_ERROR, E_SENSE_RELEASE, E_RETIRAT, E_NO_APLICA = (
    "publicat", "pendent", "error", "sense_release", "retirat", "no_aplica",
)

_SELLABLE_STATUS = (ItemStatus.disponible, ItemStatus.reservado)


def sellable_clause():
    """SQL: el item tiene al menos una unidad real a la venta (reservada cuenta)."""
    return and_(
        Item.status.in_(_SELLABLE_STATUS),
        or_(Item.condition == CondicionItem.segona_ma, Item.quantity > 0),
    )


def is_sellable(item: Item) -> bool:
    return item.status in _SELLABLE_STATUS and (item.condition == CondicionItem.segona_ma or item.quantity > 0)


def target_price(price: Decimal, recargo_pct: Decimal | float | int = 0) -> Decimal:
    """Precio a publicar: el de la app más el recargo del canal (0 = mismo que la web)."""
    value = Decimal(str(price)) * (Decimal(1) + Decimal(str(recargo_pct)) / Decimal(100))
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def decide(
    *, sellable: bool, discogs_release_id: int | None, listing_status: str | None, external_id: str | None,
    published_price: Decimal | None, price: Decimal, recargo_pct: Decimal | float | int = 0,
) -> tuple[str, str]:
    """(acción, motivo) para un item. Pura: sin acceso a BD ni a Discogs."""
    live = listing_status == LISTING_PUBLICAT and bool(external_id)
    if sellable:
        if live:
            objetivo = target_price(price, recargo_pct)
            if published_price is None or Decimal(str(published_price)) != objetivo:
                return ACTUALITZAR_PREU, f"preu publicat {published_price if published_price is not None else '—'} → {objetivo}"
            return OK, ""
        if not discogs_release_id:
            return VINCULAR, "falta vincular el release amb Discogs (discogs_release_id)"
        return PUBLICAR, "a la venda a l'app i sense listing a Discogs"
    if live:
        return RETIRAR, "ja no està a la venda a l'app i el listing segueix publicat"
    return RES, ""


def channel_state(*, sellable: bool, discogs_release_id: int | None, listing_status: str | None, external_id: str | None) -> str:
    if listing_status == LISTING_PUBLICAT and external_id:
        return E_PUBLICAT
    if listing_status == LISTING_ERROR:
        return E_ERROR
    if sellable:
        return E_SENSE_RELEASE if not discogs_release_id else E_PENDENT
    return E_RETIRAT if listing_status == LISTING_RETIRAT else E_NO_APLICA


def plan_rows(db: Session, recargo_pct: Decimal | float | int = 0, channel: str = CHANNEL_DISCOGS) -> list[dict]:
    """Una fila por item que está a la venta o tiene un listing publicado, con su estado de
    canal y la acción propuesta. Calcula todo en Python sobre una única consulta (unos miles
    de filas); si el catálogo crece mucho habrá que paginar en SQL."""
    stmt = (
        select(Item, ChannelListing, Release.title, RecordProduct.artista, RecordProduct.discogs_release_id, RecordProduct.formato)
        .join(Release, Release.id == Item.release_id)
        .outerjoin(RecordProduct, RecordProduct.release_id == Release.id)
        .outerjoin(ChannelListing, and_(ChannelListing.item_id == Item.id, ChannelListing.channel == channel))
        .where(or_(sellable_clause(), ChannelListing.status == LISTING_PUBLICAT))
    )
    rows = []
    for item, listing, titol, artista, rid, formato in db.execute(stmt).all():
        sellable = is_sellable(item)
        ls = listing.status if listing else None
        ext = listing.external_id if listing else None
        pub = listing.published_price if listing else None
        accio, motiu = decide(
            sellable=sellable, discogs_release_id=rid, listing_status=ls, external_id=ext,
            published_price=pub, price=item.price, recargo_pct=recargo_pct,
        )
        rows.append({
            "item_id": item.id, "release_id": item.release_id, "artista": artista, "titol": titol, "formato": formato,
            "condicio": item.condition.value, "estat_item": item.status.value, "quantity": item.quantity,
            "price": item.price, "target_price": target_price(item.price, recargo_pct),
            "discogs_release_id": rid, "listing_status": ls, "external_id": ext, "published_price": pub,
            "last_error": listing.last_error if listing else None,
            "last_synced_at": listing.last_synced_at if listing else None,
            "estat_canal": channel_state(sellable=sellable, discogs_release_id=rid, listing_status=ls, external_id=ext),
            "accio": accio, "motiu": motiu,
        })
    return rows
