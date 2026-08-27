"""Webhook públic de Revolut Business (facturació de plataforma als
tenants) — a diferència de `routers/internal.py`, aquest SÍ ha de ser
accessible des d'internet (Revolut hi truca des dels seus servidors), i
per això s'autentica només amb la firma HMAC del payload
(`services/revolut_billing.py`), no amb cap token de sessió ni comprovació
de Host.

Format del payload assumit a partir de la documentació pública, NO
verificat contra un event real (sense credencials de sandbox encara, ver
models/platform.py per al context complet): s'espera un camp `event`
(un dels quatre documentats — SUBSCRIPTION_INITIATED/_OVERDUE/_CANCELLED/
_FINISHED) i `data.subscription_id` per localitzar el `TenantBilling`
corresponent. El payload complet es guarda sempre a
`PlatformInvoice.raw_event`: si l'estructura real difereix del que s'ha
assumit aquí, la informació no es perd i es pot reprocessar a mà."""

import logging
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_superadmin_settings
from ..database import get_db_unscoped
from ..models import PlatformInvoice, PlatformInvoiceStatus, TenantBilling, TenantBillingStatus
from ..services.revolut_billing import InvalidRevolutSignature, verify_revolut_signature

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["billing"])

_STATUS_BY_EVENT = {
    "SUBSCRIPTION_INITIATED": TenantBillingStatus.activa,
    "SUBSCRIPTION_OVERDUE": TenantBillingStatus.impagada,
    "SUBSCRIPTION_CANCELLED": TenantBillingStatus.cancellada,
    "SUBSCRIPTION_FINISHED": TenantBillingStatus.cancellada,
}
# Només aquests dos events representen un cobrament (fet o fallit) que
# mereix una fila a `PlatformInvoice` — els altres dos són canvis d'estat
# sense moviment de diners associat.
_INVOICE_STATUS_BY_EVENT = {
    "SUBSCRIPTION_INITIATED": PlatformInvoiceStatus.pagada,
    "SUBSCRIPTION_OVERDUE": PlatformInvoiceStatus.fallida,
}


@router.post("/revolut")
async def revolut_webhook(request: Request, db: Session = Depends(get_db_unscoped)):
    payload = await request.body()
    try:
        verify_revolut_signature(
            payload=payload,
            signature_header=request.headers.get("Revolut-Signature"),
            timestamp_header=request.headers.get("Revolut-Request-Timestamp"),
            signing_secret=get_superadmin_settings().revolut_webhook_signing_secret,
        )
    except InvalidRevolutSignature as exc:
        raise HTTPException(401, str(exc))

    body = await request.json()
    event_type = body.get("event")
    data = body.get("data") or {}
    subscription_id = data.get("subscription_id") or body.get("subscription_id")
    event_id = body.get("id") or body.get("event_id")

    # 200 en tots els casos "no accionables" (esdeveniment desconegut,
    # subscripció no localitzada) a propòsit: un 4xx faria que Revolut
    # reintentés indefinidament un event que mai passarà a ser accionable.
    if subscription_id is None:
        logger.warning("Webhook de Revolut sense subscription_id (event=%s)", event_type)
        return {"ok": True}

    tenant_billing = db.scalar(
        select(TenantBilling).where(TenantBilling.revolut_subscription_id == subscription_id)
    )
    if tenant_billing is None:
        logger.warning("Webhook de Revolut per una subscripció no reconeguda: %s", subscription_id)
        return {"ok": True}

    # Idempotència: les entregues de webhook són "at-least-once" — un event
    # ja processat no ha de tornar a canviar l'estat ni duplicar la factura.
    if event_id and db.scalar(select(PlatformInvoice).where(PlatformInvoice.revolut_event_id == event_id)):
        return {"ok": True}

    if event_type in _STATUS_BY_EVENT:
        tenant_billing.status = _STATUS_BY_EVENT[event_type]

    invoice_status = _INVOICE_STATUS_BY_EVENT.get(event_type)
    if invoice_status is not None:
        try:
            amount = Decimal(str(data.get("amount", "0")))
        except InvalidOperation:
            amount = Decimal("0")
        db.add(PlatformInvoice(
            tenant_id=tenant_billing.tenant_id, revolut_event_id=event_id,
            amount=amount, currency=data.get("currency", "EUR"),
            status=invoice_status, raw_event=body,
        ))

    db.commit()
    return {"ok": True}
