import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session, selectinload

from ...database import get_db
from ...models import (
    CajaMovimiento, CajaSession, CondicionItem, DevolucionVenta, Item, Order, OrderItem,
    OrderOrigen, OrderStatus, StockHold, TipoMovimiento, User,
)
from ...schemas import (
    OrderMarcarPagadoTiendaIn, OrderPendentTiendaItemOut, OrderPendentTiendaOut, OrderStatusUpdate,
)
from ...services.discogs_sync import push_shipped_status, sync_stock_listing
from ...services.emailer import render_email_html, send_email
from ...services.i18n import translate
from ...services.iva import compute_iva_venda
from ...services.orders import finalize_payment
from ...services.pricing import release_coupon_redemption
from ...services.reservations import release_expired, release_items, release_stock_hold
from ...services.security import require_admin
from ...tenancy import tenant_frontend_url
from ...tenant_secrets import get_tenant_secrets

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/orders")
def list_orders(
    db: Session = Depends(get_db),
    status: OrderStatus | None = None,
    metodo_envio: str | None = None,
    metodo_pago: str | None = None,
    origen: OrderOrigen | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    q: str | None = None,
):
    stmt = select(Order).order_by(Order.created_at.desc())
    if status:
        stmt = stmt.where(Order.status == status)
    if metodo_envio:
        stmt = stmt.where(Order.shipping_method == metodo_envio)
    if metodo_pago:
        stmt = stmt.where(Order.payment_method == metodo_pago)
    if origen:
        stmt = stmt.where(Order.origin == origen)
    if desde:
        stmt = stmt.where(Order.created_at >= desde)
    if hasta:
        stmt = stmt.where(Order.created_at <= hasta)
    orders = list(db.scalars(
        stmt.options(
            selectinload(Order.items).selectinload(OrderItem.item).selectinload(Item.release),
            selectinload(Order.items).selectinload(OrderItem.release),
        )
    ))

    # Filtre de text lliure (client-friendly: fer-ho en Python, mateix patró
    # que list_ventas_externas): email, id de comanda a Discogs, o artista/
    # títol de qualsevol dels discos de la comanda.
    if q:
        ql = q.lower()
        def _matches(o):
            if ql in o.contact_email.lower():
                return True
            if o.discogs_order_id and ql in o.discogs_order_id.lower():
                return True
            for oi in o.items:
                release = oi.item.release if oi.item else oi.release
                if release and (ql in release.artista.lower() or ql in release.title.lower()):
                    return True
            return False
        orders = [o for o in orders if _matches(o)]

    # Ordres amb alguna línia "de reserva" (petició pagada per endavant,
    # encara sense exemplar físic assignat — veure OrderItem.item_id).
    pendents_arribada = set(db.scalars(
        select(OrderItem.order_id)
        .where(OrderItem.order_id.in_([o.id for o in orders]), OrderItem.item_id.is_(None))
        .distinct()
    ))

    return [
        {
            "id": o.id,
            "email": o.contact_email,
            "status": o.status,
            "total": str(o.total),
            "coste_envio": str(o.shipping_cost),
            "metodo_envio": o.shipping_method,
            "metodo_pago": o.payment_method,
            "numero_seguiment": o.tracking_number,
            "created_at": o.created_at,
            "origen": o.origin,
            "discogs_order_id": o.discogs_order_id,
            "pendent_arribada": o.id in pendents_arribada,
            "avisada_recollida_at": o.pickup_notified_at,
        }
        for o in orders
    ]


