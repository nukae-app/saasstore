"""Copias y restauración del CATÁLOGO de un tenant (services/catalog_backup.py)."""

import gzip
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import (
    CartItem, ChannelBackup, ChannelEvent, CondicionItem, Item, ItemStatus, Order, OrderItem, OrderStatus, Release,
    Tenant,
)
from app.services import catalog_backup as cb
from app.tenancy import scoped_to

D = Decimal


def _item(db, *, title="T", codi=None, price="10.00", condition=CondicionItem.segona_ma, quantity=1, rid=None,
          status=ItemStatus.disponible):
    r = Release(artista="Artista", title=title, formato="LP", discogs_release_id=rid)
    db.add(r)
    db.flush()
    it = Item(release_id=r.id, price=D(price), condition=condition, quantity=quantity, status=status)
    db.add(it)
    db.flush()
    if codi:
        it.codi_discogs = codi
    db.commit()
    return it


def _state(db):
    """Estado del catálogo del tenant de la sesión, sin las columnas que cambian solas."""
    db.expire_all()
    tid = db.info["tenant_id"]
    return {
        name: {pk: {k: v for k, v in row.items() if k != "updated_at"} for pk, row in cb._dump(db, tid, name).items()}
        for name in cb.TABLES
    }


def _order_after(db, item, *, minutes=5, status=OrderStatus.pagado):
    """Pedido creado DESPUÉS de la copia (SQLite tiene 1 s de resolución: se fija la fecha a mano)."""
    o = Order(contact_email="x@y.z", status=status, total=D("10"), shipping_method="envio",
              created_at=datetime.now(timezone.utc) + timedelta(minutes=minutes))
    db.add(o)
    db.flush()
    db.add(OrderItem(order_id=o.id, item_id=item.id, price=D("10")))
    db.commit()
    return o


def _snapshot(db, label="foto", trigger="manual"):
    b = cb.create_snapshot(db, label=label, trigger=trigger, actor="ana@x.com")
    db.commit()
    return b


# --- Crear copias -----------------------------------------------------------------------------

def test_la_copia_guarda_las_cinco_tablas_comprimidas_y_resume_los_recuentos(db):
    _item(db, codi=100)
    _item(db, condition=CondicionItem.nou, quantity=3)
    b = _snapshot(db)
    assert b.kind == "catalog" and b.trigger == "manual" and b.created_by == "ana@x.com"
    assert b.summary == {"releases": 2, "release_records": 2, "items": 2, "record_stock_details": 1, "channel_listings": 1}
    data = json.loads(gzip.decompress(b.payload))
    assert data["version"] == 1 and set(data["tables"]) == set(cb.TABLES) and b.size_bytes == len(b.payload)


def test_las_copias_automaticas_se_podan_y_las_manuales_no(db):
    _item(db)
    manuales = [_snapshot(db, f"m{i}") for i in range(3)]
    for i in range(cb.AUTO_KEEP + 4):
        _snapshot(db, f"auto{i}", trigger="pre_load")
    db.expire_all()
    autos = db.scalars(select(ChannelBackup).where(ChannelBackup.trigger == "pre_load")).all()
    assert len(autos) == cb.AUTO_KEEP
    assert {b.id for b in db.scalars(select(ChannelBackup).where(ChannelBackup.trigger == "manual")).all()} == {m.id for m in manuales}


# --- Ida y vuelta exacta -----------------------------------------------------------------------

def test_restaurar_devuelve_el_catalogo_exactamente_al_estado_de_la_copia(db):
    a = _item(db, title="A", codi=100, price="10.00")
    b = _item(db, title="B", codi=200, price="20.00", condition=CondicionItem.nou, quantity=5)
    antes = _state(db)
    snap = _snapshot(db)

    # Cambios posteriores: precio, borrado de un item, item nuevo con código, título y código cambiados
    a.price = D("99.00")
    a.release.title = "Título cambiado"
    a.codi_discogs = 101
    db.delete(b)
    db.commit()
    _item(db, title="Nuevo", codi=300)
    assert _state(db) != antes

    res = cb.restore(db, snap, actor="ana@x.com")
    assert res["restored"] is True and res["conflicts"] == []
    assert _state(db) == antes


