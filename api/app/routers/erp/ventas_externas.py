import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session, selectinload

from ...database import get_db
from ...models import (
    CanalVenta, CondicionItem, DevolucionVenta, EstadoPeticionCliente, Item, ItemStatus, JournalSourceType,
    MetodoPago, PeticionCliente, StockHold, TipusIva, User, VentaExterna,
)
from ...schemas import VentaExternaIn, VentaExternaLoteIn, VentaExternaOut, VincularUsuariTicketIn
from ...services.comptabilitat_posting import post_venda
from ...services.discogs_sync import get_discogs_token_if_enabled, sync_stock_listing
from ...services.iva import compute_iva_venda
from ...services.reservations import release_expired
from ...services.security import require_admin

router = APIRouter(prefix="/admin", tags=["erp"], dependencies=[Depends(require_admin)])

_NO_SYNC = {"synchronize_session": False}


def _iva_articulo_manual(db: Session, tipus_iva_id: int, sale_price: Decimal) -> tuple[int, Decimal, Decimal]:
    """Un article manual no té `Item` del qual deduir el règim d'IVA (nou vs
    REBU): el tria l'admin a mà entre els tipus configurats. REBU es basa en
    el marge sobre un cost d'adquisició que un article manual no té, així
    que no és una opció vàlida aquí."""
    tipus = db.get(TipusIva, tipus_iva_id)
    if tipus is None or not tipus.active:
        raise HTTPException(404, "Tipus d'IVA no trobat o inactiu")
    if tipus.is_rebu:
        raise HTTPException(422, "Aquest tipus d'IVA és de règim REBU (marge) i no és aplicable a un article manual")
    if sale_price <= 0:
        return tipus.id, tipus.percentage, Decimal("0.00")
    pct = tipus.percentage
    iva_import = (sale_price * pct / (Decimal("100") + pct)).quantize(Decimal("0.01"))
    return tipus.id, pct, iva_import


def _crear_linia_venta(
    db: Session,
    *,
    ticket_id: uuid.UUID,
    item_id: uuid.UUID | None,
    description: str | None,
    tipus_iva_id: int | None,
    channel: str,
    payment_method: str,
    sale_price: Decimal,
    date: datetime,
    client_name: str | None,
    user_id: uuid.UUID | None,
    discogs_sale_id: int | None = None,
    notes: str | None = None,
    quantity: int = 1,
) -> tuple[VentaExterna, Item | None]:
    """Crea una VentaExterna (sin commitear: quien llama decide cuándo, para
    poder agrupar varias líneas en una sola transacción — venta de un item
    suelto, o de un lote). `ticket_id` lo decide siempre el caller: el mismo
    valor para todas las líneas de un lote, uno nuevo para una venta suelta.
    Dos casos:
    - item_id presente: venda de catàleg, reserva atòmica de l'ejemplar.
      Per a nou, `quantity` és quantes unitats es venen d'aquesta línia
      (descompta `Item.quantity` en comptes de canviar `status`, que a nou
      no representa res); per a segona_ma sempre és 1.
    - item_id ausent: article manual (llibre, samarreta...), sense estoc
      que reservar; l'IVA es tria a mà (veure `_iva_articulo_manual`)."""
    if item_id is None:
        tipus_iva_id_calc, iva_pct, iva_import = _iva_articulo_manual(db, tipus_iva_id, sale_price)
        venta = VentaExterna(
            ticket_id=ticket_id,
            item_id=None,
            description=description,
            channel=CanalVenta(channel),
            payment_method=MetodoPago(payment_method),
            sale_price=sale_price,
            date=date,
            client_name=client_name,
            user_id=user_id,
            discogs_sale_id=discogs_sale_id,
            notes=notes,
            tipus_iva_id=tipus_iva_id_calc,
            vat_pct=iva_pct,
            vat_amount=iva_import,
        )
        db.add(venta)
        db.flush()
        _post_venda_externa(db, venta, cost=None)
        return venta, None

    # Una PeticionCliente en Via 2 (recollida_paga_botiga) reté l'ítem amb
    # status='reservado' (segona_ma) o un StockHold (nou): cal saber-ho
    # ABANS de vendre, que el buidarà si té èxit.
    peticion_vinculada = db.scalar(
        select(PeticionCliente).where(
            PeticionCliente.item_id == item_id, PeticionCliente.status == EstadoPeticionCliente.reservada,
        )
    )
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "Ejemplar no encontrado")

    if item.condition == CondicionItem.nou:
        hold_peticion = (
            db.scalar(select(StockHold).where(StockHold.item_id == item_id, StockHold.peticion_id == peticion_vinculada.id))
            if peticion_vinculada else None
        )
        if hold_peticion is not None:
            if hold_peticion.quantity != quantity:
                raise HTTPException(409, "La reserva d'aquesta petició no coincideix amb la quantitat a vendre")
            result = db.execute(
                update(Item)
                .where(Item.id == item_id, Item.quantity >= quantity, Item.reserved_quantity >= quantity)
                .values(quantity=Item.quantity - quantity, reserved_quantity=Item.reserved_quantity - quantity)
                .execution_options(**_NO_SYNC)
            )
            if result.rowcount == 1:
                db.delete(hold_peticion)
        else:
            result = db.execute(
                update(Item)
                .where(Item.id == item_id, Item.quantity - Item.reserved_quantity >= quantity)
                .values(quantity=Item.quantity - quantity)
                .execution_options(**_NO_SYNC)
            )
        if result.rowcount == 0:
            raise HTTPException(409, f"No hi ha prou stock per vendre {quantity} unitats")
        db.refresh(item)
        sync_stock_listing(db, item, get_discogs_token_if_enabled(db, item.tenant_id))
    else:
        # Reserva atómica: disponible, o retingut per aquesta petició concreta.
        result = db.execute(
            update(Item)
            .where(
                Item.id == item_id,
                or_(
                    Item.status == ItemStatus.disponible,
                    and_(Item.status == ItemStatus.reservado, Item.reserved_for_peticion_id.isnot(None)),
                ),
            )
            .values(
                status=ItemStatus.retirado, reserved_until=None,
                reserved_by_cart_id=None, reserved_for_peticion_id=None,
            )
            .execution_options(**_NO_SYNC)
        )
        if result.rowcount == 0:
            raise HTTPException(409, f"Ejemplar no disponible (estado actual: {item.status})")

    if peticion_vinculada:
        peticion_vinculada.status = EstadoPeticionCliente.recollida

    # sale_price es el TOTAL cobrado por la línea (todas las unidades),
    # no por unidad — igual criterio que ya asumían los informes de
    # comptabilitat.py que suman VentaExterna.sale_price directamente.
    tipus_iva_id_calc, iva_pct, iva_import = compute_iva_venda(item, sale_price, db)
    venta = VentaExterna(
        ticket_id=ticket_id,
        item_id=item_id,
        condition=item.condition,
        quantity=quantity,
        channel=CanalVenta(channel),
        payment_method=MetodoPago(payment_method),
        sale_price=sale_price,
        date=date,
        client_name=client_name,
        user_id=user_id,
        discogs_sale_id=discogs_sale_id,
        notes=notes,
        tipus_iva_id=tipus_iva_id_calc,
        vat_pct=iva_pct,
        vat_amount=iva_import,
    )
    db.add(venta)
    db.flush()
    cost = (item.acquisition_cost * quantity) if item.acquisition_cost is not None else None
    _post_venda_externa(db, venta, cost=cost)
    return venta, item


