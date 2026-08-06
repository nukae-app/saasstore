"""Checkout en tres pasos, con pasarela Redsys entre /confirm y el pago real.

1. POST /checkout/start  -> reserva atómica de todos los ejemplares del
   carrito durante N minutos. Si alguno ya no está disponible, devuelve
   409 con la lista de conflictos y no reserva nada.
2. POST /checkout/confirm -> crea el pedido en `pendiente_pago`, copia los
   precios y la dirección (snapshots). Los ejemplares siguen `reservado`
   (todavía no se venden: eso solo pasa cuando se confirma el pago).
   `metodo_pago="tienda"` (paga al recoger, solo con recogida_tienda) deja
   el pedido así hasta que un admin lo marca como pagado desde el panel;
   `metodo_pago="redsys"` sigue con el paso 3.
3. POST /checkout/{order_id}/pay/redsys/start -> genera los campos firmados
   para el formulario de pago (el frontend hace un POST-redirect a Redsys).
4. POST /checkout/pay/redsys/notify -> notificación server-to-server de
   Redsys. Si el cobro se autoriza, aquí es donde el pedido pasa a `pagado`
   y los ejemplares a `vendido` (vía services.orders.finalize_payment, que
   usa el mismo cart_id que hizo la reserva original). Si se deniega, se
   cancela el pedido y el ejemplar vuelve a la venta.
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import (
    Cart, CartItem, CondicionItem, ConfiguracioBotiga, Item, Order, OrderItem, OrderStatus, Payment,
    PaymentStatus, StockHold, User,
)
from ..schemas import CheckoutConfirm, OrderOut
from ..services import redsys
from ..services.metrics import redsys_payment_result_total
from ..services.orders import finalize_payment
from ..services.iva import compute_iva_venda
from ..services.enviament import PaisNoDisponible, compute_coste_enviament, paisos_disponibles, pes_total_g
from ..services.reservations import (
    release_expired, release_items, release_stock_hold, reservation_minutes, reserve_items,
    reserve_stock_bulk,
)
from ..services.security import get_current_user_optional
from .cart import get_or_create_cart

router = APIRouter(prefix="/checkout", tags=["checkout"])


def _cart_items(db: Session, cart: Cart) -> list[CartItem]:
    return list(
        db.scalars(
            select(CartItem)
            .where(CartItem.cart_id == cart.id)
            .options(selectinload(CartItem.item).selectinload(Item.release))
        )
    )


def _check_botiga_no_bloquejada(db: Session, user: User | None) -> None:
    """Si el mode manteniment (`ConfiguracioBotiga.manteniment_actiu`) està
    actiu, només un admin pot completar el checkout — permet fer-hi proves
    mentre la resta de clients veuen el banner "en construcció" (front)."""
    if user is not None and user.rol == "admin":
        return
    config = db.get(ConfiguracioBotiga, 1)
    if config is not None and config.manteniment_actiu:
        raise HTTPException(403, "La botiga està en manteniment. Les compres estan temporalment desactivades.")


@router.post("/start")
def start_checkout(
    cart: Cart = Depends(get_or_create_cart),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    _check_botiga_no_bloquejada(db, user)
    rows = _cart_items(db, cart)
    if not rows:
        raise HTTPException(400, "El carrito está vacío")

    rows_segona = [r for r in rows if r.item.condicion != CondicionItem.nou]
    rows_nou = [r for r in rows if r.item.condicion == CondicionItem.nou]
    minutos = reservation_minutes(db)

    failed_segona = reserve_items(db, [r.item_id for r in rows_segona], cart.id) if rows_segona else []
    failed_nou: list[uuid.UUID] = []
    if not failed_segona and rows_nou:
        failed_nou = reserve_stock_bulk(
            db, [(r.item_id, r.cantidad) for r in rows_nou], cart.id, ttl_minutes=minutos,
        )
        if failed_nou:
            # el lote de nou falló: revertir también lo reservado de segona_ma
            release_items(db, [r.item_id for r in rows_segona])

    failed = set(failed_segona) | set(failed_nou)
    if failed:
        no_disponibles = [
            f"{r.item.release.artista} — {r.item.release.titulo}" for r in rows if r.item_id in failed
        ]
        raise HTTPException(409, {"detail": "Algunos discos ya no están disponibles", "items": no_disponibles})
    total = sum((r.item.precio * r.cantidad for r in rows), Decimal("0"))
    return {"reserved": True, "total": str(total), "minutos_reserva": minutos}


@router.get("/paisos-enviament")
def get_paisos_enviament(db: Session = Depends(get_db)):
    """Països a on avui es pot triar "Enviament" al checkout (els que tenen
    algun tram actiu a `TramEnviament`). Font única de veritat pel selector
    de país del client: afegir un país nou és crear un tram des de l'admin,
    no requereix cap canvi de codi aquí."""
    return {"paisos": paisos_disponibles(db)}


@router.get("/coste-envio")
def get_coste_envio(
    metodo_envio: str,
    pais: str | None = None,
    cart: Cart = Depends(get_or_create_cart),
    db: Session = Depends(get_db),
):
    """Cost d'enviament del carret actual per al mètode indicat, per mostrar-lo
    al resum abans de confirmar (el valor que realment es cobra es recalcula
    igual a `/confirm`, no es rep del client)."""
    rows = _cart_items(db, cart)
    pes_g = pes_total_g([r.item for r in rows for _ in range(r.cantidad)], db)
    try:
        coste_envio = compute_coste_enviament(pes_g, metodo_envio, pais, db)
    except PaisNoDisponible as exc:
        raise HTTPException(422, str(exc))
    return {"coste_envio": str(coste_envio)}


@router.post("/confirm", response_model=OrderOut, status_code=201)
def confirm_checkout(
    payload: CheckoutConfirm,
    cart: Cart = Depends(get_or_create_cart),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """Crea el pedido en `pendiente_pago`. El cobro real (y el paso a
    `pagado`/`vendido`) ocurre en la notificación de Redsys, no aquí."""
    _check_botiga_no_bloquejada(db, user)
    if payload.metodo_envio == "envio" and payload.direccion_envio is None:
        raise HTTPException(422, "Falta la dirección de envío")
    if payload.metodo_pago == "tienda" and payload.metodo_envio != "recogida_tienda":
        raise HTTPException(422, "El pago en tienda solo está disponible con recogida en tienda")

    # Libera reservas caducadas ANTES de leer el carrito: si no, `rows`
    # traería estados de item obsoletos (el UPDATE masivo no sincroniza la
    # sesión, ver services/reservations.py).
    release_expired(db)
    rows = _cart_items(db, cart)
    if not rows:
        raise HTTPException(400, "El carrito está vacío")

    # No se vende nada todavía: solo comprobamos que la reserva de ESTE
    # carrito siga viva (si no, es que caducó o alguien más ya se lo llevó).
    holds_nou = {
        h.item_id: h for h in db.scalars(select(StockHold).where(StockHold.cart_id == cart.id))
    }
    no_disponibles = []
    for r in rows:
        if r.item.condicion == CondicionItem.nou:
            hold = holds_nou.get(r.item_id)
            if hold is None or hold.cantidad != r.cantidad:
                no_disponibles.append(f"{r.item.release.artista} — {r.item.release.titulo}")
        elif r.item.status.value != "reservado" or r.item.reserved_by_cart_id != cart.id:
            no_disponibles.append(f"{r.item.release.artista} — {r.item.release.titulo}")
    if no_disponibles:
        raise HTTPException(409, {"detail": "Algunos discos ya no están disponibles", "items": no_disponibles})

    email = payload.email_contacto.lower()
    # Checkout d'invitat amb el mateix email d'un compte ja existent: vincula
    # la comanda a aquell compte (igual que faria qualsevol ecommerce), perquè
    # l'historial de compres no es perdi només per no haver iniciat sessió.
    if user is None:
        user = db.scalar(select(User).where(func.lower(User.email) == email))

    subtotal = sum((r.item.precio * r.cantidad for r in rows), Decimal("0"))
    pes_g = pes_total_g([r.item for r in rows for _ in range(r.cantidad)], db)
    pais = payload.direccion_envio.pais if payload.direccion_envio else None
    try:
        coste_envio = compute_coste_enviament(pes_g, payload.metodo_envio, pais, db)
    except PaisNoDisponible as exc:
        raise HTTPException(422, str(exc))
    total = subtotal + coste_envio
    order = Order(
        user_id=user.id if user else None,
        email_contacto=email,
        status=OrderStatus.pendiente_pago,
        total=total,
        coste_envio=coste_envio,
        metodo_envio=payload.metodo_envio,
        metodo_pago=payload.metodo_pago,
        direccion_envio=payload.direccion_envio.model_dump() if payload.direccion_envio else None,
        notas=payload.notas,
        cart_id=cart.id,
        # Cuenta ya existente (logueado o vinculado por email) manda su idioma
        # guardado; para un invitado sin cuenta es la única señal disponible.
        idioma=user.idioma if user else payload.idioma,
    )
    db.add(order)
    db.flush()
    for r in rows:
        precio_total_linea = r.item.precio * r.cantidad
        tipus_iva_id, iva_pct, iva_import = compute_iva_venda(r.item, precio_total_linea, db)
        db.add(OrderItem(
            order_id=order.id, item_id=r.item_id, precio=r.item.precio, cantidad=r.cantidad,
            condicion=r.item.condicion,
            tipus_iva_id=tipus_iva_id, iva_pct=iva_pct, iva_import=iva_import,
        ))
        db.delete(r)  # vaciar carrito (el item ya está referenciado por el pedido)

    if payload.metodo_pago == "tienda":
        # La reserva estàndard de carret (20 min, ver services/reservations.py)
        # no dura prou perquè el client vingui a recollir i pagar en persona.
        # S'allarga a 72h, igual que la reserva equivalent d'una
        # PeticionCliente Via 2 (recollida_paga_botiga, veure
        # erp.py._reservar_item_para_peticion). reserved_by_cart_id es manté
        # (no es toca): finalize_payment -> confirm_sale el necessita per
        # vendre l'ítem quan un admin marqui la comanda com a pagada.
        ids_segona = [r.item_id for r in rows if r.item.condicion != CondicionItem.nou]
        if ids_segona:
            db.execute(
                update(Item)
                .where(Item.id.in_(ids_segona))
                .values(reserved_until=datetime.now(timezone.utc) + timedelta(hours=72))
                .execution_options(synchronize_session=False)
            )
        # Nou: el hold pasa de "carrito" a "pedido pendiente de pago en
        # tienda" (StockHold.order_id en vez de cart_id), mismo criterio que
        # arriba pero vía la tabla de retenciones — release_expired lo
        # localiza y cancela el pedido si nadie viene a pagar en 72h.
        for r in rows:
            if r.item.condicion == CondicionItem.nou:
                hold = holds_nou[r.item_id]
                hold.cart_id = None
                hold.order_id = order.id
                hold.reserved_until = datetime.now(timezone.utc) + timedelta(hours=72)

    db.commit()
    db.refresh(order)
    return order


@router.get("/{order_id}")
def get_order_status(order_id: uuid.UUID, db: Session = Depends(get_db)):
    """Estado mínimo de un pedido para las páginas de resultado del pago
    (pago-ok/pago-ko) o la de "paga al recoger". Sin autenticación: es
    checkout de invitado, conocer el UUID del pedido es la única prueba
    que tiene el navegador del cliente en ese momento."""
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(404, "Pedido no encontrado")
    return {
        "id": order.id,
        "status": order.status,
        "total": str(order.total),
        "coste_envio": str(order.coste_envio),
        "metodo_envio": order.metodo_envio,
        "metodo_pago": order.metodo_pago,
    }


@router.post("/{order_id}/pay/redsys/start")
def start_redsys_payment(order_id: uuid.UUID, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(404, "Pedido no encontrado")
    if order.status != OrderStatus.pendiente_pago:
        raise HTTPException(409, f"El pedido no está pendiente de pago (estado: {order.status.value})")

    ds_order = redsys.generate_ds_order()
    payment = Payment(order_id=order.id, ds_order=ds_order, importe=order.total)
    db.add(payment)
    db.commit()

    return redsys.build_payment_form(ds_order=ds_order, importe=order.total, order_id_for_url=str(order.id))


@router.post("/pay/redsys/notify")
async def redsys_notify(request: Request, db: Session = Depends(get_db)):
    """Notificación server-to-server de Redsys tras el intento de cobro.
    Redsys manda esto como application/x-www-form-urlencoded."""
    form = await request.form()
    params_b64 = form.get("Ds_MerchantParameters")
    signature = form.get("Ds_Signature")
    if not params_b64 or not signature:
        raise HTTPException(400, "Notificación incompleta")

    params = redsys.verify_notification(params_b64, signature)
    if params is None:
        raise HTTPException(400, "Firma inválida")

    ds_order = params.get("Ds_Order") or params.get("Ds_Merchant_Order")
    payment = db.scalar(select(Payment).where(Payment.ds_order == ds_order))
    if payment is None:
        redsys_payment_result_total.labels(result="payment_not_found").inc()
        raise HTTPException(404, "Pago no encontrado")
    if payment.estado != PaymentStatus.creado:
        redsys_payment_result_total.labels(result="already_processed").inc()
        return {"status": "ya procesado"}  # idempotencia: Redsys puede reintentar la notificación

    payment.raw_notification = params
    payment.ds_response_code = params.get("Ds_Response")
    payment.ds_authorisation_code = params.get("Ds_AuthorisationCode")

    order = db.get(Order, payment.order_id)

    if redsys.is_authorised(payment.ds_response_code):
        failed = finalize_payment(db, order)
        if failed:
            # La reserva caducó o el ejemplar se vendió por otra vía mientras
            # el cliente pagaba: el cobro se ha autorizado pero no podemos
            # entregar el disco. Requiere reembolso manual (fuera de alcance
            # de este endpoint) y revisión del pedido por un admin.
            payment.estado = PaymentStatus.error
            db.commit()
            redsys_payment_result_total.labels(result="stock_gone").inc()
            return {"status": "error", "detail": "No se pudo reservar el stock tras el pago"}
        payment.estado = PaymentStatus.autorizado
        db.commit()
        redsys_payment_result_total.labels(result="autorizado").inc()
    else:
        rows = list(db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)))
        payment.estado = PaymentStatus.denegado
        order.status = OrderStatus.cancelado
        db.commit()
        redsys_payment_result_total.labels(result="denegado").inc()
        item_ids_segona = [r.item_id for r in rows if r.item_id is not None and r.condicion != CondicionItem.nou]
        if item_ids_segona:
            release_items(db, item_ids_segona)
        # Nou: el pago con Redsys nunca llega a reasignar el hold de
        # cart_id a order_id (eso solo pasa con metodo_pago='tienda'), así
        # que sigue localizable por cart_id.
        item_ids_nou = [r.item_id for r in rows if r.item_id is not None and r.condicion == CondicionItem.nou]
        if item_ids_nou and order.cart_id is not None:
            for hold in db.scalars(
                select(StockHold).where(StockHold.cart_id == order.cart_id, StockHold.item_id.in_(item_ids_nou))
            ):
                release_stock_hold(db, hold.id)

    return {"status": "ok"}