@router.get("/orders/pendientes-tienda", response_model=list[OrderPendentTiendaOut])
def list_orders_pendientes_tienda(db: Session = Depends(get_db)):
    """Comandes web amb 'paga al recollir' (metodo_pago='tienda') encara
    pendents de pagar: equivalent a /peticiones/reserves-recollida però per
    a Order en comptes de PeticionCliente. El TPV les mostra a la pestanya
    'Reserves web' perquè el mostrador les trobi sense haver de saber-ne
    l'id de memòria; cobrar-la (i vendre l'ítem) es fa amb
    POST /admin/orders/{id}/marcar-pagado-tienda, no amb
    /admin/ventas-externas (l'ítem ja té el seu OrderItem amb el preu/IVA
    de compra web)."""
    release_expired(db)
    orders = db.scalars(
        select(Order)
        .where(Order.status == OrderStatus.pendiente_pago, Order.payment_method == "tienda")
        .options(
            selectinload(Order.items).selectinload(OrderItem.item).selectinload(Item.release),
        )
        .order_by(Order.created_at)
    ).all()
    result = []
    for o in orders:
        rows_amb_item = [oi for oi in o.items if oi.item is not None]
        if not rows_amb_item:
            continue
        reserved_untils = [oi.item.reserved_until for oi in rows_amb_item if oi.item.reserved_until]
        user = db.get(User, o.user_id) if o.user_id else None
        result.append(OrderPendentTiendaOut(
            order_id=o.id, email=o.contact_email, total=o.total, created_at=o.created_at,
            reserved_until=min(reserved_untils) if reserved_untils else None,
            user_id=user.id if user else None, user_nombre=user.name if user else None,
            items=[
                OrderPendentTiendaItemOut(
                    item_id=oi.item.id, artista=oi.item.release.artista, titulo=oi.item.release.title,
                    imagen_url=oi.item.release.image_url, estado_disco=oi.item.estado_disco, precio=oi.item.price,
                )
                for oi in rows_amb_item
            ],
        ))
    return result


@router.post("/orders/{order_id}/marcar-pagado-tienda")
def marcar_pagado_tienda(order_id: uuid.UUID, payload: OrderMarcarPagadoTiendaIn, db: Session = Depends(get_db)):
    """Cobra al mostrador una comanda web 'paga en recollir': ven l'estoc
    (finalize_payment, igual que faria un pagament Redsys) i, si es paga en
    efectiu, apunta un CajaMovimiento 'entrada' a la sessió de caixa oberta
    perquè el tancament del dia hi quadri. NO crea una VentaExterna (l'Order
    ja és el registre de venda, amb el seu propi OrderItem i IVA calculat al
    checkout); total_ventas_efectivo a cerrar_caja només compta VentaExterna,
    per això cal aquest apunt manual equivalent.

    `payload.price`, si es dona, sobreescriu el preu (i recalcula l'IVA
    snapshot) del disc abans de vendre'l — mateix descompte manual que ja
    permet el diàleg de vendre una reserva de PeticionCliente al TPV."""
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(404, "Comanda no trobada")
    if order.status != OrderStatus.pendiente_pago or order.payment_method != "tienda":
        raise HTTPException(409, "Aquesta comanda no està pendent de pagar a botiga")

    if payload.price is not None:
        rows_amb_item = [oi for oi in order.items if oi.item_id is not None]
        if len(rows_amb_item) != 1:
            raise HTTPException(422, "Només es pot canviar el preu en comandes d'un sol disc")
        order_item = rows_amb_item[0]
        item = db.get(Item, order_item.item_id)
        precio_total = payload.price * order_item.quantity
        tipus_iva_id, iva_pct, iva_import = compute_iva_venda(item, precio_total, db)
        order_item.price = payload.price
        order_item.tipus_iva_id = tipus_iva_id
        order_item.vat_pct = iva_pct
        order_item.vat_amount = iva_import
        order.total = precio_total  # coste_envio sempre 0 amb recogida_tienda

    failed = finalize_payment(db, order)
    if failed:
        raise HTTPException(409, "No es pot cobrar: algun exemplar ja no està disponible")

    if payload.payment_method == "efectivo":
        sesion_activa = db.scalar(
            select(CajaSession).where(CajaSession.closed_at.is_(None))
            .order_by(CajaSession.opened_at.desc())
        )
        if sesion_activa:
            db.add(CajaMovimiento(
                session_id=sesion_activa.id,
                type=TipoMovimiento.entrada,
                concept=f"Comanda web #{str(order.id)[:8]} — recollida i pagament a botiga",
                amount=order.total,
                date=datetime.now(timezone.utc),
            ))
            db.commit()

    return {"status": order.status}


