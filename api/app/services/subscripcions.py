"""Club del disc: selecció automàtica dels exemplars a enviar (entre els que
l'admin ha marcat com a elegibles), cobrament recurrent per Redsys (COF) i
confirmació d'un enviament com a venda normal.

Dues fases separades a propòsit (veure discussió d'arquitectura a
`models.py`): el cobrament és automàtic i va per data (`facturar_subscripcio`,
cridat pel job de Celery); l'assignació dels exemplars concrets a un
cobrament (enviament) ja fet la revisa i confirma l'admin
(`proposar_assignacio` / `confirmar_cobrament`, cridats des de
`routers/admin_subscripcions.py`). Confirmar un cobrament reutilitza
`services/orders.py::finalize_payment` tal qual, així que la venda resultant
es comporta exactament com qualsevol altra comanda web.

L'algorisme d'assignació MAI tria lliurement de tot el catàleg: només entre
els exemplars que l'admin ha marcat (`Item.subscription_pool`) des de la
pantalla "Catàleg" del panell — el marge i l'antiguitat hi són com a eines
per ajudar l'admin a triar, no com a filtre automàtic aquí.
"""

import calendar
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from ..models import (
    Assignacio,
    CobramentSubscripcio,
    CondicionItem,
    EstatAssignacio,
    EstatCobrament,
    EstatSubscripcio,
    Item,
    ItemStatus,
    Order,
    OrderItem,
    OrderOrigen,
    OrderStatus,
    RecordProduct,
    Release,
    StockHold,
    Subscripcio,
)
from . import redsys
from .iva import compute_iva_venda
from .orders import finalize_payment

# Taxonomia de gèneres de Discogs (fixa, la fa servir Discogs mateix per
# etiquetar releases): `Release.genero` és un text amb un o més d'aquests,
# separats per ", " — però "Folk, World, & Country" ÉS un sol gènere amb
# comes al nom, així que mai es pot fer servir un split(","); el matching
# és sempre per substring (`ILIKE`), mateix patró que `routers/catalog.py`.
GENERES_DISCOGS = [
    "Blues", "Brass & Military", "Children's", "Classical", "Electronic",
    "Folk, World, & Country", "Funk / Soul", "Hip Hop", "Jazz", "Latin",
    "Non-Music", "Pop", "Reggae", "Rock", "Stage & Screen",
]


def _mes_seguent(any_: int, mes: int, n: int = 1) -> tuple[int, int]:
    """(any, mes) que cauen `n` mesos després de (any_, mes)."""
    mes_total = mes - 1 + n
    return any_ + mes_total // 12, mes_total % 12 + 1


def penultim_divendres(any_: int, mes: int) -> date:
    """Penúltim divendres del mes: la data de tall d'inscripció del cicle
    (dona com a mínim 3 setmanes obertes des de l'inici de cada mes fins
    al tall — tot mes en té almenys 4 divendres)."""
    ultim_dia = calendar.monthrange(any_, mes)[1]
    divendres = [
        date(any_, mes, dia) for dia in range(1, ultim_dia + 1)
        if date(any_, mes, dia).weekday() == 4
    ]
    return divendres[-2] if len(divendres) >= 2 else divendres[-1]


def primer_dia_habil(any_: int, mes: int) -> date:
    """Primer dia de dilluns a divendres del mes (sense calendari de
    festius: per una botiga petita, saltar-se caps de setmana ja n'hi ha
    prou) — el dia de facturació global del cicle."""
    d = date(any_, mes, 1)
    while d.weekday() >= 5:  # dissabte=5, diumenge=6
        d += timedelta(days=1)
    return d


def proxima_facturacio_alta(avui: date) -> date:
    """Cicle en què entra una alta feta avui: si és el penúltim divendres
    del mes actual o abans, es factura al 1r dia hàbil del mes vinent; si
    no, la finestra d'inscripció d'aquest mes ja ha tancat i s'espera un
    mes més (per donar temps a l'admin de tancar la tria del catàleg)."""
    tall = penultim_divendres(avui.year, avui.month)
    n = 1 if avui <= tall else 2
    any_, mes = _mes_seguent(avui.year, avui.month, n)
    return primer_dia_habil(any_, mes)


