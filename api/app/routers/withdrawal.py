"""Función de desistimiento (Directiva 2011/83/UE art. 11 bis, añadido por la
Directiva (UE) 2023/2673; aplicable desde el 19-jun-2026).

Cualquier consumidor —con cuenta o invitado— puede comunicar el desistimiento
de un pedido web con dos datos: referencia del pedido y email de compra, sin
iniciar sesión. Al hacerlo:
  1. se sella `Order.withdrawal_requested_at` (de aquí cuentan los 14 días para
     reembolsar, y es la prueba de que se ejerció a tiempo);
  2. se envía al consumidor el acuse en soporte duradero (email), que exige la
     Directiva, y se avisa a la tienda.

NO cambia `status` ni devuelve stock: es una comunicación. La devolución física
y el reembolso los gestiona la tienda (el stock vuelve al recibir el género).

Respuesta uniforme (siempre 200): no revela qué pedidos existen para ese email
(si no, el endpoint serviría para enumerar compras ajenas).
"""

import html
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ConfiguracioBotiga, Order, OrderOrigen, OrderStatus, Tenant
from ..rate_limit import limiter
from ..services.emailer import render_email_html, send_email

router = APIRouter(prefix="/orders", tags=["withdrawal"])

# Textos propios del módulo (no del seed de traducciones): es un acuse legal,
# su redacción debe vivir junto a la lógica que lo envía y ser revisable en un sitio.
_TEXTS = {
    "ca": {
        "subject": "Hem rebut el teu desistiment — comanda {ref}",
        "heading": "Desistiment rebut",
        "body": "Hem rebut la teva comunicació de desistiment de la comanda <strong>{ref}</strong> el {when}. "
                "T'indicarem com tornar els productes; el reemborsament es fa en un màxim de 14 dies des d'aquesta comunicació, "
                "i podem retenir-lo fins que rebem els productes o en demostris l'enviament.",
    },
    "es": {
        "subject": "Hemos recibido tu desistimiento — pedido {ref}",
        "heading": "Desistimiento recibido",
        "body": "Hemos recibido tu comunicación de desistimiento del pedido <strong>{ref}</strong> el {when}. "
                "Te indicaremos cómo devolver los productos; el reembolso se hace en un máximo de 14 días desde esta comunicación, "
                "y podemos retenerlo hasta recibir los productos o que demuestres su envío.",
    },
    "en": {
        "subject": "We received your withdrawal — order {ref}",
        "heading": "Withdrawal received",
        "body": "We received your notice of withdrawal for order <strong>{ref}</strong> on {when}. "
                "We will tell you how to return the goods; the refund is made within 14 days of this notice, "
                "and we may withhold it until we receive the goods or you prove you have sent them back.",
    },
}


class WithdrawalIn(BaseModel):
    order_ref: str = Field(min_length=6, max_length=36)  # id completo o los primeros caracteres
    email: EmailStr
    name: str | None = Field(default=None, max_length=120)


@router.post("/withdrawal")
@limiter.limit("10/hour")
def request_withdrawal(request: Request, payload: WithdrawalIn, db: Session = Depends(get_db)):
    ref = payload.order_ref.strip().lower()
    # Pocos pedidos por email: se filtra el prefijo del UUID en Python (portable
    # entre Postgres y los tests en SQLite, sin CAST de uuid a texto).
    candidatos = db.scalars(
        select(Order).where(
            func.lower(Order.contact_email) == payload.email.lower(),
            Order.origin == OrderOrigen.web,
            Order.status != OrderStatus.cancelado,
        )
    ).all()
    order = next((o for o in candidatos if str(o.id).startswith(ref)), None)

    if order is not None and order.withdrawal_requested_at is None:
        now = datetime.now(timezone.utc)
        order.withdrawal_requested_at = now
        db.commit()
        _notify(db, order, now, payload.name)
    return {"ok": True}


def _notify(db: Session, order: Order, when: datetime, name: str | None) -> None:
    tenant = db.get(Tenant, order.tenant_id)
    ref = str(order.id)[:8]
    lang = order.language if order.language in _TEXTS else "ca"
    t = _TEXTS[lang]
    when_txt = when.strftime("%d/%m/%Y %H:%M UTC")
    body_html = f"<p>{t['body'].format(ref=ref, when=when_txt)}</p>"
    plain = f"{t['heading']}: {ref} ({when_txt})"
    send_email(
        order.contact_email, t["subject"].format(ref=ref), plain, tenant, db,
        html=render_email_html(t["heading"], body_html, tenant, db),
    )
    # Aviso a la tienda (en catalán: es el idioma de trabajo del equipo).
    config = db.scalar(select(ConfiguracioBotiga).where(ConfiguracioBotiga.tenant_id == tenant.id))
    destino = config.contact_email if config else None
    if destino:
        quien = html.escape(name or order.contact_email)
        send_email(
            destino, f"Desistiment rebut — comanda {ref}",
            f"{quien} ha desistit de la comanda {ref} ({order.contact_email}) el {when_txt}. "
            "El reemborsament s'ha de fer en un màxim de 14 dies des d'ara.",
            tenant, db,
        )