def test_la_vista_previa_cuenta_y_detalla_sin_modificar_nada(db):
    a = _item(db, title="A", price="10.00")
    snap = _snapshot(db)
    a.price = D("15.00")
    nuevo = _item(db, title="Nuevo")
    db.commit()
    estado = _state(db)

    p = cb.preview(db, snap)
    assert p["counts"]["items"] == {"insert": 0, "update": 1, "delete": 1}
    assert p["counts"]["releases"] == {"insert": 0, "update": 0, "delete": 1}
    cambio = next(s for s in p["sample"] if s["table"] == "items" and s["op"] == "update")
    assert cambio["label"] == "Artista — A" and cambio["changes"]["price"] == ["15.00", "10.00"]
    assert any(s["op"] == "delete" and s["label"] == "Artista — Nuevo" for s in p["sample"])
    assert p["conflicts"] == [] and p["total_changes"] > 0
    assert _state(db) == estado  # la vista previa no toca nada
    assert db.get(Item, nuevo.id) is not None


def test_si_el_catalogo_ya_coincide_no_hay_nada_que_restaurar(db):
    _item(db)
    snap = _snapshot(db)
    res = cb.restore(db, snap)
    assert res["restored"] is False and "ja coincideix" in res["message"]
    db.expire_all()
    assert db.scalars(select(ChannelBackup).where(ChannelBackup.trigger == "pre_restore")).all() == []


def test_restaurar_guarda_una_copia_automatica_del_estado_actual_y_un_evento(db):
    a = _item(db, price="10.00")
    snap = _snapshot(db, label="mi punto")
    a.price = D("77.00")
    db.commit()
    res = cb.restore(db, snap, actor="ana@x.com")
    previa = db.get(ChannelBackup, res["copia_previa"])
    assert previa.trigger == "pre_restore" and "mi punto" in previa.label
    # esa copia previa permite deshacer la propia restauración
    cb.restore(db, previa, actor="ana@x.com")
    db.expire_all()
    assert db.get(Item, a.id).price == D("77.00")
    ev = db.scalars(select(ChannelEvent).where(ChannelEvent.action == "restore")).all()
    assert len(ev) == 2 and ev[0].actor == "ana@x.com" and ev[0].detail["backup"] == snap.id


def test_un_codigo_que_cambia_de_item_no_choca_con_la_unicidad(db):
    a = _item(db, title="A", codi=100)
    b = _item(db, title="B", codi=200)
    antes = _state(db)
    snap = _snapshot(db)
    a.codi_discogs = None                         # el 100 pasa de A a B y el 200 de B a A (como al consolidar líneas)
    db.commit()
    b.codi_discogs = 100
    db.commit()
    a.codi_discogs = 200
    db.commit()
    cb.restore(db, snap)
    assert _state(db) == antes


# --- Conflictos: lo que ya no es seguro tocar ----------------------------------------------------

def test_un_item_vendido_despues_de_la_copia_no_se_vuelve_a_poner_a_la_venta(db):
    vendido, normal = _item(db, title="Vendido", price="10.00"), _item(db, title="Normal", price="10.00")
    snap = _snapshot(db)
    vendido.status, vendido.price = ItemStatus.vendido, D("12.00")
    normal.price = D("13.00")
    db.commit()
    _order_after(db, vendido)

    p = cb.preview(db, snap)
    assert [c["pk"] for c in p["conflicts"]] == [str(vendido.id)]
    assert "posteriors" in p["conflicts"][0]["reason"] and p["conflicts"][0]["label"] == "Artista — Vendido"

    res = cb.restore(db, snap)
    db.expire_all()
    assert res["restored"] is True and len(res["conflicts"]) == 1
    assert db.get(Item, vendido.id).status == ItemStatus.vendido and db.get(Item, vendido.id).price == D("12.00")
    assert db.get(Item, normal.id).price == D("10.00")  # el resto sí se restaura