def proxima_facturacio_seguent(periode_actual: date, periodicitat_mesos: int) -> date:
    """1r dia hàbil del mes que cau `periodicitat_mesos` mesos després del
    cicle `periode_actual`. La fan servir tant `facturar_subscripcio` (per
    a renovacions MIT) com `redsys_notify_alta` (per fixar la 2a
    facturació just després de la 1a, que és la CIT de l'alta)."""
    any_, mes = _mes_seguent(periode_actual.year, periode_actual.month, periodicitat_mesos)
    return primer_dia_habil(any_, mes)


def _reservar_item(db: Session, item_id: uuid.UUID, assignacio_id: uuid.UUID) -> bool:
    """Reserva `item_id` para `assignacio_id`, sin caducidad (el ritmo lo
    marca el admin, no un cliente esperando). Para nou (stock agregado) usa
    un `StockHold` de 1 unidad en vez de status/reserved_for_assignacio_id,
    que solo tienen un titular posible a la vez — varias asignaciones
    pueden compartir la misma línea nou simultáneamente."""
    item = db.get(Item, item_id)
    if item is None:
        return False
    if item.condition == CondicionItem.nou:
        result = db.execute(
            update(Item)
            .where(Item.id == item_id, Item.quantity - Item.reserved_quantity >= 1)
            .values(reserved_quantity=Item.reserved_quantity + 1)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount == 1:
            db.add(StockHold(item_id=item_id, quantity=1, assignacio_id=assignacio_id))
        return result.rowcount == 1

    result = db.execute(
        update(Item)
        .where(Item.id == item_id, Item.status == ItemStatus.disponible)
        .values(status=ItemStatus.reservado, reserved_for_assignacio_id=assignacio_id)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1


def _liberar_item_de_assignacio(db: Session, item_id: uuid.UUID, assignacio_id: uuid.UUID) -> None:
    """Inverso de `_reservar_item`: libera la retención de esta asignación
    sobre este item, sea segona_ma (status) o nou (StockHold)."""
    item = db.get(Item, item_id)
    if item is not None and item.condition == CondicionItem.nou:
        hold = db.scalar(
            select(StockHold).where(StockHold.item_id == item_id, StockHold.assignacio_id == assignacio_id)
        )
        if hold is not None:
            db.execute(
                update(Item).where(Item.id == item_id)
                .values(reserved_quantity=Item.reserved_quantity - hold.quantity)
                .execution_options(synchronize_session=False)
            )
            db.delete(hold)
        return
    db.execute(
        update(Item)
        .where(Item.id == item_id, Item.reserved_for_assignacio_id == assignacio_id)
        .values(status=ItemStatus.disponible, reserved_for_assignacio_id=None)
        .execution_options(synchronize_session=False)
    )


def seleccionar_items_candidats(
    db: Session, subscripcio: Subscripcio, n: int, *, assignacio_ids: list[uuid.UUID],
) -> list[Item]:
    """Cerca fins a `n` exemplars per aquesta subscripció i els reserva
    atòmicament, un per cada id de `assignacio_ids` (mateix patró que
    `erp.py::_reservar_item_para_peticion`: `UPDATE ... WHERE status=
    'disponible'` comprovant files afectades, mai un SELECT previ + UPDATE).

    Candidats: **només `Item.subscription_pool == True`** (la safata que ha
    triat l'admin — mai tot el catàleg disponible), dins d'un dels gèneres
    preferits del client (si n'ha triat; substring sobre `Release.genero`,
    veure `GENERES_DISCOGS`), mai un `Release` que ja se li hagi confirmat
    abans NI un que ja s'hagi triat en aquesta mateixa crida (no enviar dues
    còpies del mateix àlbum en un sol paquet), prioritzant l'estoc més antic
    (`fecha_entrada` ascendent, mateix criteri que
    `admin.py::_aging_dias_disponibles`) com a desempat dins la safata.

    Si hi ha menys candidats que `n`, retorna els que hagi trobat: la resta
    d'`assignacio_ids` es deixen sense item (`sense_match`)."""
    releases_rebuts = set(db.scalars(
        select(Assignacio.release_id).where(
            Assignacio.subscripcio_id == subscripcio.id,
            Assignacio.estat == EstatAssignacio.confirmada,
            Assignacio.release_id.is_not(None),
        )
    ))
    releases_triats: set[uuid.UUID] = set()

    stmt = (
        select(Item)
        .join(Release, Item.release_id == Release.id)
        .outerjoin(RecordProduct, RecordProduct.release_id == Release.id)
        .where(
            Item.status == ItemStatus.disponible,
            Item.subscription_pool.is_(True),
            # nou (stock agregado): solo cuenta si queda alguna unidad libre;
            # segona_ma ya lo garantiza el filtro de status de arriba.
            or_(Item.condition != CondicionItem.nou, Item.quantity > Item.reserved_quantity),
        )
        .order_by(Item.entry_date.asc().nulls_last())
    )
    if subscripcio.generes_preferits:
        stmt = stmt.where(or_(*(RecordProduct.genero.ilike(f"%{g}%") for g in subscripcio.generes_preferits)))

    triats: list[Item] = []
    ids_pendents = iter(assignacio_ids)
    assignacio_id = next(ids_pendents, None)

    for item in db.scalars(stmt):
        if assignacio_id is None:
            break
        if item.release_id in releases_rebuts or item.release_id in releases_triats:
            continue
        if not _reservar_item(db, item.id, assignacio_id):
            continue  # un altre procés l'ha agafat mentre iteràvem; provem el següent
        db.refresh(item)
        triats.append(item)
        releases_triats.add(item.release_id)
        assignacio_id = next(ids_pendents, None)

    return triats


def cobraments_pendents_assignacio(db: Session) -> list[CobramentSubscripcio]:
    """Cobraments ja fets que encara no tenen cap `Assignacio` (la cua de
    feina de l'admin a `/admin/subscripcions`)."""
    return list(db.scalars(
        select(CobramentSubscripcio)
        .outerjoin(Assignacio, Assignacio.cobrament_id == CobramentSubscripcio.id)
        .where(CobramentSubscripcio.estat == EstatCobrament.cobrat, Assignacio.id.is_(None))
        .order_by(CobramentSubscripcio.created_at)
    ))


def proposar_assignacio(db: Session, cobrament: CobramentSubscripcio) -> list[Assignacio]:
    """Crea la proposta automàtica per a un cobrament pendent: tantes files
    `Assignacio` com `subscripcio.quantitat`. No fa commit: el crida
    l'endpoint `/admin/subscripcions/proposar` en bloc per a tots els
    cobraments pendents, un sol commit al final."""
    subscripcio = cobrament.subscripcio
    assignacions = [
        Assignacio(cobrament_id=cobrament.id, subscripcio_id=subscripcio.id)
        for _ in range(subscripcio.quantitat)
    ]
    db.add_all(assignacions)
    db.flush()  # calen els ids per reservar-hi els items

    items = seleccionar_items_candidats(
        db, subscripcio, subscripcio.quantitat, assignacio_ids=[a.id for a in assignacions],
    )
    for assignacio, item in zip(assignacions, items):
        assignacio.item_id = item.id
        assignacio.release_id = item.release_id
    for assignacio in assignacions[len(items):]:
        assignacio.estat = EstatAssignacio.sense_match

    return assignacions


def reintentar_sense_match(db: Session, cobrament: CobramentSubscripcio) -> list[Assignacio]:
    """Torna a buscar exemplar per als discos d'aquest enviament que van
    quedar `sense_match` (típicament perquè la safata era buida o massa
    curta en el moment de proposar). Útil després d'afegir més exemplars a
    la safata: no cal esperar un cobrament nou, es reintenta el mateix.
    Les files ja `proposada`/`confirmada`/`omesa` no es toquen."""
    pendents = [a for a in cobrament.assignacions if a.estat == EstatAssignacio.sense_match]
    if not pendents:
        return []

    items = seleccionar_items_candidats(
        db, cobrament.subscripcio, len(pendents), assignacio_ids=[a.id for a in pendents],
    )
    for assignacio, item in zip(pendents, items):
        assignacio.item_id = item.id
        assignacio.release_id = item.release_id
        assignacio.estat = EstatAssignacio.proposada

    return pendents


def reassignar_item(db: Session, assignacio: Assignacio, nou_item: Item) -> None:
    """Substitueix l'exemplar d'una proposta encara no confirmada (l'admin
    l'ha triat a mà, típicament des de la safata). Allibera l'anterior si
    n'hi havia."""
    if assignacio.estat not in (EstatAssignacio.proposada, EstatAssignacio.sense_match):
        raise ValueError("Només es poden reassignar propostes encara no confirmades")
    disponible = (
        nou_item.quantity > nou_item.reserved_quantity
        if nou_item.condition == CondicionItem.nou else nou_item.status == ItemStatus.disponible
    )
    if not disponible:
        raise ValueError("Aquest exemplar ja no està disponible")

    if assignacio.item_id is not None:
        _liberar_item_de_assignacio(db, assignacio.item_id, assignacio.id)

    if not _reservar_item(db, nou_item.id, assignacio.id):
        raise ValueError("Aquest exemplar ja no està disponible")

    assignacio.item_id = nou_item.id
    assignacio.release_id = nou_item.release_id
    assignacio.estat = EstatAssignacio.proposada


def ometre_assignacio(db: Session, assignacio: Assignacio) -> None:
    """L'admin descarta la proposta per aquest disc (allibera l'exemplar
    reservat). No toca la resta de l'enviament."""
    if assignacio.item_id is not None:
        _liberar_item_de_assignacio(db, assignacio.item_id, assignacio.id)
        assignacio.item_id = None
    assignacio.estat = EstatAssignacio.omesa


def confirmar_cobrament(db: Session, cobrament: CobramentSubscripcio) -> Order:
    """Converteix un enviament validat en una venda normal: crea **un sol**
    `Order` amb una `OrderItem` per cada disc de l'enviament (origen=
    subscripcio), i reutilitza `finalize_payment` (marca els items venuts,
    treu els listings de Discogs, envia l'email de confirmació). A partir
    d'aquí la comanda es gestiona exactament igual que qualsevol venda web a
    `/admin/vendes-web`.

    El total de la comanda és sempre `cobrament.import_` (el que ja s'ha
    cobrat), independentment de quants discs s'hagin pogut trobar: si la
    safata s'ha quedat curta i només n'hi ha, per exemple, 2 dels 3 pagats,
    es reparteix igualment el total entre els 2 (el client no pot rebre
    menys valor del que ha pagat)."""
    assignacions = [
        a for a in cobrament.assignacions
        if a.estat == EstatAssignacio.proposada and a.item_id is not None
    ]
    if not assignacions:
        raise ValueError("Aquest enviament no té cap exemplar per confirmar")

    subscripcio = cobrament.subscripcio
    address = subscripcio.address

    order = Order(
        user_id=subscripcio.user_id,
        contact_email=subscripcio.user.email,
        status=OrderStatus.pendiente_pago,
        origin=OrderOrigen.subscripcio,
        total=cobrament.import_,
        shipping_method="envio",
        payment_method="redsys",
        shipping_address={
            "recipient_name": address.recipient_name,
            "address_line1": address.address_line1,
            "address_line2": address.address_line2,
            "city": address.city,
            "postal_code": address.postal_code,
            "province": address.province,
            "country": address.country,
            "phone": address.phone,
        },
    )
    db.add(order)
    db.flush()

    n = len(assignacions)
    preu_linia = (cobrament.import_ / n).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    diferencia = cobrament.import_ - preu_linia * n  # cèntims d'arrodoniment, per quadrar la suma

    for i, assignacio in enumerate(assignacions):
        preu = preu_linia + (diferencia if i == n - 1 else Decimal("0"))
        item = assignacio.item
        tipus_iva_id, iva_pct, iva_import = compute_iva_venda(item, preu, db)
        db.add(OrderItem(
            order_id=order.id, item_id=item.id, price=preu, quantity=1, condition=item.condition,
            tipus_iva_id=tipus_iva_id, vat_pct=iva_pct, vat_amount=iva_import,
        ))
        if item.condition == CondicionItem.nou:
            # finalize_payment (reutilizado tal cual) busca el StockHold por
            # cart_id/order_id, no por assignacio_id: se reasigna aquí,
            # mismo criterio que checkout.py con el pago en tienda.
            hold = db.scalar(
                select(StockHold).where(StockHold.item_id == item.id, StockHold.assignacio_id == assignacio.id)
            )
            if hold is not None:
                hold.assignacio_id = None
                hold.order_id = order.id
        assignacio.estat = EstatAssignacio.confirmada
        assignacio.order_id = order.id
        assignacio.confirmada_at = datetime.now(timezone.utc)

    # Els discos d'aquest mateix enviament que s'han quedat `sense_match`
    # (la safata no tenia prou exemplars per arribar a la quantitat pagada)
    # es tanquen com a `omesa`: l'enviament ja s'ha confirmat amb el que hi
    # havia, i deixar-los `sense_match` els convertiria en un enviament
    # "fantasma" que reapareixeria per sempre a la pantalla de revisió.
    for assignacio in cobrament.assignacions:
        if assignacio.estat == EstatAssignacio.sense_match:
            assignacio.estat = EstatAssignacio.omesa

    # Autoflush està desactivat (veure database.py): sense aquest flush,
    # la consulta que fa finalize_payment per trobar les OrderItem que
    # acabem d'afegir no les veuria encara, i vendria la comanda per bona
    # sense marcar realment els items com a venuts.
    db.flush()

    # finalize_payment fa el seu propi commit; com que és la mateixa sessió,
    # s'hi enduu també els canvis fets just abans (assignacions incloses).
    failed = finalize_payment(db, order)
    if failed:
        raise RuntimeError(
            "No s'ha pogut confirmar: algun dels exemplars assignats ja no estava "
            "disponible (reviseu l'enviament i torneu-hi)"
        )
    return order


def facturar_subscripcio(db: Session, subscripcio: Subscripcio) -> CobramentSubscripcio:
    """Cobra el període vençut d'una subscripció activa via COF (Redsys,
    servidor-a-servidor amb l'`identifier` capturat a l'alta) i avança
    `proxima_facturacio` al següent cicle mensual (1r dia hàbil del mes que
    toqui) si s'autoritza. No toca res d'`Assignacio`/`Order`: això és
    feina posterior de l'admin."""
    periode = subscripcio.proxima_facturacio
    ds_order = redsys.generate_ds_order()
    resultat = redsys.charge_recurring(
        ds_order=ds_order, importe=subscripcio.preu_periode, identifier=subscripcio.redsys_identifier,
        cof_txnid=subscripcio.redsys_cof_txnid,
    )
    autoritzat = resultat is not None and redsys.is_authorised(resultat.get("Ds_Response"))

    cobrament = CobramentSubscripcio(
        subscripcio_id=subscripcio.id,
        periode=periode,
        import_=subscripcio.preu_periode,
        estat=EstatCobrament.cobrat if autoritzat else EstatCobrament.fallit,
        ds_order=ds_order,
        raw_notification=resultat,
    )
    db.add(cobrament)
    if autoritzat:
        subscripcio.proxima_facturacio = proxima_facturacio_seguent(periode, subscripcio.periodicitat_mesos)
    db.commit()
    db.refresh(cobrament)
    return cobrament


def facturar_subscripcions_vencudes(db: Session) -> list[CobramentSubscripcio]:
    """Cobra totes les subscripcions actives amb `proxima_facturacio` vençuda
    avui (cridat pel job diari de Celery, veure tasks/subscripcions.py). Un
    cobrament fallit no avança la data: es reintenta l'endemà, en la
    següent execució d'aquesta mateixa funció."""
    avui = datetime.now(timezone.utc).date()
    subscripcions = list(db.scalars(
        select(Subscripcio).where(
            Subscripcio.estat == EstatSubscripcio.activa,
            Subscripcio.proxima_facturacio <= avui,
        )
    ))
    return [facturar_subscripcio(db, s) for s in subscripcions]
