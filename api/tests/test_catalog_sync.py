"""Tests de la reconciliació del catàleg amb el CSV del Google Sheet."""

from decimal import Decimal

from app.models import Item, ItemStatus, RecordProduct, RecordStockDetail, Release
from app.services.catalog_sync import apply_sync, diff_catalog, parse_sheet_csv

CSV_HEADER = "CODI,ARTISTA ,TITOL / TÍTULO,SEGELL / SELLO,REFERENCIA,FORMAT,PREU/PRECIO,DATA/FECHA ENTRADA,ESTAT DISCO,ESTAT FUNDA\n"


def _row(codi, artista="Artista Test", titulo="Titol Test", discogs_release_id=123, precio="10.0"):
    return f'{codi},{artista},{titulo},Segell,REF1,LP,{discogs_release_id},For Sale,{precio},2024-01-01 0:00:00,,Mint (M),Mint (M),N,,1,1,,1'


def test_parse_sheet_csv_llegeix_per_posicio():
    csv_text = CSV_HEADER + _row(111) + "\n"
    result = parse_sheet_csv(csv_text)
    assert list(result.keys()) == [111]


def test_afegeix_disc_nou_del_sheet(db):
    csv_text = CSV_HEADER + _row(111, artista="Nou Artista", titulo="Nou Titol") + "\n"
    sheet_codis = parse_sheet_csv(csv_text)
    diff = diff_catalog(db, sheet_codis)
    assert diff["a_afegir"] == [111]

    result = apply_sync(db, sheet_codis, diff)
    assert result == {"creados": 1, "retirados": 0, "errores": 0}

    item = db.query(Item).join(RecordStockDetail, RecordStockDetail.item_id == Item.id).filter(
        RecordStockDetail.codi_discogs == 111
    ).one()
    assert item.status == ItemStatus.disponible
    assert item.price == Decimal("10.0")
    assert item.release.artista == "Nou Artista"


def test_retira_item_que_ja_no_es_al_sheet(db):
    release = Release(artista="X", title="Y")
    db.add(release)
    db.flush()
    item = Item(release_id=release.id, codi_discogs=222, price=Decimal("5.0"), status=ItemStatus.disponible)
    db.add(item)
    db.commit()

    sheet_codis = parse_sheet_csv(CSV_HEADER)  # sheet buit
    diff = diff_catalog(db, sheet_codis)
    assert diff["a_retirar"] == [222]

    apply_sync(db, sheet_codis, diff)
    db.refresh(item)
    assert item.status == ItemStatus.retirado


def test_no_retira_items_venuts_ni_reservats(db):
    release = Release(artista="X", title="Y")
    db.add(release)
    db.flush()
    venut = Item(release_id=release.id, codi_discogs=333, price=Decimal("5.0"), status=ItemStatus.vendido)
    reservat = Item(release_id=release.id, codi_discogs=444, price=Decimal("5.0"), status=ItemStatus.reservado)
    db.add_all([venut, reservat])
    db.commit()

    sheet_codis = parse_sheet_csv(CSV_HEADER)  # sheet buit
    diff = diff_catalog(db, sheet_codis)
    assert diff["a_retirar"] == []

    apply_sync(db, sheet_codis, diff)
    db.refresh(venut)
    db.refresh(reservat)
    assert venut.status == ItemStatus.vendido
    assert reservat.status == ItemStatus.reservado


def test_reutilitza_release_existent_per_discogs_release_id(db):
    release = Release(artista="Ja Existeix", title="Album", discogs_release_id=999)
    db.add(release)
    db.commit()

    csv_text = CSV_HEADER + _row(555, artista="Nom Diferent Al Sheet", discogs_release_id=999) + "\n"
    sheet_codis = parse_sheet_csv(csv_text)
    diff = diff_catalog(db, sheet_codis)
    apply_sync(db, sheet_codis, diff)

    item = db.query(Item).join(RecordStockDetail, RecordStockDetail.item_id == Item.id).filter(
        RecordStockDetail.codi_discogs == 555
    ).one()
    assert item.release_id == release.id
    assert db.query(Release).join(RecordProduct).filter(RecordProduct.discogs_release_id == 999).count() == 1