def _post_venda_externa(db: Session, venta: VentaExterna, *, cost: Decimal | None) -> None:
    # vat_amount pot ser None (REBU sense acquisition_cost resolt, ver
    # services/iva.py) — buit de dades ja existent, es tracta com 0 en
    # comptes de bloquejar la venda de mostrador.
    vat_amount = venta.vat_amount or Decimal("0")
    post_venda(
        db, entry_date=venta.date.date(), source_type=JournalSourceType.venda_externa, source_id=venta.id,
        description=f"Venda {venta.channel.value} #{str(venta.ticket_id)[:8]}",
        total_collected=venta.sale_price, revenue_base=venta.sale_price - vat_amount,
        vat_amount=vat_amount, cost=cost,
    )


def _venta_externa_out(venta: VentaExterna, item: Item | None) -> VentaExternaOut:
    return VentaExternaOut(
        id=venta.id,
        ticket_id=venta.ticket_id,
        item_id=venta.item_id,
        description=venta.description,
        channel=venta.channel,
        payment_method=venta.payment_method,
        sale_price=venta.sale_price,
        coste_adquisicion=item.acquisition_cost if item else None,
        date=venta.date,
        client_name=venta.client_name,
        user_id=venta.user_id,
        user_nom=venta.client.name if venta.client else None,
        discogs_sale_id=venta.discogs_sale_id,
        notes=venta.notes,
        created_at=venta.created_at,
        tipus_iva_id=venta.tipus_iva_id,
        vat_pct=venta.vat_pct,
        vat_amount=venta.vat_amount,
        quantity=venta.quantity,
        condition=venta.condition.value if venta.condition else None,
        artista=item.release.artista if item else None,
        titulo=item.release.title if item else None,
    )


@router.post("/ventas-externas", status_code=201, response_model=VentaExternaOut)
def create_venta_externa(payload: VentaExternaIn, db: Session = Depends(get_db)):
    release_expired(db)
    venta, item = _crear_linia_venta(
        db,
        ticket_id=uuid.uuid4(),
        item_id=payload.item_id,
        description=payload.description,
        tipus_iva_id=payload.tipus_iva_id,
        channel=payload.channel,
        payment_method=payload.payment_method,
        sale_price=payload.sale_price,
        date=payload.date,
        client_name=payload.client_name,
        user_id=payload.user_id,
        discogs_sale_id=payload.discogs_sale_id,
        notes=payload.notes,
        quantity=payload.quantity,
    )
    db.commit()
    db.refresh(venta)
    return _venta_externa_out(venta, item)


