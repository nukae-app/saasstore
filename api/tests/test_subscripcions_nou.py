"""Club del disc con stock agregado (condicion='nou'): la safata puede
incluir líneas nou (varias asignaciones/suscriptores pueden compartir la
misma línea, cada una consumiendo 1 unidad), usando StockHold en vez de
status/reserved_for_assignacio_id."""

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models import (
    Assignacio, CanalComissio, CobramentSubscripcio, ComissioPagament, CondicionItem, EstatAssignacio,
    EstatCobrament, EstatSubscripcio, Item, JournalEntry, JournalLine, JournalSourceType, ModeComissio, Order,
    OrderItem, Release, StockHold, Subscripcio, User,
)
from app.services.subscripcions import (
    confirmar_cobrament, ometre_assignacio, proposar_assignacio, reassignar_item,
)


def _seed_subscripcio(db, email="fan@example.com", ds_order="123abcdef01") -> tuple[Subscripcio, CobramentSubscripcio]:
    from app.models import Address

    user = User(email=email, name="Fan")
    db.add(user)
    db.flush()
    address = Address(user_id=user.id, recipient_name="Fan", address_line1="C. Falsa 1", city="BCN", postal_code="08001")
    db.add(address)
    db.flush()
    subscripcio = Subscripcio(
        user_id=user.id, address_id=address.id, periodicitat_mesos=1, quantitat=1,
        preu_periode=Decimal("25.00"), estat=EstatSubscripcio.activa,
        redsys_identifier="TOKEN-123", proxima_facturacio=date.today(),
    )
    db.add(subscripcio)
    db.flush()
    cobrament = CobramentSubscripcio(
        subscripcio_id=subscripcio.id, periode=date.today(), import_=Decimal("25.00"),
        estat=EstatCobrament.cobrat, ds_order=ds_order,
    )
    db.add(cobrament)
    db.commit()
    return subscripcio, cobrament


def _item_nou(db, cantidad=3, precio="22.00", pool=True) -> Item:
    release = Release(artista="Artista", title="Àlbum", formato="LP")
    db.add(release)
    db.flush()
    item = Item(
        release_id=release.id, price=Decimal(precio), condition=CondicionItem.nou,
        quantity=cantidad, subscription_pool=pool,
    )
    db.add(item)
    db.commit()
    return item


def test_proposar_reserva_1_unidad_via_stockhold(db):
    subscripcio, cobrament = _seed_subscripcio(db)
    item = _item_nou(db, cantidad=3)

    assignacions = proposar_assignacio(db, cobrament)
    db.commit()

    assert len(assignacions) == 1
    assert assignacions[0].item_id == item.id
    assert assignacions[0].estat == EstatAssignacio.proposada

    db.refresh(item)
    assert item.quantity == 3  # no se vende todavía, solo se reserva
    assert item.reserved_quantity == 1
    hold = db.scalar(select(StockHold).where(StockHold.item_id == item.id))
    assert hold is not None
    assert hold.assignacio_id == assignacions[0].id
    assert hold.reserved_until is None  # sin caducidad, lo marca el admin


def test_dos_suscriptores_comparten_la_misma_linia_nou(db):
    """La misma línea agregada puede servir a dos suscriptores distintos a
    la vez: cada asignación consume 1 unidad, no la fila entera."""
    _, cobrament1 = _seed_subscripcio(db, email="fan1@example.com", ds_order="aaaaaaaaaa01")
    _, cobrament2 = _seed_subscripcio(db, email="fan2@example.com", ds_order="bbbbbbbbbb02")
    item = _item_nou(db, cantidad=3)

    a1 = proposar_assignacio(db, cobrament1)
    db.commit()
    a2 = proposar_assignacio(db, cobrament2)
    db.commit()

    assert a1[0].item_id == item.id
    assert a2[0].item_id == item.id  # mismo disco, dos asignaciones distintas

    db.refresh(item)
    assert item.reserved_quantity == 2
    assert db.scalar(select(StockHold).where(StockHold.item_id == item.id)).quantity in (1,)
    holds = db.scalars(select(StockHold).where(StockHold.item_id == item.id)).all()
    assert len(holds) == 2


