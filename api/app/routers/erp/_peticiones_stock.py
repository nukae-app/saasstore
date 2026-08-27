"""Helpers de peticions de client compartits entre comandas.py (recepció),
solicitudes_compra.py (resoldre des d'estoc) i peticiones.py (vincular a mà) —
viuen aquí, i no en cap dels tres, per evitar un import circular entre ells."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from ...models import (
    CondicionItem, EstadoPeticionCliente, EstadoSolicitud, Item, ItemStatus, Order, OrderItem,
    OrderStatus, PeticionCliente, SolicitudCompra, SolicitudCompraLinea, StockHold, Tenant,
)
from ...schemas import PeticionClienteAdminOut
from ...services.discogs_sync import get_discogs_token_if_enabled, remove_item_from_discogs
from ...services.emailer import render_email_html, send_email
from ...services.i18n import frontend_url, translate
from ...services.iva import compute_iva_venda
from ...services.security import create_magic_link_token


def _peticion_admin_out(p: PeticionCliente) -> PeticionClienteAdminOut:
    artista = p.release.artista if p.release else p.free_artist
    titulo = p.release.title if p.release else p.free_title
    return PeticionClienteAdminOut(
        id=p.id, user_id=p.user_id, user_nombre=p.user.name, user_email=p.user.email,
        channel=p.channel, release_id=p.release_id, artista=artista, titulo=titulo, status=p.status,
        estimated_price=p.estimated_price, chosen_delivery_method=p.chosen_delivery_method,
        client_notes=p.client_notes, admin_notes=p.admin_notes,
        solicitud_compra_linea_id=p.solicitud_compra_linea_id, order_id=p.order_id,
        pagada=p.order is not None and p.order.status == OrderStatus.pagado,
        created_at=p.created_at,
    )


def _get_peticion_or_404(db: Session, peticion_id: uuid.UUID) -> PeticionCliente:
    p = db.scalar(
        select(PeticionCliente)
        .where(PeticionCliente.id == peticion_id)
        .options(
            selectinload(PeticionCliente.release), selectinload(PeticionCliente.user),
            selectinload(PeticionCliente.order),
        )
    )
    if p is None:
        raise HTTPException(404, "Petició no trobada")
    return p


def _link_un_clic_a_peticions(db: Session, email: str, lang: str, tenant: Tenant) -> str:
    """Magic link (14 dies de caducitat) que porta directament a "Les meves
    peticions" ja loguejat — perquè el client pugui acceptar el preu amb un
    sol clic des de l'email, sense haver de fer login a part."""
    raw = create_magic_link_token(db, email, timedelta(days=14))
    return f"{frontend_url('/auth/magic', lang, tenant)}?token={raw}&next=/compte/peticions"


def _completar_order_pagada(db: Session, peticion: PeticionCliente, item: Item) -> bool:
    """Envio / recollida_paga_ara: el client ja va pagar en acceptar (veure
    me.py, aceptar_peticion), amb una Order que té una línia 'de reserva'
    (item_id=None). Si la trobem, hi assignem l'exemplar real ara (calculant
    l'IVA, que abans no es podia saber) i la petició queda 'recollida'
    directament — no cal cap pas més del client.

    Retorna False si no hi ha cap Order pagada esperant (petició anterior a
    aquesta funcionalitat, o el pagament encara no s'ha completat): en
    aquest cas cal caure al camí antic (reservar i esperar "Comprar ara")."""
    if peticion.order_id is None:
        return False
    order = db.get(Order, peticion.order_id)
    if order is None or order.status != OrderStatus.pagado:
        return False
    linia = db.scalar(
        select(OrderItem).where(OrderItem.order_id == order.id, OrderItem.item_id.is_(None))
    )
    if linia is None:
        return False

    if item.condition == CondicionItem.nou:
        result = db.execute(
            update(Item)
            .where(Item.id == item.id, Item.quantity - Item.reserved_quantity >= 1)
            .values(quantity=Item.quantity - 1)
            .execution_options(synchronize_session=False)
        )
    else:
        result = db.execute(
            update(Item)
            .where(Item.id == item.id, Item.status == ItemStatus.disponible)
            .values(status=ItemStatus.vendido, reserved_until=None)
            .execution_options(synchronize_session=False)
        )
    if result.rowcount == 0:
        raise HTTPException(409, "Aquest exemplar ja no està disponible")

    tipus_iva_id, iva_pct, iva_import = compute_iva_venda(item, linia.price, db)
    linia.item_id = item.id
    linia.release_id = None
    linia.condition = item.condition
    linia.quantity = 1
    linia.tipus_iva_id = tipus_iva_id
    linia.vat_pct = iva_pct
    linia.vat_amount = iva_import

    peticion.item_id = item.id
    peticion.status = EstadoPeticionCliente.recollida

    # El listing virtual de nou es retira sol quan `cantidad` arriba a 0
    # (ver services/discogs_sync.sync_stock_listing); aquí només cal fer-ho
    # explícit per a segona_ma, que és 1 còpia = 1 listing sempre.
    if item.condition != CondicionItem.nou and item.codi_discogs:
        remove_item_from_discogs(get_discogs_token_if_enabled(db, item.tenant_id), item.codi_discogs)

    return True


