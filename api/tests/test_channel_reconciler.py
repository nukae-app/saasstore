"""Plan de reconciliación item -> Discogs (services/channel_reconciler.py)."""

from decimal import Decimal

import pytest

from app.models import ChannelListing, CondicionItem, Item, ItemStatus, Release
from app.services import channel_reconciler as rec
from app.services.channel_reconciler import decide, plan_rows, target_price

D = Decimal


def _decide(**kw):
    base = dict(sellable=True, discogs_release_id=1, listing_status=None, external_id=None,
                published_price=None, price=D("10.00"))
    base.update(kw)
    return decide(**base)


def test_publicar_si_esta_a_la_venta_y_no_hay_listing():
    assert _decide()[0] == rec.PUBLICAR


def test_vincular_release_si_falta_el_id_de_discogs():
    assert _decide(discogs_release_id=None)[0] == rec.VINCULAR


def test_ok_si_el_listing_ya_tiene_el_precio_correcto():
    assert _decide(listing_status="publicat", external_id="5", published_price=D("10.00"))[0] == rec.OK


def test_actualizar_precio_si_difiere_o_no_consta():
    r = _decide(listing_status="publicat", external_id="5", published_price=D("9.00"))
    assert r[0] == rec.ACTUALITZAR_PREU and "10.00" in r[1]
    assert _decide(listing_status="publicat", external_id="5", published_price=None)[0] == rec.ACTUALITZAR_PREU


def test_retirar_si_ya_no_esta_a_la_venta_pero_el_listing_sigue():
    assert _decide(sellable=False, listing_status="publicat", external_id="5", published_price=D("10"))[0] == rec.RETIRAR


def test_nada_si_no_esta_a_la_venta_ni_publicado():
    assert _decide(sellable=False)[0] == rec.RES
    assert _decide(sellable=False, listing_status="retirat", external_id="5")[0] == rec.RES


def test_listing_con_error_o_sin_external_id_se_reintenta_publicando():
    assert _decide(listing_status="error")[0] == rec.PUBLICAR
    assert _decide(listing_status="publicat", external_id=None)[0] == rec.PUBLICAR


def test_recargo_se_aplica_al_precio_objetivo():
    assert target_price(D("10.00"), 10) == D("11.00")
    assert target_price(D("9.99"), D("5")) == D("10.49")
    r = _decide(listing_status="publicat", external_id="5", published_price=D("10.00"), recargo_pct=10)
    assert r[0] == rec.ACTUALITZAR_PREU


def _mk(db, *, condition=CondicionItem.segona_ma, status=ItemStatus.disponible, quantity=1, rid=123, price="10.00",
        codi=None, listing=None, published=None):
    r = Release(artista="A", title="T", formato="LP", discogs_release_id=rid)
    db.add(r)
    db.flush()
    it = Item(release_id=r.id, price=D(price), condition=condition, status=status, quantity=quantity)
    db.add(it)
    db.flush()
    if codi:
        it.codi_discogs = codi
    if listing:
        db.add(ChannelListing(item_id=it.id, external_id=str(codi) if codi else None, status=listing,
                              published_price=D(published) if published else None))
    db.commit()
    return it


def test_una_reserva_no_retira_el_listing(db):
    it = _mk(db, status=ItemStatus.reservado, codi=1, listing="publicat", published="10.00")
    (row,) = plan_rows(db)
    assert row["item_id"] == it.id and row["accio"] == rec.OK and row["estat_canal"] == "publicat"


def test_nou_con_cantidad_cero_se_retira_y_con_stock_se_mantiene(db):
    sin = _mk(db, condition=CondicionItem.nou, quantity=0, codi=1, listing="publicat", published="10.00")
    con = _mk(db, condition=CondicionItem.nou, quantity=3, codi=2, listing="publicat", published="10.00")
    por_item = {r["item_id"]: r for r in plan_rows(db)}
    assert por_item[sin.id]["accio"] == rec.RETIRAR
    assert por_item[con.id]["accio"] == rec.OK


def test_vendido_o_retirado_con_listing_vivo_se_retira(db):
    v = _mk(db, status=ItemStatus.vendido, codi=1, listing="publicat", published="10.00")
    r = _mk(db, status=ItemStatus.retirado, codi=2, listing="publicat", published="10.00")
    por_item = {x["item_id"]: x["accio"] for x in plan_rows(db)}
    assert por_item[v.id] == por_item[r.id] == rec.RETIRAR


def test_plan_cubre_pendientes_sin_release_y_excluye_lo_irrelevante(db):
    pend = _mk(db)
    sin = _mk(db, rid=None)
    _mk(db, status=ItemStatus.vendido)  # vendido y sin listing: no aparece
    rows = {r["item_id"]: r for r in plan_rows(db)}
    assert set(rows) == {pend.id, sin.id}
    assert rows[pend.id]["accio"] == rec.PUBLICAR and rows[pend.id]["estat_canal"] == "pendent"
    assert rows[sin.id]["accio"] == rec.VINCULAR and rows[sin.id]["estat_canal"] == "sense_release"


def test_plan_trae_artista_titulo_y_precio_objetivo(db):
    _mk(db, price="20.00")
    (row,) = plan_rows(db, recargo_pct=10)
    assert (row["artista"], row["titol"]) == ("A", "T")
    assert row["price"] == D("20.00") and row["target_price"] == D("22.00")