def test_las_ventas_anteriores_a_la_copia_no_bloquean(db):
    nou = _item(db, condition=CondicionItem.nou, quantity=5, price="10.00")
    _order_after(db, nou, minutes=-60)   # venta antigua de la línea agregada
    snap = _snapshot(db)
    nou.price = D("11.00")
    db.commit()
    p = cb.preview(db, snap)
    assert p["conflicts"] == [] and p["counts"]["items"]["update"] == 1
    cb.restore(db, snap)
    db.expire_all()
    assert db.get(Item, nou.id).price == D("10.00")


def test_un_item_creado_despues_con_pedido_no_se_borra(db):
    _item(db, title="Base")
    snap = _snapshot(db)
    nuevo = _item(db, title="Nuevo", codi=300)
    _order_after(db, nuevo)
    p = cb.preview(db, snap)
    assert [c["pk"] for c in p["conflicts"] if c["table"] == "items"] == [str(nuevo.id)]
    assert any(c["table"] == "releases" and "encara té items" in c["reason"] for c in p["conflicts"])
    cb.restore(db, snap)
    db.expire_all()
    assert db.get(Item, nuevo.id) is not None and db.get(Release, nuevo.release_id) is not None


def test_reservados_y_en_carrito_se_dejan_como_estan(db):
    reservado, en_carro = _item(db, title="R", price="10.00"), _item(db, title="C", price="10.00")
    snap = _snapshot(db)
    reservado.price = en_carro.price = D("14.00")
    reservado.status = ItemStatus.reservado
    from app.models import Cart

    cart = Cart()
    db.add(cart)
    db.flush()
    db.add(CartItem(cart_id=cart.id, item_id=en_carro.id))
    db.commit()
    p = cb.preview(db, snap)
    motivos = {c["pk"]: c["reason"] for c in p["conflicts"]}
    assert "reservat" in motivos[str(reservado.id)] and "carretó" in motivos[str(en_carro.id)]
    cb.restore(db, snap)
    db.expire_all()
    assert db.get(Item, reservado.id).price == D("14.00") and db.get(Item, en_carro.id).price == D("14.00")


# --- Atomicidad y aislamiento ---------------------------------------------------------------------

def test_si_la_restauracion_falla_no_se_cambia_nada(db, monkeypatch):
    a = _item(db, price="10.00")
    snap = _snapshot(db)
    a.price = D("50.00")
    _item(db, title="Otro")
    db.commit()
    antes = _state(db)

    original = cb._apply

    def falla_a_medias(db_, plan, tenant_id):
        original(db_, plan, tenant_id)       # aplica TODO...
        raise RuntimeError("boom")           # ...y revienta antes del commit

    monkeypatch.setattr(cb, "_apply", falla_a_medias)
    with pytest.raises(cb.RestoreError, match="no s'ha canviat res"):
        cb.restore(db, snap)
    assert _state(db) == antes
    # la copia previa sí se conservó (se guarda antes de empezar)
    assert db.scalars(select(ChannelBackup).where(ChannelBackup.trigger == "pre_restore")).first() is not None


def test_solo_toca_el_catalogo_del_tenant_de_la_copia(db):
    a = _item(db, title="Mío", price="10.00")
    otro = Tenant(slug="otra-tienda", domain="otra.testserver", nombre="Otra", vertical_id="records")
    db.add(otro)
    db.commit()
    tenant_a = db.info["tenant_id"]
    with scoped_to(db, otro.id):
        ajeno = _item(db, title="Ajeno", price="30.00")
        ajeno_id, ajeno_rel = ajeno.id, ajeno.release_id
    db.info["tenant_id"] = tenant_a

    snap = _snapshot(db)
    assert snap.summary["items"] == 1   # la copia no incluye lo de la otra tienda
    a.price = D("99.00")
    db.commit()
    cb.restore(db, snap)

    db.expire_all()
    assert db.get(Item, a.id).price == D("10.00")
    with scoped_to(db, otro.id):
        assert db.get(Item, ajeno_id).price == D("30.00") and db.get(Release, ajeno_rel) is not None
    db.info["tenant_id"] = tenant_a
