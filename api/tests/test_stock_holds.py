"""Tests de la reserva de stock agregado (condicion='nou'): reserve_stock,
release_stock_hold, confirm_stock_sale y el barrido de holds caducados en
release_expired. Análogos a los que cubrirían reserve_items/confirm_sale
para segona_ma, pero sobre cantidad en vez de status."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models import CondicionItem, Item, Release, StockHold
from app.services.reservations import (
    confirm_stock_sale, release_expired, release_stock_hold, reserve_stock, reserve_stock_bulk,
)


def _seed_release(db) -> Release:
    r = Release(artista="Artista", titulo="Álbum", formato="LP")
    db.add(r)
    db.commit()
    return r


def _seed_item_nou(db, release, cantidad=5, precio="20.00") -> Item:
    item = Item(
        release_id=release.id, precio=Decimal(precio),
        condicion=CondicionItem.nou, cantidad=cantidad,
    )
    db.add(item)
    db.commit()
    return item


def test_reserve_stock_ok_descuenta_disponibilidad(db):
    release = _seed_release(db)
    item = _seed_item_nou(db, release, cantidad=5)
    cart_id = uuid.uuid4()

    hold_id = reserve_stock(db, item.id, 3, cart_id=cart_id, ttl_minutes=20)

    assert hold_id is not None
    db.refresh(item)
    assert item.cantidad == 5
    assert item.cantidad_reservada == 3
    hold = db.get(StockHold, hold_id)
    assert hold.cantidad == 3
    assert hold.cart_id == cart_id


def test_reserve_stock_falla_si_no_hay_suficiente(db):
    release = _seed_release(db)
    item = _seed_item_nou(db, release, cantidad=5)

    assert reserve_stock(db, item.id, 3, cart_id=uuid.uuid4(), ttl_minutes=20) is not None
    # ya solo quedan 2 libres: pedir 3 más debe fallar TODO o NADA
    assert reserve_stock(db, item.id, 3, cart_id=uuid.uuid4(), ttl_minutes=20) is None

    db.refresh(item)
    assert item.cantidad_reservada == 3  # el intento fallido no ha tocado nada


def test_reserve_stock_dos_carritos_se_reparten_las_ultimas_unidades(db):
    release = _seed_release(db)
    item = _seed_item_nou(db, release, cantidad=5)

    h1 = reserve_stock(db, item.id, 3, cart_id=uuid.uuid4(), ttl_minutes=20)
    h2 = reserve_stock(db, item.id, 2, cart_id=uuid.uuid4(), ttl_minutes=20)
    assert h1 is not None and h2 is not None

    db.refresh(item)
    assert item.cantidad_reservada == 5
    # ya no queda nada para un tercero
    assert reserve_stock(db, item.id, 1, cart_id=uuid.uuid4(), ttl_minutes=20) is None


def test_reserve_stock_ignora_items_segona_ma(db):
    release = _seed_release(db)
    item = Item(release_id=release.id, precio=Decimal("10.00"), condicion=CondicionItem.segona_ma)
    db.add(item)
    db.commit()

    assert reserve_stock(db, item.id, 1, cart_id=uuid.uuid4(), ttl_minutes=20) is None


def test_release_stock_hold_devuelve_la_cantidad(db):
    release = _seed_release(db)
    item = _seed_item_nou(db, release, cantidad=5)
    hold_id = reserve_stock(db, item.id, 3, cart_id=uuid.uuid4(), ttl_minutes=20)

    assert release_stock_hold(db, hold_id) is True
    db.refresh(item)
    assert item.cantidad_reservada == 0
    assert db.get(StockHold, hold_id) is None
    # liberar dos veces no rompe nada
    assert release_stock_hold(db, hold_id) is False


def test_confirm_stock_sale_descuenta_cantidad_real(db):
    release = _seed_release(db)
    item = _seed_item_nou(db, release, cantidad=5)
    hold_id = reserve_stock(db, item.id, 2, cart_id=uuid.uuid4(), ttl_minutes=20)

    vendidos = confirm_stock_sale(db, hold_id)

    assert vendidos == 2
    db.refresh(item)
    assert item.cantidad == 3
    assert item.cantidad_reservada == 0
    assert db.get(StockHold, hold_id) is None


def test_confirm_stock_sale_hold_inexistente(db):
    assert confirm_stock_sale(db, uuid.uuid4()) is None


def test_release_expired_libera_holds_caducados_de_carrito(db):
    release = _seed_release(db)
    item = _seed_item_nou(db, release, cantidad=5)
    hold_id = reserve_stock(db, item.id, 3, cart_id=uuid.uuid4(), ttl_minutes=20)

    # forzamos la caducidad manualmente, como en los tests de segona_ma
    hold = db.get(StockHold, hold_id)
    hold.reserved_until = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    release_expired(db)

    db.refresh(item)
    assert item.cantidad_reservada == 0
    assert db.get(StockHold, hold_id) is None


def test_reserve_stock_mismo_carrito_renueva_en_vez_de_sumar(db):
    release = _seed_release(db)
    item = _seed_item_nou(db, release, cantidad=5)
    cart_id = uuid.uuid4()

    h1 = reserve_stock(db, item.id, 2, cart_id=cart_id, ttl_minutes=20)
    h2 = reserve_stock(db, item.id, 4, cart_id=cart_id, ttl_minutes=20)  # el cliente sube la cantidad

    assert h1 is not None and h2 is not None and h1 != h2
    db.refresh(item)
    assert item.cantidad_reservada == 4  # no 6: el segundo hold sustituye al primero
    assert db.get(StockHold, h1) is None
    assert db.get(StockHold, h2).cantidad == 4


def test_reserve_stock_bulk_todo_o_nada(db):
    release1 = _seed_release(db)
    release2 = Release(artista="Artista2", titulo="Àlbum2", formato="LP")
    db.add(release2)
    db.commit()
    item1 = _seed_item_nou(db, release1, cantidad=5)
    item2 = _seed_item_nou(db, release2, cantidad=1)
    cart_id = uuid.uuid4()

    # item2 solo tiene 1 unidad: pedir 2 hace fallar TODO el lote, incluido item1.
    failed = reserve_stock_bulk(db, [(item1.id, 3), (item2.id, 2)], cart_id, ttl_minutes=20)

    assert failed == [item2.id]
    db.refresh(item1)
    db.refresh(item2)
    assert item1.cantidad_reservada == 0  # revertido
    assert item2.cantidad_reservada == 0


def test_reserve_stock_bulk_exito(db):
    release1 = _seed_release(db)
    release2 = Release(artista="Artista2", titulo="Àlbum2", formato="LP")
    db.add(release2)
    db.commit()
    item1 = _seed_item_nou(db, release1, cantidad=5)
    item2 = _seed_item_nou(db, release2, cantidad=5)
    cart_id = uuid.uuid4()

    failed = reserve_stock_bulk(db, [(item1.id, 3), (item2.id, 2)], cart_id, ttl_minutes=20)

    assert failed == []
    db.refresh(item1)
    db.refresh(item2)
    assert item1.cantidad_reservada == 3
    assert item2.cantidad_reservada == 2


def test_release_expired_no_toca_holds_sin_caducidad(db):
    release = _seed_release(db)
    item = _seed_item_nou(db, release, cantidad=5)
    # ttl_minutes=None -> retención de club, sin caducidad automática
    hold_id = reserve_stock(db, item.id, 2, assignacio_id=uuid.uuid4(), ttl_minutes=None)

    release_expired(db)

    db.refresh(item)
    assert item.cantidad_reservada == 2
    assert db.get(StockHold, hold_id) is not None
