"""Reflejo `channel_listings` <- `record_stock_details.codi_discogs` (fase A)."""

from decimal import Decimal

from sqlalchemy import select

from app.models import ChannelListing, Item, Release
from app.services.channel_listings import backfill_discogs_listings


def _item(db, codi=None, precio="10.00"):
    r = Release(artista="A", title="T", formato="LP")
    db.add(r)
    db.flush()
    it = Item(release_id=r.id, price=Decimal(precio))
    db.add(it)
    db.flush()
    if codi:
        it.codi_discogs = codi
    db.commit()
    return it


def _sin_reflejo(db):
    """Borra los vínculos que el reflejo automático ya creó, para ejercitar el backfill (red de
    seguridad para filas anteriores o escritas sin pasar por el ORM, como las de la migración)."""
    db.query(ChannelListing).delete()
    db.commit()


def _listings(db):
    db.expire_all()
    return {l.item_id: l for l in db.scalars(select(ChannelListing)).all()}


def test_backfill_crea_listing_para_cada_item_con_codi(db):
    con, sin = _item(db, codi=111, precio="12.50"), _item(db)
    _sin_reflejo(db)
    res = backfill_discogs_listings(db)
    db.commit()
    assert res == {"creats": 1, "actualitzats": 0, "retirats": 0}
    ls = _listings(db)
    assert sin.id not in ls
    assert ls[con.id].external_id == "111" and ls[con.id].status == "publicat"
    assert ls[con.id].published_price == Decimal("12.50") and ls[con.id].channel == "discogs"


def test_backfill_es_idempotente(db):
    _item(db, codi=111)
    _sin_reflejo(db)
    backfill_discogs_listings(db)
    db.commit()
    assert backfill_discogs_listings(db) == {"creats": 0, "actualitzats": 0, "retirats": 0}


def test_el_reflejo_automatico_sigue_los_cambios_de_codi_discogs(db):
    """Cualquier flujo que asigne o borre `codi_discogs` (alta, botón manual, reposición, importaciones...)
    deja el vínculo al día en la misma transacción: si no, el plan propondría publicar de nuevo."""
    it = _item(db, codi=111)
    assert _listings(db)[it.id].external_id == "111" and _listings(db)[it.id].status == "publicat"

    it.codi_discogs = 222
    db.commit()
    assert _listings(db)[it.id].external_id == "222" and _listings(db)[it.id].status == "publicat"

    it.codi_discogs = None
    db.commit()
    assert _listings(db)[it.id].status == "retirat"

    it.codi_discogs = 333  # vuelve a publicarse
    db.commit()
    assert _listings(db)[it.id].status == "publicat" and _listings(db)[it.id].external_id == "333"
    assert len(_listings(db)) == 1  # siempre el mismo vínculo, nunca duplicados


def test_el_reflejo_funciona_tambien_al_crear_el_item_ya_con_codigo(db):
    r = Release(artista="A", title="T", formato="LP")
    db.add(r)
    db.flush()
    it = Item(release_id=r.id, price=Decimal("15.00"), codi_discogs=777)  # como hacen las importaciones
    db.add(it)
    db.commit()
    l = _listings(db)[it.id]
    assert (l.external_id, l.status, l.published_price) == ("777", "publicat", Decimal("15.00"))


def test_backfill_repara_cambios_hechos_sin_pasar_por_el_orm(db):
    from sqlalchemy import update

    from app.models import RecordStockDetail

    it = _item(db, codi=111)
    db.execute(update(RecordStockDetail).where(RecordStockDetail.item_id == it.id).values(codi_discogs=222))
    db.commit()
    assert backfill_discogs_listings(db)["actualitzats"] == 1
    db.commit()
    assert _listings(db)[it.id].external_id == "222"

    db.execute(update(RecordStockDetail).where(RecordStockDetail.item_id == it.id).values(codi_discogs=None))
    db.commit()
    assert backfill_discogs_listings(db)["retirats"] == 1
    db.commit()
    assert _listings(db)[it.id].status == "retirat"
