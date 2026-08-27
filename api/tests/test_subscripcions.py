"""Tests de l'algorisme de selecció d'exemplars per al club del disc
(services/subscripcions.py): només tria entre els exemplars que l'admin ha
marcat com a elegibles (`Item.subscripcio_pool`), no repetir mai un
`Release` ja confirmat ni dos cops dins del mateix enviament, preferència de
gènere musical, prioritat per antiguitat de l'estoc, i reserva atòmica dels
ítems triats."""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.models import (
    Address,
    Assignacio,
    CobramentSubscripcio,
    EstatAssignacio,
    EstatCobrament,
    Item,
    ItemStatus,
    Release,
    Subscripcio,
    User,
)
from app.services.subscripcions import proposar_assignacio, seleccionar_items_candidats


def _user(db, email="client@example.com") -> User:
    u = User(email=email, name="Client")
    db.add(u)
    db.commit()
    return u


def _address(db, user: User) -> Address:
    a = Address(
        user_id=user.id, recipient_name="Client", address_line1="Carrer Fals 1",
        city="Barcelona", postal_code="08001", country="ES",
    )
    db.add(a)
    db.commit()
    return a


def _subscripcio(db, user: User, address: Address, *, generes=None, quantitat=1) -> Subscripcio:
    s = Subscripcio(
        user_id=user.id, address_id=address.id, generes_preferits=generes,
        periodicitat_mesos=1, quantitat=quantitat, preu_periode=Decimal("25.00") * quantitat,
        proxima_facturacio=date.today(),
    )
    db.add(s)
    db.commit()
    return s


def _release(db, artista="Artista", titulo="Àlbum", genero=None) -> Release:
    r = Release(artista=artista, title=titulo, formato="LP", genero=genero)
    db.add(r)
    db.commit()
    return r


def _item(db, release: Release, precio: str = "20.00", dies_entrada: int = 0, pool: bool = True) -> Item:
    i = Item(
        release_id=release.id, price=Decimal(precio), status=ItemStatus.disponible,
        entry_date=datetime.now(timezone.utc) - timedelta(days=dies_entrada),
        subscription_pool=pool,
    )
    db.add(i)
    db.commit()
    return i


def _cobrament(db, subscripcio: Subscripcio) -> CobramentSubscripcio:
    c = CobramentSubscripcio(
        subscripcio_id=subscripcio.id, periode=date.today(), import_=subscripcio.preu_periode,
        estat=EstatCobrament.cobrat, ds_order=uuid.uuid4().hex[:12],
    )
    db.add(c)
    db.commit()
    return c


def _assignacio_buida(db, subscripcio: Subscripcio) -> Assignacio:
    cobrament = _cobrament(db, subscripcio)
    assignacio = Assignacio(cobrament_id=cobrament.id, subscripcio_id=subscripcio.id)
    db.add(assignacio)
    db.commit()
    return assignacio


def test_nomes_tria_items_del_pool(db):
    user = _user(db)
    subscripcio = _subscripcio(db, user, _address(db, user))
    release = _release(db)
    _item(db, release, pool=False)  # fora de la safata -> exclòs encara que sigui l'únic disponible

    assignacio = _assignacio_buida(db, subscripcio)
    triats = seleccionar_items_candidats(db, subscripcio, 1, assignacio_ids=[assignacio.id])

    assert triats == []


def test_reserva_atomicament_litem_del_pool_triat(db):
    user = _user(db)
    subscripcio = _subscripcio(db, user, _address(db, user))
    release = _release(db)
    dins = _item(db, release, pool=True)

    assignacio = _assignacio_buida(db, subscripcio)
    triats = seleccionar_items_candidats(db, subscripcio, 1, assignacio_ids=[assignacio.id])

    assert [i.id for i in triats] == [dins.id]
    assert dins.status == ItemStatus.reservado
    assert dins.reserved_for_assignacio_id == assignacio.id


def test_prioritza_estoc_mes_antic(db):
    user = _user(db)
    subscripcio = _subscripcio(db, user, _address(db, user))
    release = _release(db)
    recent = _item(db, release, dies_entrada=2)
    antic = _item(db, _release(db, titulo="Un altre"), dies_entrada=200)

    assignacio = _assignacio_buida(db, subscripcio)
    triats = seleccionar_items_candidats(db, subscripcio, 1, assignacio_ids=[assignacio.id])

    assert [i.id for i in triats] == [antic.id]
    assert recent.status == ItemStatus.disponible  # no s'ha tocat


