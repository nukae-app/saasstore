"""Vínculos item ↔ publicación en un canal (`channel_listings`).

Fase A (docs/PLAN_CANAL_DISCOGS.md): `record_stock_details.codi_discogs` sigue
siendo la columna en uso; `channel_listings` es su reflejo con estado. Este
módulo lo reconstruye de forma idempotente. Cuando el reconciliador (fase C)
pase a ser quien escribe, la dirección se invierte."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    CHANNEL_DISCOGS, ChannelListing, Item, RecordStockDetail,
)
from ..models.channels import LISTING_PUBLICAT, LISTING_RETIRAT


def was_published(db: Session, item_id, channel: str = CHANNEL_DISCOGS) -> bool:
    """¿Este item ya se publicó alguna vez en el canal? (hay un vínculo con id externo, aunque
    hoy esté retirado). Distingue "reponer un listing ya aprobado" de "publicar por primera vez"."""
    return db.scalar(
        select(ChannelListing.id).where(
            ChannelListing.item_id == item_id, ChannelListing.channel == channel,
            ChannelListing.external_id.isnot(None),
        ).limit(1)
    ) is not None


def backfill_discogs_listings(db: Session) -> dict:
    """Alinea `channel_listings` (canal Discogs) con `record_stock_details.codi_discogs`
    para el tenant de la sesión. Idempotente; no hace commit.

    - Item con `codi_discogs` -> listing `publicat` con ese `external_id`.
    - Listing `publicat` cuyo item ya no tiene `codi_discogs` -> `retirat`.
    Devuelve {"creats", "actualitzats", "retirats"}."""
    ahora = datetime.now(timezone.utc)
    creats = actualitzats = retirats = 0

    con_codi = {
        item.id: (codi, item.price)
        for item, codi in db.execute(
            select(Item, RecordStockDetail.codi_discogs)
            .join(RecordStockDetail, RecordStockDetail.item_id == Item.id)
            .where(RecordStockDetail.codi_discogs.isnot(None))
        ).all()
    }
    existentes = {
        listing.item_id: listing
        for listing in db.scalars(select(ChannelListing).where(ChannelListing.channel == CHANNEL_DISCOGS)).all()
    }

    for item_id, (codi, precio) in con_codi.items():
        externo = str(codi)
        listing = existentes.get(item_id)
        if listing is None:
            db.add(ChannelListing(
                item_id=item_id, channel=CHANNEL_DISCOGS, external_id=externo, status=LISTING_PUBLICAT,
                published_price=precio, last_synced_at=ahora,
            ))
            creats += 1
        elif listing.external_id != externo or listing.status != LISTING_PUBLICAT:
            # Evita chocar con el UNIQUE (canal, external_id) si otro listing
            # retirado conservaba este mismo código.
            listing.external_id = externo
            listing.status = LISTING_PUBLICAT
            listing.last_error = None
            listing.last_synced_at = ahora
            actualitzats += 1

    for item_id, listing in existentes.items():
        if item_id not in con_codi and listing.status == LISTING_PUBLICAT:
            listing.status = LISTING_RETIRAT
            listing.last_synced_at = ahora
            retirats += 1

    db.flush()
    return {"creats": creats, "actualitzats": actualitzats, "retirats": retirats}
