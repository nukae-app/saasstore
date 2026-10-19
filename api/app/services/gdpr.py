"""Derechos RGPD del titular: acceso/portabilidad (art. 15 y 20) y supresión
(art. 17). Un solo sitio para los dos flujos: el autoservicio del cliente
(`/me/data-export`, `DELETE /me`) y la anonimización desde el panel de admin
(`POST /admin/users/{id}/anonymize`) llaman a las mismas funciones, para que
no puedan divergir en qué se borra.

Qué se CONSERVA al anonimizar, y por qué (base legal art. 6.1.c RGPD):
- `orders` / `order_items` / `payments`: obligación fiscal y mercantil
  (decisión #5 de CLAUDE.md). Del pedido se conserva `shipping_address` (snapshot
  de entrega: sirve de prueba ante reclamaciones y garantía legal) y se sustituye
  `contact_email` por el pseudónimo, salvo en pedidos aún en curso.
- `documents` (facturas/albaranes/presupuestos): el nombre/NIF del cliente forman
  parte del documento fiscal y no se tocan.
- `compras` a particulares (segunda mano): libro registro de objetos usados.
- `cobraments_subscripcio`: histórico de cobros de la suscripción.

Todo lo demás (cuenta, credenciales, direcciones, sesiones, vínculos con
Google/Spotify, carrito, notas, consentimientos) se borra o se vacía.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, selectinload

from ..models import (
    Address,
    AuthToken,
    Cart,
    CartItem,
    EstadoPeticionCliente,
    EstatSubscripcio,
    Identity,
    Item,
    ItemStatus,
    NewsletterCampaign,
    NewsletterSend,
    NotificationPref,
    Order,
    OrderItem,
    OrderStatus,
    PeticionCliente,
    RefreshToken,
    SpotifyConnection,
    StockHold,
    Subscripcio,
    User,
)
from .reservations import release_stock_hold

# Pedidos que aún no han terminado su ciclo: borrar la cuenta ahora dejaría al
# cliente sin poder recibir avisos de su compra.
_ORDERS_EN_CURS = (OrderStatus.pendiente_pago, OrderStatus.pagado, OrderStatus.enviado)
_PETICIONES_FINALS = (
    EstadoPeticionCliente.cancelada,
    EstadoPeticionCliente.recollida,
    EstadoPeticionCliente.caducada,
    EstadoPeticionCliente.rebutjada,
)
_SUBS_ACTIVES = (EstatSubscripcio.pendent_pagament, EstatSubscripcio.activa, EstatSubscripcio.pausada)


class ErasureBlocked(Exception):
    """La cuenta no se puede anonimizar todavía. `reasons` son claves estables
    (el frontend las traduce); no mensajes."""

    def __init__(self, reasons: list[str]):
        super().__init__(", ".join(reasons))
        self.reasons = reasons


def _rel(order_item):
    return order_item.release or (order_item.item.release if order_item.item else None)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


# ---------------------------------------------------------------------------
# Exportación (art. 15 + 20)
# ---------------------------------------------------------------------------

def export_user_data(db: Session, user: User) -> dict:
    """Todo lo que el sistema guarda sobre `user`, en JSON legible por máquina.
    No incluye secretos (hash de contraseña, tokens) ni datos de terceros."""
    identities = db.scalars(select(Identity).where(Identity.user_id == user.id)).all()
    addresses = db.scalars(select(Address).where(Address.user_id == user.id)).all()
    orders = db.scalars(
        select(Order)
        .where(Order.user_id == user.id)
        .options(
            selectinload(Order.items).selectinload(OrderItem.release),
            selectinload(Order.items).selectinload(OrderItem.item).selectinload(Item.release),
        )
        .order_by(Order.created_at)
    ).all()
    peticiones = db.scalars(select(PeticionCliente).where(PeticionCliente.user_id == user.id)).all()
    subs = db.scalars(
        select(Subscripcio).where(Subscripcio.user_id == user.id).options(selectinload(Subscripcio.cobraments))
    ).all()
    spotify = db.get(SpotifyConnection, user.id)
    sends = db.execute(
        select(NewsletterSend, NewsletterCampaign.subject)
        .join(NewsletterCampaign, NewsletterCampaign.id == NewsletterSend.campaign_id)
        .where(NewsletterSend.user_id == user.id)
    ).all()

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "profile": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "phone": user.phone,
            "language": user.language,
            "email_verified": user.email_verified,
            "created_at": _iso(user.created_at),
            "consent_newsletter": user.consent_newsletter,
        },
        "login_methods": {
            "password": bool(user.password_hash),
            "linked_providers": [{"provider": i.provider, "linked_at": _iso(i.created_at)} for i in identities],
        },
        "addresses": [
            {
                "recipient_name": a.recipient_name, "address_line1": a.address_line1,
                "address_line2": a.address_line2, "city": a.city, "postal_code": a.postal_code,
                "province": a.province, "country": a.country, "phone": a.phone, "is_default": a.is_default,
            }
            for a in addresses
        ],
        "orders": [
            {
                "id": str(o.id), "created_at": _iso(o.created_at), "status": o.status.value,
                "contact_email": o.contact_email, "total": str(o.total), "shipping_cost": str(o.shipping_cost),
                "shipping_method": o.shipping_method, "payment_method": o.payment_method,
                "shipping_address": o.shipping_address, "notes": o.notes,
                "tracking_number": o.tracking_number, "carrier": o.carrier,
                "coupon_code": o.coupon_code,
                "items": [
                    {
                        "artist": (_rel(li).artista if _rel(li) else None),
                        "title": (_rel(li).title if _rel(li) else None),
                        "price": str(li.price), "quantity": li.quantity,
                    }
                    for li in o.items
                ],
            }
            for o in orders
        ],
        "requests": [
            {
                "id": str(p.id), "created_at": _iso(p.created_at), "status": p.status.value,
                "artist": p.free_artist, "title": p.free_title, "notes": p.client_notes,
                "estimated_price": str(p.estimated_price) if p.estimated_price is not None else None,
            }
            for p in peticiones
        ],
        "club_subscriptions": [
            {
                "id": str(s.id), "status": s.estat.value, "created_at": _iso(s.created_at),
                "every_months": s.periodicitat_mesos, "quantity": s.quantitat,
                "price_per_period": str(s.preu_periode), "preferred_genres": s.generes_preferits,
                "payments": [
                    {"period": c.periode.isoformat(), "amount": str(c.import_), "status": c.estat.value}
                    for c in s.cobraments
                ],
            }
            for s in subs
        ],
        "spotify": (
            {"display_name": spotify.display_name, "connected_at": _iso(spotify.connected_at)} if spotify else None
        ),
        "newsletter": {
            "subscribed": user.consent_newsletter,
            "received": [{"campaign": subject, "sent_at": _iso(s.sent_at)} for s, subject in sends],
        },
    }


# ---------------------------------------------------------------------------
# Supresión (art. 17)
# ---------------------------------------------------------------------------

def erasure_blockers(db: Session, user: User) -> list[str]:
    """Razones por las que ahora no se debe borrar la cuenta (vacío = se puede)."""
    reasons: list[str] = []
    if user.role == "admin":
        reasons.append("is_admin")
    if db.scalar(select(Order.id).where(Order.user_id == user.id, Order.status.in_(_ORDERS_EN_CURS)).limit(1)):
        reasons.append("open_orders")
    if db.scalar(select(Subscripcio.id).where(Subscripcio.user_id == user.id, Subscripcio.estat.in_(_SUBS_ACTIVES)).limit(1)):
        reasons.append("active_subscription")
    if db.scalar(
        select(PeticionCliente.id)
        .where(PeticionCliente.user_id == user.id, PeticionCliente.status.not_in(_PETICIONES_FINALS))
        .limit(1)
    ):
        reasons.append("open_requests")
    return reasons


def _purge_cart(db: Session, user: User) -> None:
    cart = db.scalar(select(Cart).where(Cart.user_id == user.id))
    if cart is None:
        return
    # Las retenciones de stock agregado (nou) hay que devolverlas una a una:
    # borrar el carrito en cascada dejaría `reserved_quantity` inflado.
    for hold_id in db.scalars(select(StockHold.id).where(StockHold.cart_id == cart.id)).all():
        release_stock_hold(db, hold_id)
    db.execute(
        update(Item)
        .where(Item.reserved_by_cart_id == cart.id, Item.status == ItemStatus.reservado)
        .values(status=ItemStatus.disponible, reserved_until=None, reserved_by_cart_id=None)
    )
    db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
    db.delete(cart)


def anonymize_user(db: Session, user: User, *, force: bool = False) -> str:
    """Borra/vacía todos los datos personales de `user` conservando lo que la
    ley obliga a guardar (ver docstring del módulo). Devuelve el email
    seudónimo. `force=True` (solo admin) ignora los bloqueos y cancela la
    suscripción/peticiones abiertas. Hace commit."""
    blockers = erasure_blockers(db, user)
    if not force and blockers:
        raise ErasureBlocked(blockers)
    if force and "is_admin" in blockers:
        raise ErasureBlocked(["is_admin"])  # nunca se deja a un tenant sin admin por esta vía

    old_email = user.email
    anon_email = f"anon-{uuid.uuid4().hex[:12]}@deleted.local"
    now = datetime.now(timezone.utc)

    # Suscripción del club: se cancela (y se olvida el identificador de cobro
    # recurrente de Redsys) pero la fila y sus cobros se conservan.
    subs = db.scalars(select(Subscripcio).where(Subscripcio.user_id == user.id)).all()
    for s in subs:
        if s.estat != EstatSubscripcio.cancel_lada:
            s.estat = EstatSubscripcio.cancel_lada
            s.cancel_lada_at = now
        s.redsys_identifier = None
        s.redsys_cof_txnid = None

    # Direcciones: la suscripción tiene FK RESTRICT a su dirección, así que las
    # que cuelgan de una suscripción se vacían en sitio y el resto se borran.
    used_by_sub = {s.address_id for s in subs}
    for a in db.scalars(select(Address).where(Address.user_id == user.id)).all():
        if a.id in used_by_sub:
            a.recipient_name, a.address_line1, a.address_line2 = "—", "—", None
            a.city, a.postal_code, a.province, a.phone, a.is_default = "—", "—", None, None, False
        else:
            db.delete(a)

    # Peticiones: se mantienen (enlazan con compras a proveedor y pedidos) pero
    # sin el texto libre del cliente; las abiertas se cancelan con `force`.
    for p in db.scalars(select(PeticionCliente).where(PeticionCliente.user_id == user.id)).all():
        p.client_notes = None
        p.admin_notes = None
        if force and p.status not in _PETICIONES_FINALS:
            p.status = EstadoPeticionCliente.cancelada

    # Pedidos terminados: el email de contacto ya no hace falta. Los que siguen
    # en curso (solo posible con `force`) lo conservan para poder avisar.
    db.execute(
        update(Order)
        .where(Order.user_id == user.id, Order.status.not_in(_ORDERS_EN_CURS))
        .values(contact_email=anon_email)
    )
    db.execute(update(NewsletterSend).where(NewsletterSend.user_id == user.id).values(email=anon_email))

    _purge_cart(db, user)
    db.execute(delete(Identity).where(Identity.user_id == user.id))
    db.execute(delete(SpotifyConnection).where(SpotifyConnection.user_id == user.id))
    db.execute(delete(NotificationPref).where(NotificationPref.user_id == user.id))
    db.execute(delete(AuthToken).where(AuthToken.email == old_email))
    # Sesiones: se borran (no solo se revocan) para que el hash no quede.
    db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))

    user.email = anon_email
    user.name = None
    user.phone = None
    user.password_hash = None
    user.internal_notes = None
    user.consent_newsletter = False
    user.email_verified = False
    user.active = False
    db.commit()
    return anon_email
