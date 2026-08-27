"""Tests del núcleo multi-tenant (fase 1, ver plan
/Users/paumartinez/.claude/plans/swift-gathering-bengio.md): el filtro
automático de tenant (app/tenancy.py) y el caso que motivó añadir tenant_id
a StockHold — sin él, liberar una reserva caducada de un tenant podía
descontar stock de OTRO tenant."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.models import Cart, CondicionItem, Item, Release, StockHold, Tenant
from app.services.reservations import release_expired, reserve_stock


def _seed_release_nou(db, cantidad=5, precio="10.00") -> tuple[Release, Item, Cart]:
    r = Release(artista="Artista", title="Àlbum", formato="LP")
    db.add(r)
    db.flush()
    item = Item(release_id=r.id, price=Decimal(precio), condition=CondicionItem.nou, quantity=cantidad)
    cart = Cart()
    db.add_all([item, cart])
    db.commit()
    return r, item, cart


def test_db_get_respeta_filtro_de_tenant(db):
    """`db.get()` puede devolver un hit del identity map sin pasar por el
    filtro automático (ver app/tenancy.py::_filter_by_tenant) — este test
    fuerza `expunge_all()` para comprobar el caso real: sesión sin identity
    map caliente, que es lo que pasa en cada request nueva vía get_db."""
    tenant_propio = db.info["tenant_id"]
    otro = Tenant(slug="otro-tenant", domain="otro.testserver", nombre="Otro")
    db.add(otro)
    db.commit()

    _, item, _ = _seed_release_nou(db)
    item_id = item.id

    db.expunge_all()
    db.info["tenant_id"] = otro.id
    assert db.get(Item, item_id) is None, "db.get() no debe devolver un item de otro tenant"

    db.expunge_all()
    db.info["tenant_id"] = tenant_propio
    assert db.get(Item, item_id) is not None, "db.get() sí debe devolver el item del tenant propio"


def test_stockhold_expirado_de_un_tenant_no_afecta_a_otro(db):
    """Regresión del hallazgo de la revisión de diseño (ver plan): antes de
    añadir tenant_id a StockHold, el barrido de reservas caducadas
    (`_release_expired_stock_holds`) no distinguía tenants — el UPDATE de
    `Item.reserved_quantity` de una reserva ajena afectaba 0 filas (el
    WHERE no coincidía) pero el StockHold se borraba igualmente: stock
    bloqueado para siempre sin nadie que lo liberase. Con tenant_id, cada
    tenant solo ve y libera sus propias reservas caducadas."""
    tenant_a_id = db.info["tenant_id"]
    tenant_b = Tenant(slug="tenant-b", domain="b.testserver", nombre="Tenant B")
    db.add(tenant_b)
    db.commit()

    db.info["tenant_id"] = tenant_a_id
    _, item_a, cart_a = _seed_release_nou(db)
    hold_a_id = reserve_stock(db, item_a.id, 2, cart_id=cart_a.id, ttl_minutes=20)
    assert hold_a_id is not None
    db.get(StockHold, hold_a_id).reserved_until = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    db.info["tenant_id"] = tenant_b.id
    _, item_b, cart_b = _seed_release_nou(db)
    hold_b_id = reserve_stock(db, item_b.id, 3, cart_id=cart_b.id, ttl_minutes=20)
    assert hold_b_id is not None
    db.get(StockHold, hold_b_id).reserved_until = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    # Liberar reservas caducadas SOLO en el contexto del tenant A.
    db.info["tenant_id"] = tenant_a_id
    release_expired(db)
    db.expunge_all()

    # El hold de A se liberó: stock reservado a 0, StockHold borrado.
    db.info["tenant_id"] = tenant_a_id
    assert db.get(Item, item_a.id).reserved_quantity == 0
    assert db.get(StockHold, hold_a_id) is None

    # El hold de B NO se ha tocado: sigue reservado, con su StockHold intacto.
    db.info["tenant_id"] = tenant_b.id
    assert db.get(Item, item_b.id).reserved_quantity == 3
    assert db.get(StockHold, hold_b_id) is not None