def test_ometre_assignacio_libera_hold_nou(db):
    _, cobrament = _seed_subscripcio(db)
    item = _item_nou(db, cantidad=3)
    assignacions = proposar_assignacio(db, cobrament)
    db.commit()

    ometre_assignacio(db, assignacions[0])
    db.commit()

    db.refresh(item)
    assert item.reserved_quantity == 0
    assert db.scalar(select(StockHold).where(StockHold.item_id == item.id)) is None
    assert assignacions[0].estat == EstatAssignacio.omesa
    assert assignacions[0].item_id is None


def test_reassignar_item_nou_a_nou(db):
    _, cobrament = _seed_subscripcio(db)
    item1 = _item_nou(db, cantidad=3, precio="20.00")
    item2 = _item_nou(db, cantidad=2, precio="18.00")
    assignacions = proposar_assignacio(db, cobrament)
    db.commit()
    assert assignacions[0].item_id == item1.id  # fecha_entrada más antigua (creado primero)

    reassignar_item(db, assignacions[0], item2)
    db.commit()

    db.refresh(item1)
    db.refresh(item2)
    assert item1.reserved_quantity == 0
    assert db.scalar(select(StockHold).where(StockHold.item_id == item1.id)) is None
    assert item2.reserved_quantity == 1
    assert db.scalar(select(StockHold).where(StockHold.item_id == item2.id)) is not None
    assert assignacions[0].item_id == item2.id


def test_confirmar_cobrament_vende_y_descuenta_cantidad(db):
    _, cobrament = _seed_subscripcio(db)
    item = _item_nou(db, cantidad=3, precio="22.00")
    assignacions = proposar_assignacio(db, cobrament)
    db.commit()

    order = confirmar_cobrament(db, cobrament)

    db.refresh(item)
    assert item.quantity == 2  # se vendió 1 unidad, la línea sigue viva
    assert item.reserved_quantity == 0
    assert db.scalar(select(StockHold).where(StockHold.item_id == item.id)) is None

    order_item = db.scalar(select(OrderItem).where(OrderItem.order_id == order.id))
    assert order_item.quantity == 1
    assert order_item.condition == CondicionItem.nou
    assert order_item.item_id == item.id

    db.refresh(assignacions[0])
    assert assignacions[0].estat == EstatAssignacio.confirmada


def test_confirmar_cobrament_tanca_automaticament_el_430(db):
    """El cobrament Redsys (COF/MIT) ja es va autoritzar a facturar_subscripcio
    — a diferència del checkout web, aquí no hi ha res a l'espera, es tanca
    ja mateix (ver docs/PLAN_COBRAMENTS_PAGAMENTS.md)."""
    _, cobrament = _seed_subscripcio(db)
    _item_nou(db, cantidad=3, precio="22.00")
    proposar_assignacio(db, cobrament)
    db.commit()

    order = confirmar_cobrament(db, cobrament)

    entries = db.scalars(
        select(JournalEntry).where(
            JournalEntry.source_type == JournalSourceType.venda_web, JournalEntry.source_id == order.id,
        )
    ).all()
    assert len(entries) == 2  # post_venda (obre) + el tancament automàtic (el tanca)
    tancament = next(e for e in entries if any(l.account.code == "572" for l in e.lines))
    lines = {l.account.code: (l.debit, l.credit) for l in tancament.lines}
    assert lines["572"] == (Decimal("25.00"), Decimal("0.00"))
    assert lines["430"] == (Decimal("0.00"), Decimal("25.00"))
    assert "626" not in lines


def test_confirmar_cobrament_amb_comissio_club_reconeix_626(db):
    db.add(ComissioPagament(
        canal=CanalComissio.club_targeta, mode=ModeComissio.deduccio,
        pct=Decimal("1.00"), fixed_fee=Decimal("0.00"),
    ))
    db.commit()

    _, cobrament = _seed_subscripcio(db)
    _item_nou(db, cantidad=3, precio="22.00")
    proposar_assignacio(db, cobrament)
    db.commit()

    order = confirmar_cobrament(db, cobrament)

    tancament = db.scalar(
        select(JournalEntry).where(
            JournalEntry.source_type == JournalSourceType.venda_web, JournalEntry.source_id == order.id,
        ).order_by(JournalEntry.entry_number.desc())
    )
    lines = {l.account.code: (l.debit, l.credit) for l in tancament.lines}
    # 25.00 * 1% = 0.25 de comissió
    assert lines["626"] == (Decimal("0.25"), Decimal("0.00"))
    assert lines["572"] == (Decimal("24.75"), Decimal("0.00"))
    assert lines["430"] == (Decimal("0.00"), Decimal("25.00"))