@router.get("/orders/{order_id}")
def get_order_detail(order_id: uuid.UUID, db: Session = Depends(get_db)):
    order = db.scalar(
        select(Order)
        .options(
            selectinload(Order.items).selectinload(OrderItem.item).selectinload(Item.release),
            selectinload(Order.items).selectinload(OrderItem.release),
            selectinload(Order.payments),
        )
        .where(Order.id == order_id)
    )
    if order is None:
        raise HTTPException(404, "Pedido no encontrado")

    returned_ids = set(db.scalars(
        select(DevolucionVenta.order_item_id)
        .where(DevolucionVenta.order_item_id.in_([oi.id for oi in order.items]))
    ).all())

    return {
        "id": order.id,
        "email": order.contact_email,
        "status": order.status,
        "total": str(order.total),
        "coste_envio": str(order.shipping_cost),
        "metodo_envio": order.shipping_method,
        "metodo_pago": order.payment_method,
        "direccion_envio": order.shipping_address,
        "notas": order.notes,
        "numero_seguiment": order.tracking_number,
        "transportista": order.carrier,
        "created_at": order.created_at,
        "origen": order.origin,
        "discogs_order_id": order.discogs_order_id,
        "discogs_buyer": order.discogs_buyer,
        "avisada_recollida_at": order.pickup_notified_at,
        "payments": [
            {
                "id": p.id,
                "proveedor": p.provider,
                "ds_order": p.ds_order,
                "estado": p.status,
                "importe": str(p.amount),
                "ds_response_code": p.ds_response_code,
                "ds_authorisation_code": p.ds_authorisation_code,
                "created_at": p.created_at,
            }
            for p in sorted(order.payments, key=lambda p: p.created_at, reverse=True)
        ],
        "items": [
            {
                "order_item_id": oi.id,
                "item_id": oi.item_id,
                "artista": oi.item.release.artista if oi.item else (oi.release.artista if oi.release else None),
                "titulo": oi.item.release.title if oi.item else (oi.release.title if oi.release else None),
                "precio": str(oi.price),
                "condicion": oi.item.condition if oi.item else None,
                "estado_disco": oi.item.estado_disco if oi.item else None,
                "item_status": oi.item.status if oi.item else None,
                "pendent_arribada": oi.item_id is None,
                "devuelto": oi.id in returned_ids,
            }
            for oi in order.items
        ],
    }


# Un cop pagat, l'estoc ja està venut (no torna a canviar de mans en cap
# d'aquests tres): es poden moure lliurement entre ells en qualsevol
# direcció, per corregir errades ("s'ha marcat entregat per accident",
# "el lliurem en mà, sense pas per enviat"...) sense arriscar l'estoc.
_ESTATS_LOGISTICS = {OrderStatus.pagado, OrderStatus.enviado, OrderStatus.entregado}
# Cancel·lar allibera l'estoc: no té sentit un cop ja entregat (caldria una
# devolució, no una cancel·lació) ni reversible cap enrere (l'exemplar
# pot haver-se venut a algú altre mentre estava alliberat).
_ESTATS_CANCELABLES = {OrderStatus.pendiente_pago, OrderStatus.pagado, OrderStatus.enviado}