def test_no_repeteix_un_release_ja_confirmat(db):
    user = _user(db)
    subscripcio = _subscripcio(db, user, _address(db, user))
    release_rebut = _release(db, titulo="Ja el té")
    _item(db, release_rebut)
    release_nou = _release(db, titulo="Encara no el té")
    nou = _item(db, release_nou)

    # Simula un enviament anterior ja confirmat per aquest mateix disc.
    cobrament_previ = _cobrament(db, subscripcio)
    db.add(Assignacio(
        cobrament_id=cobrament_previ.id, subscripcio_id=subscripcio.id,
        release_id=release_rebut.id, estat=EstatAssignacio.confirmada,
    ))
    db.commit()

    assignacio = _assignacio_buida(db, subscripcio)
    triats = seleccionar_items_candidats(db, subscripcio, 1, assignacio_ids=[assignacio.id])

    assert [i.id for i in triats] == [nou.id]


def test_respecta_generes_preferits(db):
    user = _user(db)
    subscripcio = _subscripcio(db, user, _address(db, user), generes=["Jazz"])
    release_rock = _release(db, titulo="De Rock", genero="Rock")
    _item(db, release_rock)
    release_jazz = _release(db, titulo="De Jazz", genero="Jazz, Funk / Soul")
    esperat = _item(db, release_jazz)

    assignacio = _assignacio_buida(db, subscripcio)
    triats = seleccionar_items_candidats(db, subscripcio, 1, assignacio_ids=[assignacio.id])

    assert [i.id for i in triats] == [esperat.id]


def test_no_confon_folk_world_country_amb_country_solt(db):
    # "Folk, World, & Country" és UN sol gènere de Discogs (amb comes al
    # nom): un client que tria aquest gènere ha de trobar-lo per substring
    # complet, no per un split ingenu que el trossejaria.
    user = _user(db)
    subscripcio = _subscripcio(db, user, _address(db, user), generes=["Folk, World, & Country"])
    release = _release(db, genero="Electronic, Folk, World, & Country")
    esperat = _item(db, release)

    assignacio = _assignacio_buida(db, subscripcio)
    triats = seleccionar_items_candidats(db, subscripcio, 1, assignacio_ids=[assignacio.id])

    assert [i.id for i in triats] == [esperat.id]


def test_sense_candidats_retorna_llista_buida_i_marca_sense_match(db):
    user = _user(db)
    subscripcio = _subscripcio(db, user, _address(db, user))
    release = _release(db)
    _item(db, release, pool=False)  # únic disc disponible, però fora de la safata

    cobrament = _cobrament(db, subscripcio)
    assignacions = proposar_assignacio(db, cobrament)
    db.commit()

    assert len(assignacions) == 1
    assert assignacions[0].estat == EstatAssignacio.sense_match
    assert assignacions[0].item_id is None


def test_quantitat_multiple_reserva_n_items_diferents(db):
    user = _user(db)
    subscripcio = _subscripcio(db, user, _address(db, user), quantitat=3)
    items = [_item(db, _release(db, titulo=f"Disc {i}"), dies_entrada=i) for i in range(5)]

    cobrament = _cobrament(db, subscripcio)
    assignacions = proposar_assignacio(db, cobrament)
    db.commit()

    assert len(assignacions) == 3
    assert all(a.estat == EstatAssignacio.proposada for a in assignacions)
    item_ids_triats = {a.item_id for a in assignacions}
    assert len(item_ids_triats) == 3  # tres discos diferents
    # prioritza els més antics (index 4, 3, 2 -> dies_entrada 4, 3, 2)
    assert item_ids_triats == {items[4].id, items[3].id, items[2].id}


def test_quantitat_multiple_mai_repeteix_release_dins_del_mateix_enviament(db):
    # quantitat=3 però només hi ha 2 releases diferents a la safata (un d'ells
    # amb dues còpies físiques): el tercer slot no s'ha de poder omplir amb
    # una segona còpia del mateix àlbum, ha de quedar sense_match.
    user = _user(db)
    subscripcio = _subscripcio(db, user, _address(db, user), quantitat=3)
    release = _release(db)
    item_a = _item(db, release, precio="10.00")
    _item(db, release, precio="20.00")  # mateix release, segona còpia -> mai s'ha de triar
    altre_release = _release(db, titulo="Un altre")
    item_b = _item(db, altre_release)

    cobrament = _cobrament(db, subscripcio)
    assignacions = proposar_assignacio(db, cobrament)
    db.commit()

    amb_item = [a for a in assignacions if a.item_id is not None]
    assert len(amb_item) == 2
    assert {a.item_id for a in amb_item} == {item_a.id, item_b.id}
    sense = [a for a in assignacions if a.item_id is None]
    assert len(sense) == 1
    assert sense[0].estat == EstatAssignacio.sense_match