@router.post("/ventas-externas/lote", status_code=201, response_model=list[VentaExternaOut])
def create_venta_externa_lote(payload: VentaExternaLoteIn, db: Session = Depends(get_db)):
    """Vende varios ejemplares (discos distintos, o varias copias del mismo
    álbum, o articles manuals) en una sola operación de TPV: si alguna línea
    falla (ejemplar ya no disponible, tipo de IVA inválido...), no se
    commitea nada del lote — o se cobran todos, o ninguno."""
    release_expired(db)
    ticket_id = uuid.uuid4()
    pendientes: list[tuple[VentaExterna, Item | None]] = []
    for linea in payload.lineas:
        venta, item = _crear_linia_venta(
            db,
            ticket_id=ticket_id,
            item_id=linea.item_id,
            description=linea.description,
            tipus_iva_id=linea.tipus_iva_id,
            channel=payload.channel,
            payment_method=payload.payment_method,
            sale_price=linea.sale_price,
            date=payload.date,
            client_name=payload.client_name,
            user_id=payload.user_id,
            notes=payload.notes,
            quantity=linea.quantity,
        )
        pendientes.append((venta, item))

    db.commit()
    for venta, _ in pendientes:
        db.refresh(venta)
    return [_venta_externa_out(venta, item) for venta, item in pendientes]


@router.patch("/ventas-externas/tickets/{ticket_id}/usuari", response_model=list[VentaExternaOut])
def vincular_usuari_ticket(ticket_id: uuid.UUID, payload: VincularUsuariTicketIn, db: Session = Depends(get_db)):
    """Vincula (o, amb user_id=None, desvincula) un usuari registrat a totes
    les línies d'un tiquet ja cobrat. No canvia cap altra dada de la venda
    (preu, IVA, estoc...) — només qui hi queda associat."""
    ventas = db.scalars(select(VentaExterna).where(VentaExterna.ticket_id == ticket_id)).all()
    if not ventas:
        raise HTTPException(404, "Tiquet no trobat")
    if payload.user_id is not None and db.get(User, payload.user_id) is None:
        raise HTTPException(404, "Usuari no trobat")

    for venta in ventas:
        venta.user_id = payload.user_id
    db.commit()

    result = []
    for venta in ventas:
        db.refresh(venta)
        item = db.get(Item, venta.item_id) if venta.item_id else None
        result.append(_venta_externa_out(venta, item))
    return result


@router.get("/ventas-externas", response_model=list[VentaExternaOut])
def list_ventas_externas(
    canal: str | None = None,
    metodo_pago: str | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
):
    stmt = (
        select(VentaExterna)
        .options(
            selectinload(VentaExterna.item).selectinload(Item.release),
            selectinload(VentaExterna.client),
        )
        .order_by(VentaExterna.date.desc())
    )
    if canal:
        stmt = stmt.where(VentaExterna.channel == canal)
    if metodo_pago:
        stmt = stmt.where(VentaExterna.payment_method == metodo_pago)
    if desde:
        stmt = stmt.where(VentaExterna.date >= desde)
    if hasta:
        stmt = stmt.where(VentaExterna.date <= hasta)
    ventas = db.scalars(stmt).all()

    # Filtro de texto sobre artista/título/descripción (client-friendly: hacerlo en Python)
    if q:
        ql = q.lower()
        ventas = [
            v for v in ventas
            if (v.item and v.item.release and (
                ql in v.item.release.artista.lower() or ql in v.item.release.title.lower()
            ))
            or (v.description and ql in v.description.lower())
            or (v.client_name and ql in v.client_name.lower())
        ]

    returned = set(db.scalars(
        select(DevolucionVenta.venta_externa_id)
        .where(DevolucionVenta.venta_externa_id.in_([v.id for v in ventas]))
    ).all())
    return [
        VentaExternaOut(
            id=v.id,
            ticket_id=v.ticket_id,
            item_id=v.item_id,
            description=v.description,
            channel=v.channel,
            payment_method=v.payment_method,
            sale_price=v.sale_price,
            coste_adquisicion=v.item.acquisition_cost if v.item else None,
            date=v.date,
            client_name=v.client_name,
            user_id=v.user_id,
            user_nom=v.client.name if v.client else None,
            discogs_sale_id=v.discogs_sale_id,
            notes=v.notes,
            created_at=v.created_at,
            tipus_iva_id=v.tipus_iva_id,
            vat_pct=v.vat_pct,
            vat_amount=v.vat_amount,
            artista=v.item.release.artista if v.item and v.item.release else None,
            titulo=v.item.release.title if v.item and v.item.release else None,
            devuelta=v.id in returned,
        )
        for v in ventas
    ]
