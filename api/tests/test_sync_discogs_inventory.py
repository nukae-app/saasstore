"""Tests de la consolidación de líneas `nou` duplicadas (herencia de antes
del stock agregado) en scripts/sync_discogs_inventory.py."""

from datetime import datetime, timezone
from decimal import Decimal

from app.models import CondicionItem, Item, Order, OrderItem, OrderStatus, Release
from scripts.sync_discogs_inventory import _consolidar_duplicados_nou, _tiene_dependientes


def _seed_release(db) -> Release:
    r = Release(artista="Artista", titulo="Àlbum", formato="LP")
    db.add(r)
    db.commit()
    return r


def test_consolidar_fusiona_dos_lineas_nou(db):
    release = _seed_release(db)
    antiguo = Item(
        release_id=release.id, precio=Decimal("20.00"), condicion=CondicionItem.nou,
        cantidad=1, coste_adquisicion=Decimal("10.00"),
        fecha_entrada=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    nuevo = Item(
        release_id=release.id, precio=Decimal("25.00"), condicion=CondicionItem.nou,
        cantidad=1, codi_discogs=999111, estado_disco="Near Mint (NM or M-)",
        fecha_entrada=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    db.add_all([antiguo, nuevo])
    db.commit()

    consolidados = _consolidar_duplicados_nou(db, dry_run=False)
    assert consolidados == 1

    db.expire_all()
    items = db.query(Item).filter(Item.release_id == release.id).all()
    assert len(items) == 1
    superviviente = items[0]
    assert superviviente.id == antiguo.id  # sobrevive el de fecha_entrada más antigua
    assert superviviente.cantidad == 2
    assert superviviente.coste_adquisicion == Decimal("10.00")  # el otro no tenía coste
    assert superviviente.codi_discogs == 999111  # hereda el listing que no tenía


def test_consolidar_omite_release_con_dependientes(db):
    release = _seed_release(db)
    item1 = Item(release_id=release.id, precio=Decimal("20.00"), condicion=CondicionItem.nou, cantidad=1)
    item2 = Item(release_id=release.id, precio=Decimal("25.00"), condicion=CondicionItem.nou, cantidad=1)
    db.add_all([item1, item2])
    db.commit()

    order = Order(
        email_contacto="a@example.com", status=OrderStatus.pagado, total=Decimal("20.00"), metodo_envio="envio",
    )
    db.add(order)
    db.flush()
    db.add(OrderItem(order_id=order.id, item_id=item1.id, precio=Decimal("20.00")))
    db.commit()

    assert _tiene_dependientes(db, item1.id) is True
    assert _tiene_dependientes(db, item2.id) is False

    consolidados = _consolidar_duplicados_nou(db, dry_run=False)
    assert consolidados == 0

    db.expire_all()
    items = db.query(Item).filter(Item.release_id == release.id).all()
    assert len(items) == 2  # no se ha tocado nada


def test_consolidar_dry_run_no_persiste(db):
    release = _seed_release(db)
    db.add_all([
        Item(release_id=release.id, precio=Decimal("20.00"), condicion=CondicionItem.nou, cantidad=1),
        Item(release_id=release.id, precio=Decimal("25.00"), condicion=CondicionItem.nou, cantidad=1),
    ])
    db.commit()

    _consolidar_duplicados_nou(db, dry_run=True)
    db.rollback()

    items = db.query(Item).filter(Item.release_id == release.id).all()
    assert len(items) == 2