def _reservar_item_para_peticion(db: Session, peticion: PeticionCliente, item: Item) -> None:
    """Assigna `item` a `peticion`, aplicant la bifurcació que el client ja
    va triar en acceptar (`chosen_delivery_method`):
    - envio / recollida_paga_ara: si ja hi ha una Order pagada esperant
      (cas normal, veure `_completar_order_pagada`), s'hi assigna
      l'exemplar i la petició queda 'recollida' d'una vegada. Si no (cas
      antic, abans del pagament en acceptar), es reserva sense caducitat i
      el client l'ha de comprar des del seu compte com abans.
    - recollida_paga_botiga: reserva de 72h (Via 2); si no ve a recollir-lo
      i pagar-lo, s'allibera sol i la petició caduca.
    NO fa commit: qui la crida ha de fer-ho, per poder incloure en la
    mateixa transacció altres canvis (p.ex. tancar la línia de la
    sol·licitud de compra associada)."""
    if peticion.status != EstadoPeticionCliente.en_tramit:
        raise HTTPException(409, "Aquesta petició no està en tràmit")
    if peticion.chosen_delivery_method is None:
        raise HTTPException(422, "La petició no té mètode d'entrega triat")
    if item.release_id != peticion.release_id:
        raise HTTPException(422, "Aquest exemplar no correspon al disc de la petició")

    if peticion.chosen_delivery_method != "recollida_paga_botiga":
        if _completar_order_pagada(db, peticion, item):
            return

    es_recollida_sense_pagar = peticion.chosen_delivery_method == "recollida_paga_botiga"
    reserved_until = (
        datetime.now(timezone.utc) + timedelta(hours=72) if es_recollida_sense_pagar else None
    )
    if item.condition == CondicionItem.nou:
        # Igual patró que reserve_stock (services/reservations.py) però SENSE
        # commit: cal poder-ho incloure a la mateixa transacció que la resta
        # de `recibir_comanda`/`vincular_item_peticion`.
        result = db.execute(
            update(Item)
            .where(Item.id == item.id, Item.quantity - Item.reserved_quantity >= 1)
            .values(reserved_quantity=Item.reserved_quantity + 1)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount == 0:
            raise HTTPException(409, "Aquest exemplar ja no està disponible")
        db.add(StockHold(item_id=item.id, quantity=1, peticion_id=peticion.id, reserved_until=reserved_until))
    else:
        result = db.execute(
            update(Item)
            .where(Item.id == item.id, Item.status == ItemStatus.disponible)
            .values(status=ItemStatus.reservado, reserved_for_peticion_id=peticion.id, reserved_until=reserved_until)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount == 0:
            raise HTTPException(409, "Aquest exemplar ja no està disponible")

    peticion.item_id = item.id
    peticion.status = EstadoPeticionCliente.reservada


def _enviar_email_item_arribat(db: Session, peticion: PeticionCliente, tenant: Tenant) -> None:
    disco = f"{peticion.release.artista} - {peticion.release.title}"
    lang = peticion.user.language
    necessita_accio = peticion.status != EstadoPeticionCliente.recollida
    link = _link_un_clic_a_peticions(db, peticion.user.email, lang, tenant) if necessita_accio else None

    if peticion.status == EstadoPeticionCliente.recollida:
        key = "email.peticion_arrived.paid_ship" if peticion.chosen_delivery_method == "envio" else "email.peticion_arrived.paid_pickup"
        cos = translate(db, key, lang, disco=disco)
    elif peticion.chosen_delivery_method == "recollida_paga_botiga":
        cos = translate(db, "email.peticion_arrived.pay_in_store", lang, disco=disco, link=link)
    else:
        key = "email.peticion_arrived.complete_ship" if peticion.chosen_delivery_method == "envio" else "email.peticion_arrived.complete_pickup"
        cos = translate(db, key, lang, disco=disco, link=link)

    send_email(
        to=peticion.user.email,
        subject=translate(db, "email.peticion_arrived.subject", lang, disco=disco),
        body=cos,
        tenant=tenant,
        db=db,
        html=render_email_html(
            translate(db, "email.peticion_arrived.heading", lang),
            f'<p style="font-size:14px;line-height:1.5">{cos}</p>',
            tenant, db,
            cta=(translate(db, "email.peticion_arrived.cta", lang), link) if link else None,
        ),
    )


def _tancar_linea_solicitud_desde_stock(db: Session, linea: SolicitudCompraLinea, item: Item) -> None:
    """Marca la línia de sol·licitud com a resolta amb un exemplar d'estoc
    (sense compra) i, si totes les línies de la sol·licitud ja estan
    resoltes, la passa a 'resolta'."""
    linea.item_resuelto_id = item.id
    solicitud = db.get(SolicitudCompra, linea.solicitud_id)
    if all(l.comanda_linea_id is not None or l.item_resuelto_id is not None for l in solicitud.lineas):
        solicitud.estado = EstadoSolicitud.resolta
