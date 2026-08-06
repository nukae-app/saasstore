"""Cierre de un pedido tras el pago: vende los ejemplares reservados,
cierra los listings de Discogs correspondientes y avisa por email.

Punto compartido por dos caminos que llegan a "pagado":
- La notificación server-to-server de Redsys (pago online autorizado).
- Un admin marcando manualmente como pagado un pedido con `metodo_pago="tienda"`
  (paga al recoger) desde el panel de pedidos.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from ..config import get_settings
from ..models import CondicionItem, EstadoPeticionCliente, Item, Order, OrderItem, OrderStatus, PeticionCliente, StockHold
from .discogs_sync import remove_item_from_discogs, sync_stock_listing
from .emailer import render_email_html, send_email
from .i18n import translate
from .reservations import confirm_sale, confirm_stock_sale_bulk


def finalize_payment(db: Session, order: Order) -> list[uuid.UUID]:
    """Marca `order` como pagado. Devuelve los item_ids que no se pudieron
    vender (vacío = éxito); si no está vacío, el pedido NO se ha modificado.

    Les línies "de reserva" (`item_id is None`, d'una petició de client
    pagada per endavant abans que existeixi l'exemplar físic — veure
    routers/me.py `aceptar_peticion`) no tenen res a vendre encara: es
    deixen tal qual, l'exemplar s'hi assignarà quan arribi (routers/erp.py)."""
    rows = list(
        db.scalars(
            select(OrderItem)
            .where(OrderItem.order_id == order.id)
            .options(selectinload(OrderItem.item).selectinload(Item.release))
        )
    )
    rows_amb_item = [r for r in rows if r.item_id is not None]
    rows_segona = [r for r in rows_amb_item if r.condicion != CondicionItem.nou]
    rows_nou = [r for r in rows_amb_item if r.condicion == CondicionItem.nou]

    # Se comprueba la disponibilidad de las líneas nou ANTES de vender nada:
    # así, si faltan, no se ha mutado todavía ni el stock ni las líneas
    # segona_ma (confirm_sale/confirm_stock_sale_bulk son atómicos cada uno
    # por separado, pero entre los dos grupos no hay una transacción común;
    # comprobar primero minimiza la ventana en la que eso importaría).
    hold_ids: list[uuid.UUID] = []
    if rows_nou:
        # El hold puede estar todavía en cart_id (pago con Redsys) o ya
        # reasignado a order_id (pago 'tienda' marcado a mano, ver
        # checkout.py::confirm_checkout).
        holds = {
            h.item_id: h for h in db.scalars(
                select(StockHold).where(or_(StockHold.cart_id == order.cart_id, StockHold.order_id == order.id))
            )
        }
        faltantes = []
        for r in rows_nou:
            hold = holds.get(r.item_id)
            if hold is None or hold.cantidad != r.cantidad:
                faltantes.append(r.item_id)
            else:
                hold_ids.append(hold.id)
        if faltantes:
            return faltantes

    if rows_segona:
        failed = confirm_sale(db, [r.item_id for r in rows_segona], order.cart_id)
        if failed:
            return failed

    if hold_ids:
        failed_nou = confirm_stock_sale_bulk(db, hold_ids)
        if failed_nou:
            # Ya se vendieron los segona_ma: no hay vuelta atrás limpia para
            # ese grupo (caso extremo, ver comentario arriba). Se reporta el
            # fallo igualmente para que el llamador no marque el pedido como
            # pagado con stock nou pendiente de resolver a mano.
            return [r.item_id for r in rows_nou if r.item_id]
        for r in rows_nou:
            db.refresh(r.item)
            sync_stock_listing(db, r.item)

    order.status = OrderStatus.pagado
    order.cobrat_at = datetime.now(timezone.utc)

    # Si algun d'aquests exemplars satisfeia una PeticionCliente (Via 1: pagat
    # online o a recollir), es tanca aquí — mai caduca un cop pagat de veritat.
    item_ids = [r.item_id for r in rows_amb_item]
    if item_ids:
        for peticion in db.scalars(
            select(PeticionCliente).where(
                PeticionCliente.item_id.in_(item_ids), PeticionCliente.estado == EstadoPeticionCliente.reservada,
            )
        ):
            peticion.estado = EstadoPeticionCliente.recollida
            peticion.order_id = order.id

    db.commit()

    for r in rows_amb_item:
        if r.item.codi_discogs:
            remove_item_from_discogs(r.item.codi_discogs)

    lang = order.idioma
    order_short = str(order.id)[:8]
    comandes_url = f"{get_settings().frontend_url}/{lang}/compte/comandes"
    send_email(
        order.email_contacto,
        translate(db, "email.order_confirmed.subject", lang, order_short=order_short),
        translate(db, "email.order_confirmed.body_text", lang, total=order.total, link=comandes_url),
        html=render_email_html(
            translate(db, "email.order_confirmed.heading", lang),
            translate(db, "email.order_confirmed.body_html", lang, total=order.total),
            cta=(translate(db, "email.order_confirmed.cta", lang), comandes_url),
        ),
    )
    return []
