"""Reserva atómica de ejemplares únicos (segona_ma) y de stock agregado (nou).

El patrón clave de toda la tienda: cada Item de segunda mano es una copia
física que solo puede comprar una persona. La reserva se hace con un UPDATE
condicionado (status='disponible') y comprobando las filas afectadas — nunca
con un SELECT previo seguido de UPDATE, que abriría una condición de carrera.

Además, la reserva se ata al carrito que la hizo (reserved_by_cart_id): sin
esto, cualquier carrito podría "confirmar" un ejemplar que otro cliente tiene
legítimamente reservado, robándole la compra.

Para discos nuevos (condicion='nou'), una línea `Item` representa cantidad
agregada, no una copia única: puede tener varias reservas simultáneas de
orígenes distintos (varios carritos por las últimas unidades, una petición de
cliente, una asignación de club...). Las funciones de la segunda mitad de
este archivo (`reserve_stock`, `release_stock_hold`, `confirm_stock_sale`)
gestionan esto con el mismo patrón UPDATE-y-comprobar-rowcount, pero contra
`Item.quantity`/`reserved_quantity` y una tabla de retenciones (`StockHold`)
en vez de las columnas `status`/`reserved_*`, que solo tienen un titular
posible a la vez y por tanto no sirven para cantidad agregada.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from ..models import (
    CondicionItem, ConfiguracioBotiga, EstadoPeticionCliente, Item, ItemStatus, Order, OrderItem,
    OrderStatus, PeticionCliente, StockHold,
)

# Los UPDATE masivos no sincronizan la sesión: trabajamos con rowcount
# y refresh explícitos, y la evaluación en memoria es frágil e innecesaria.
_OPTS = {"synchronize_session": False}


def reservation_minutes(db: Session) -> int:
    config = db.scalar(select(ConfiguracioBotiga))
    return config.reservation_minutes if config else 20


def release_expired(db: Session) -> int:
    """Devuelve a 'disponible' las reservas caducadas (tanto las del carrito
    como las reservas de 72h de una PeticionCliente o de un Order 'paga en
    tienda' que recoge y paga en tienda). Se llama de forma perezosa antes
    de operar con el stock (no hace falta un cron aparte, aunque también
    hay una tarea Celery que la invoca periódicamente para poder avisar por
    email — ver tasks/peticiones.py).

    Les peticions afectades es localitzen per `PeticionCliente.item_id`, NO
    per `Item.reserved_for_peticion_id`: aquest segon camp es buida en
    transferir la reserva cap al carret (Via 1, veure
    `claim_peticion_item_for_cart`), així que si una petició "Comprar ara"
    caduca sense completar el checkout, `reserved_for_peticion_id` ja és
    None i la petició es quedaria zombi (reservada per sempre, sense cap
    exemplar reservat de veritat) si mirés aquell camp.

    Els `Order` amb `metodo_pago='tienda'` es localitzen per `OrderItem.item_id`
    (cada item només pot estar en un `OrderItem`, veure `order_items.item_id`
    UNIQUE): si ningú ve a recollir i pagar en 72h, la comanda es cancel·la
    igual que una PeticionCliente caduca, en comptes de quedar-se
    `pendiente_pago` per sempre sense que ningú se n'assabenti."""
    items_a_alliberar = list(db.scalars(
        select(Item.id)
        .where(
            Item.status == ItemStatus.reservado,
            Item.reserved_until < datetime.now(timezone.utc),
        )
    ))
    if not items_a_alliberar:
        return _release_expired_stock_holds(db)

    peticiones_afectadas = list(db.scalars(
        select(PeticionCliente.id)
        .where(
            PeticionCliente.item_id.in_(items_a_alliberar),
            PeticionCliente.status == EstadoPeticionCliente.reservada,
        )
    ))
    orders_afectades = list(db.scalars(
        select(OrderItem.order_id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            OrderItem.item_id.in_(items_a_alliberar),
            Order.status == OrderStatus.pendiente_pago,
            Order.payment_method == "tienda",
        )
        .distinct()
    ))
    result = db.execute(
        update(Item)
        .where(Item.id.in_(items_a_alliberar))
        .values(
            status=ItemStatus.disponible, reserved_until=None,
            reserved_by_cart_id=None, reserved_for_peticion_id=None,
        )
        .execution_options(**_OPTS)
    )
    if peticiones_afectadas:
        db.execute(
            update(PeticionCliente)
            .where(PeticionCliente.id.in_(peticiones_afectadas))
            .values(status=EstadoPeticionCliente.caducada)
            .execution_options(**_OPTS)
        )
    if orders_afectades:
        db.execute(
            update(Order)
            .where(Order.id.in_(orders_afectades))
            .values(status=OrderStatus.cancelado)
            .execution_options(**_OPTS)
        )
    db.commit()
    total_alliberats = result.rowcount
    total_alliberats += _release_expired_stock_holds(db)
    return total_alliberats


def _release_expired_stock_holds(db: Session) -> int:
    """Parte de `release_expired` para stock agregado (nou): cada `StockHold`
    caducado se localiza y se libera individualmente (a diferencia de la
    segunda mano, aquí NO se puede hacer un UPDATE masivo por Item, porque
    varias retenciones pueden compartir la misma línea y cada una libera
    solo su propia cantidad). `reserved_until IS NULL` significa "sin
    caducidad" (p.ej. retención de club) y nunca se barre aquí."""
    expirats = list(db.scalars(
        select(StockHold).where(
            StockHold.reserved_until.is_not(None),
            StockHold.reserved_until < datetime.now(timezone.utc),
        )
    ))
    for hold in expirats:
        db.execute(
            update(Item)
            .where(Item.id == hold.item_id)
            .values(reserved_quantity=Item.reserved_quantity - hold.quantity)
            .execution_options(**_OPTS)
        )
        if hold.peticion_id:
            db.execute(
                update(PeticionCliente)
                .where(PeticionCliente.id == hold.peticion_id, PeticionCliente.status == EstadoPeticionCliente.reservada)
                .values(status=EstadoPeticionCliente.caducada)
                .execution_options(**_OPTS)
            )
        if hold.order_id:
            db.execute(
                update(Order)
                .where(
                    Order.id == hold.order_id, Order.status == OrderStatus.pendiente_pago,
                    Order.payment_method == "tienda",
                )
                .values(status=OrderStatus.cancelado)
                .execution_options(**_OPTS)
            )
        db.delete(hold)
    if expirats:
        db.commit()
    return len(expirats)


def claim_peticion_item_for_cart(db: Session, item_id: uuid.UUID, peticion_id: uuid.UUID, cart_id: uuid.UUID) -> bool:
    """Transfereix la reserva d'un Item retingut per a una PeticionCliente
    (reserved_for_peticion_id) cap a una reserva normal de carret, per
    poder seguir amb el checkout habitual. Mai passa per 'disponible' pel
    mig: transició atòmica directa, com la resta de reserves d'aquest
    fitxer. Retorna False si l'ítem ja no estava retingut per aquesta
    petició (algú l'ha alliberat, ja s'ha venut, etc.)."""
    release_expired(db)
    until = datetime.now(timezone.utc) + timedelta(minutes=reservation_minutes(db))
    result = db.execute(
        update(Item)
        .where(
            Item.id == item_id, Item.status == ItemStatus.reservado,
            Item.reserved_for_peticion_id == peticion_id,
        )
        .values(reserved_by_cart_id=cart_id, reserved_for_peticion_id=None, reserved_until=until)
        .execution_options(**_OPTS)
    )
    db.commit()
    return result.rowcount == 1


def reserve_items(db: Session, item_ids: list[uuid.UUID], cart_id: uuid.UUID) -> list[uuid.UUID]:
    """Intenta reservar todos los ejemplares para `cart_id`. Todo o nada.

    Devuelve la lista de ids que NO se pudieron reservar (vacía = éxito).
    Si alguno falla, se revierten las reservas conseguidas en este intento.

    Idempotent per als ítems que aquest MATEIX carret ja tenia reservats
    (per exemple, un exemplar de PeticionCliente transferit amb
    `claim_peticion_item_for_cart`, o si `/checkout/start` es crida dues
    vegades): sense això, la segona crida els trobaria amb status='reservado'
    (no 'disponible') i els donaria per no disponibles, bloquejant el
    checkout. Reserva-hi de nou allarga la finestra de reserva."""
    release_expired(db)
    until = datetime.now(timezone.utc) + timedelta(minutes=reservation_minutes(db))

    reserved: list[uuid.UUID] = []
    failed: list[uuid.UUID] = []
    for item_id in item_ids:
        result = db.execute(
            update(Item)
            .where(
                Item.id == item_id,
                or_(
                    Item.status == ItemStatus.disponible,
                    and_(Item.status == ItemStatus.reservado, Item.reserved_by_cart_id == cart_id),
                ),
            )
            .values(status=ItemStatus.reservado, reserved_until=until, reserved_by_cart_id=cart_id)
            .execution_options(**_OPTS)
        )
        if result.rowcount == 1:
            reserved.append(item_id)
        else:
            failed.append(item_id)

    if failed:
        # revertir lo reservado en este intento
        db.execute(
            update(Item)
            .where(Item.id.in_(reserved))
            .values(status=ItemStatus.disponible, reserved_until=None, reserved_by_cart_id=None)
            .execution_options(**_OPTS)
        )
        db.commit()
        return failed

    db.commit()
    return []


def confirm_sale(db: Session, item_ids: list[uuid.UUID], cart_id: uuid.UUID) -> list[uuid.UUID]:
    """Vende ejemplares reservados por `cart_id`. Todo o nada: si alguno no
    está reservado por ESTE carrito (nunca se llegó a reservar, la reserva
    caducó, se vendió a otro, o la reserva viva pertenece a otro carrito), no
    se vende ninguno y se devuelven los ids que fallaron. Debe llamarse ANTES
    de crear el pedido, para que sea imposible confirmar una compra sin una
    reserva viva propia (ver checkout.confirm_checkout)."""
    release_expired(db)
    vendidos: list[uuid.UUID] = []
    failed: list[uuid.UUID] = []
    for item_id in item_ids:
        result = db.execute(
            update(Item)
            .where(
                Item.id == item_id,
                Item.status == ItemStatus.reservado,
                Item.reserved_by_cart_id == cart_id,
            )
            .values(status=ItemStatus.vendido, reserved_until=None, reserved_by_cart_id=None)
            .execution_options(**_OPTS)
        )
        if result.rowcount == 1:
            vendidos.append(item_id)
        else:
            failed.append(item_id)

    if failed:
        # revertir lo vendido en este intento (vuelve a reservado por este
        # mismo carrito, no a disponible: la reserva original seguía viva)
        db.execute(
            update(Item)
            .where(Item.id.in_(vendidos))
            .values(status=ItemStatus.reservado, reserved_by_cart_id=cart_id)
            .execution_options(**_OPTS)
        )
        db.commit()
        return failed

    db.commit()
    return []


def release_items(db: Session, item_ids: list[uuid.UUID]) -> None:
    """Para cancelaciones de pedido: el ejemplar vuelve a la venta."""
    db.execute(
        update(Item)
        .where(
            Item.id.in_(item_ids),
            or_(Item.status == ItemStatus.reservado, Item.status == ItemStatus.vendido),
        )
        .values(
            status=ItemStatus.disponible, reserved_until=None,
            reserved_by_cart_id=None, reserved_for_peticion_id=None,
        )
        .execution_options(**_OPTS)
    )
    db.commit()


# ---------------------------------------------------------------------------
# Stock agregado (condicion='nou'): ver docstring del módulo.
# ---------------------------------------------------------------------------

def reserve_stock(
    db: Session,
    item_id: uuid.UUID,
    cantidad: int,
    *,
    cart_id: uuid.UUID | None = None,
    peticion_id: uuid.UUID | None = None,
    assignacio_id: uuid.UUID | None = None,
    order_id: uuid.UUID | None = None,
    ttl_minutes: int | None = None,
) -> uuid.UUID | None:
    """Intenta retener `cantidad` unidades de una línea `nou`. Todo o nada.

    Exactamente uno de cart_id/peticion_id/assignacio_id/order_id debe venir
    relleno (identifica el origen de la retención, ver `StockHold`).
    `ttl_minutes=None` = retención sin caducidad automática (peticiones y
    asignaciones de club se liberan a mano, no por temporizador).

    Devuelve el id del `StockHold` creado, o None si no había suficiente
    stock libre (`cantidad - cantidad_reservada < cantidad` pedida).

    Idempotente para el mismo cart_id: si ya había un hold de este carrito
    sobre esta línea (p.ej. el cliente cambió la cantidad en el carrito y
    volvió a /checkout/start), se libera y se sustituye por uno nuevo con la
    cantidad actual, en vez de sumarse — igual que `reserve_items` no
    duplica la reserva sobre el mismo item+carrito, solo que ahí basta con
    un UPDATE porque la cantidad siempre es 1."""
    assert sum(x is not None for x in (cart_id, peticion_id, assignacio_id, order_id)) == 1, (
        "reserve_stock: origen de la retención ambiguo o ausente"
    )
    if cart_id is not None:
        existing = db.scalar(select(StockHold).where(StockHold.item_id == item_id, StockHold.cart_id == cart_id))
        if existing is not None:
            release_stock_hold(db, existing.id)
    release_expired(db)
    until = (
        datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
        if ttl_minutes is not None else None
    )
    result = db.execute(
        update(Item)
        .where(
            Item.id == item_id,
            Item.condition == CondicionItem.nou,
            Item.quantity - Item.reserved_quantity >= cantidad,
        )
        .values(reserved_quantity=Item.reserved_quantity + cantidad)
        .execution_options(**_OPTS)
    )
    if result.rowcount != 1:
        db.commit()
        return None

    hold = StockHold(
        item_id=item_id, quantity=cantidad, cart_id=cart_id, peticion_id=peticion_id,
        assignacio_id=assignacio_id, order_id=order_id, reserved_until=until,
    )
    db.add(hold)
    db.commit()
    db.refresh(hold)
    return hold.id


def release_stock_hold(db: Session, hold_id: uuid.UUID) -> bool:
    """Libera una retención (quitar del carrito, cancelar pedido, omitir
    asignación de club...): devuelve su cantidad a la venta y borra el hold.
    Devuelve False si el hold ya no existía (p.ej. caducó antes)."""
    hold = db.get(StockHold, hold_id)
    if hold is None:
        return False
    db.execute(
        update(Item)
        .where(Item.id == hold.item_id)
        .values(reserved_quantity=Item.reserved_quantity - hold.quantity)
        .execution_options(**_OPTS)
    )
    db.delete(hold)
    db.commit()
    return True


def confirm_stock_sale(db: Session, hold_id: uuid.UUID) -> int | None:
    """Vende las unidades retenidas por `hold_id`: decrementa `cantidad` real
    y `cantidad_reservada` a la vez (la reserva ya garantizaba que había
    stock, así que esto no puede dejar `cantidad` negativa) y borra el hold.
    Devuelve la cantidad vendida, o None si el hold ya no existía."""
    hold = db.get(StockHold, hold_id)
    if hold is None:
        return None
    n = hold.quantity
    result = db.execute(
        update(Item)
        .where(Item.id == hold.item_id, Item.quantity >= n, Item.reserved_quantity >= n)
        .values(quantity=Item.quantity - n, reserved_quantity=Item.reserved_quantity - n)
        .execution_options(**_OPTS)
    )
    if result.rowcount != 1:
        db.rollback()
        return None
    db.delete(hold)
    db.commit()
    return n


def confirm_stock_sale_bulk(db: Session, hold_ids: list[uuid.UUID]) -> list[uuid.UUID]:
    """Como `confirm_sale` pero para holds de stock agregado: vende todos,
    todo o nada. Devuelve los hold_id que fallaron (vacío = éxito); si
    alguno falla, deshace lo vendido en este intento devolviendo la
    cantidad y recreando un hold equivalente (con un id nuevo)."""
    vendidos: list[StockHold] = []
    failed: list[uuid.UUID] = []
    for hold_id in hold_ids:
        hold = db.get(StockHold, hold_id)
        if hold is None:
            failed.append(hold_id)
            continue
        snapshot = StockHold(
            item_id=hold.item_id, quantity=hold.quantity, cart_id=hold.cart_id,
            peticion_id=hold.peticion_id, assignacio_id=hold.assignacio_id, order_id=hold.order_id,
        )
        if confirm_stock_sale(db, hold_id) is None:
            failed.append(hold_id)
        else:
            vendidos.append(snapshot)

    if failed:
        for snap in vendidos:
            db.execute(
                update(Item).where(Item.id == snap.item_id)
                .values(
                    quantity=Item.quantity + snap.quantity,
                    reserved_quantity=Item.reserved_quantity + snap.quantity,
                )
                .execution_options(**_OPTS)
            )
            db.add(StockHold(
                item_id=snap.item_id, quantity=snap.quantity, cart_id=snap.cart_id,
                peticion_id=snap.peticion_id, assignacio_id=snap.assignacio_id, order_id=snap.order_id,
            ))
        db.commit()
        return failed
    return []


def reserve_stock_bulk(
    db: Session, requests: list[tuple[uuid.UUID, int]], cart_id: uuid.UUID, ttl_minutes: int,
) -> list[uuid.UUID]:
    """Como `reserve_items` pero para líneas nou con cantidad: reserva todas
    las líneas para `cart_id`, todo o nada. Devuelve los item_id que NO se
    pudieron reservar (vacía = éxito); revierte lo conseguido en este
    intento si alguno falla."""
    reservado: list[uuid.UUID] = []
    failed: list[uuid.UUID] = []
    for item_id, cantidad in requests:
        hold_id = reserve_stock(db, item_id, cantidad, cart_id=cart_id, ttl_minutes=ttl_minutes)
        if hold_id is not None:
            reservado.append(hold_id)
        else:
            failed.append(item_id)
    if failed:
        for hold_id in reservado:
            release_stock_hold(db, hold_id)
        return failed
    return []