@router.patch("/orders/{order_id}/status")
def update_order_status(order_id: uuid.UUID, payload: OrderStatusUpdate, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(404, "Pedido no encontrado")

    if payload.shipping_method is not None and payload.shipping_method != order.shipping_method:
        if order.status == OrderStatus.cancelado:
            raise HTTPException(409, "No es pot canviar el mètode d'una comanda cancel·lada")
        if payload.shipping_method == "envio":
            if payload.shipping_address is not None:
                order.shipping_address = payload.shipping_address.model_dump()
            elif order.shipping_address is None:
                raise HTTPException(422, "Cal indicar una adreça d'enviament")
        order.shipping_method = payload.shipping_method

    if payload.tracking_number is not None:
        order.tracking_number = payload.tracking_number or None
    if payload.carrier is not None:
        order.carrier = payload.carrier or None

    if payload.status is not None:
        try:
            status = OrderStatus(payload.status)
        except ValueError:
            raise HTTPException(422, "Estat invàlid")

        if status == OrderStatus.pagado and order.status == OrderStatus.pendiente_pago:
            # Marcar como pagado a mano (p. ej. "paga al recoger" en tienda):
            # esto es lo que realmente vende los ejemplares, no un simple cambio
            # de campo (ver services/orders.finalize_payment).
            failed = finalize_payment(db, order)
            if failed:
                raise HTTPException(409, "No se puede marcar como pagado: algún ejemplar ya no está disponible")
        elif status == OrderStatus.cancelado:
            if order.status not in _ESTATS_CANCELABLES:
                raise HTTPException(409, f"No es pot cancel·lar una comanda en estat {order.status.value}")
            estaba_pagado = order.status in (OrderStatus.pagado, OrderStatus.enviado)
            order.status = status
            db.commit()
            # el ejemplar vuelve a la venta (les línies "de reserva" d'una
            # petició pagada per endavant encara no tenen item_id: no hi ha
            # res a alliberar, l'exemplar encara no existeix)
            rows_amb_item = [oi for oi in order.items if oi.item_id is not None]
            item_ids_segona = [oi.item_id for oi in rows_amb_item if oi.condition != CondicionItem.nou]
            if item_ids_segona:
                release_items(db, item_ids_segona)
            rows_nou = [oi for oi in rows_amb_item if oi.condition == CondicionItem.nou]
            if rows_nou and estaba_pagado:
                # Ya se había vendido (cantidad descontada, hold consumido):
                # cancelar repone el stock directamente.
                for oi in rows_nou:
                    db.execute(
                        update(Item).where(Item.id == oi.item_id)
                        .values(quantity=Item.quantity + oi.quantity)
                        .execution_options(synchronize_session=False)
                    )
                db.commit()
                for oi in rows_nou:
                    item = db.get(Item, oi.item_id)
                    if item is not None:
                        sync_stock_listing(db, item, get_tenant_secrets(item.tenant_id).discogs_token)
                db.commit()
            elif rows_nou:
                # Pendiente de pago todavía: el hold puede estar en cart_id
                # (redsys) o ya reasignado a order_id (tienda, ver
                # checkout.py::confirm_checkout).
                for hold in db.scalars(
                    select(StockHold).where(or_(StockHold.order_id == order.id, StockHold.cart_id == order.cart_id))
                ):
                    release_stock_hold(db, hold.id)
            release_coupon_redemption(db, order.id)
        elif order.status in _ESTATS_LOGISTICS and status in _ESTATS_LOGISTICS:
            order.status = status
            db.commit()
        elif (
            order.origin == OrderOrigen.discogs
            and order.status == OrderStatus.pendiente_pago
            and status in _ESTATS_LOGISTICS
        ):
            # Discogs gestiona el cobrament fora del nostre sistema: l'ítem ja
            # es marca 'vendido' en sincronitzar la comanda (veure
            # discogs_sync.sync_discogs_orders), encara que el nostre estat
            # intern digui 'pendiente_pago' fins que Discogs ens informi que
            # ha cobrat de veritat.
            order.status = status
            db.commit()
        else:
            raise HTTPException(409, f"No es pot canviar de {order.status.value} a {status.value}")

        if status == OrderStatus.enviado and order.discogs_order_id:
            # best-effort: si falla, l'enviament local ja ha quedat registrat igualment
            push_shipped_status(
                get_tenant_secrets(order.tenant_id).discogs_token,
                order.discogs_order_id, order.tracking_number, order.carrier,
            )
    else:
        db.commit()

    return {
        "status": order.status, "metodo_envio": order.shipping_method,
        "numero_seguiment": order.tracking_number, "transportista": order.carrier,
    }


@router.post("/orders/{order_id}/avisar-recollida")
def avisar_recollida_order(order_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    """Avisa el client per email que la comanda ja es pot recollir a la
    botiga. Un cop avisada, la comanda apareix a la pestanya "Pendent de
    recollir" (abans només hi estava perquè estava pagada, encara que ningú
    l'hagués preparat de veritat)."""
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(404, "Pedido no encontrado")
    if order.shipping_method != "recogida_tienda":
        raise HTTPException(422, "Aquesta comanda no és de recollida a botiga")
    if order.status != OrderStatus.pagado:
        raise HTTPException(409, "La comanda encara no està pagada")
    pendent = db.scalar(
        select(OrderItem.id).where(OrderItem.order_id == order.id, OrderItem.item_id.is_(None))
    )
    if pendent is not None:
        raise HTTPException(409, "Encara hi ha exemplars pendents d'arribar")

    order.pickup_notified_at = datetime.now(timezone.utc)
    db.commit()

    lang = order.language
    order_short = str(order.id)[:8]
    comanda_url = f"{tenant_frontend_url(request.state.tenant)}/{lang}/compte/comandes/{order.id}"
    send_email(
        order.contact_email,
        translate(db, "email.order_ready_pickup.subject", lang, nom=request.state.tenant.nombre),
        translate(db, "email.order_ready_pickup.body_text", lang, order_short=order_short, link=comanda_url),
        request.state.tenant,
        db,
        html=render_email_html(
            translate(db, "email.order_ready_pickup.heading", lang),
            translate(db, "email.order_ready_pickup.body_html", lang, order_short=order_short),
            request.state.tenant, db,
            cta=(translate(db, "email.order_ready_pickup.cta", lang), comanda_url),
        ),
    )

    return {"avisada_recollida_at": order.pickup_notified_at}
