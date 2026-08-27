"""Endpoint del webhook de Revolut (`POST /webhooks/revolut`) — cobreix el
camí complet (firma vàlida, cerca de tenant per subscription_id, canvi
d'estat, creació de factura, idempotència) i el rebuig de payloads mal
firmats. Sense credencials reals de Revolut (ver models/platform.py per
context): el format del payload és una assumpció documentada al propi
router, no verificada contra un event real."""

import hashlib
import hmac
import time
from decimal import Decimal

from app.models import PlatformInvoice, TenantBilling, TenantBillingStatus

SECRET = "whsec_test"


def _sign(payload: bytes, timestamp: str, secret: str = SECRET) -> str:
    message = f"v1.{timestamp}.".encode() + payload
    digest = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return f"v1={digest}"


def _headers(payload: bytes) -> dict:
    timestamp = str(int(time.time() * 1000))
    return {"Revolut-Signature": _sign(payload, timestamp), "Revolut-Request-Timestamp": timestamp}


def _configure_secret(monkeypatch):
    monkeypatch.setattr(
        "app.routers.billing_webhooks.get_superadmin_settings",
        lambda: type("S", (), {"revolut_webhook_signing_secret": SECRET})(),
    )


def _seed_billing(db, subscription_id: str) -> TenantBilling:
    tenant_id = db.info["tenant_id"]
    tb = TenantBilling(tenant_id=tenant_id, revolut_subscription_id=subscription_id, status=TenantBillingStatus.pendent_targeta)
    db.add(tb)
    db.commit()
    return tb


def test_webhook_rebutja_signatura_incorrecta(client, monkeypatch):
    _configure_secret(monkeypatch)
    resp = client.post(
        "/webhooks/revolut", json={"event": "SUBSCRIPTION_INITIATED"},
        headers={"Revolut-Signature": "v1=deadbeef", "Revolut-Request-Timestamp": str(int(time.time() * 1000))},
    )
    assert resp.status_code == 401


def test_webhook_sense_capcaleres_es_rebutjat(client, monkeypatch):
    _configure_secret(monkeypatch)
    resp = client.post("/webhooks/revolut", json={"event": "SUBSCRIPTION_INITIATED"})
    assert resp.status_code == 401


def test_webhook_subscripcio_desconeguda_no_peta(client, monkeypatch):
    _configure_secret(monkeypatch)
    payload = b'{"event": "SUBSCRIPTION_INITIATED", "data": {"subscription_id": "sub_no_existeix"}}'
    resp = client.post("/webhooks/revolut", content=payload, headers={
        "Content-Type": "application/json", **_headers(payload),
    })
    assert resp.status_code == 200


def test_webhook_initiated_activa_subscripcio_i_crea_factura(db, client, monkeypatch):
    _configure_secret(monkeypatch)
    _seed_billing(db, "sub_123")

    payload = (
        b'{"event": "SUBSCRIPTION_INITIATED", "id": "evt_1", '
        b'"data": {"subscription_id": "sub_123", "amount": "29.00", "currency": "EUR"}}'
    )
    resp = client.post("/webhooks/revolut", content=payload, headers={
        "Content-Type": "application/json", **_headers(payload),
    })
    assert resp.status_code == 200, resp.text

    db.expire_all()
    tb = db.query(TenantBilling).filter_by(revolut_subscription_id="sub_123").one()
    assert tb.status == TenantBillingStatus.activa

    invoice = db.query(PlatformInvoice).filter_by(revolut_event_id="evt_1").one()
    assert invoice.amount == Decimal("29.00")
    assert invoice.status.value == "pagada"


def test_webhook_overdue_marca_impagada(db, client, monkeypatch):
    _configure_secret(monkeypatch)
    _seed_billing(db, "sub_456")

    payload = b'{"event": "SUBSCRIPTION_OVERDUE", "id": "evt_2", "data": {"subscription_id": "sub_456"}}'
    resp = client.post("/webhooks/revolut", content=payload, headers={
        "Content-Type": "application/json", **_headers(payload),
    })
    assert resp.status_code == 200

    db.expire_all()
    tb = db.query(TenantBilling).filter_by(revolut_subscription_id="sub_456").one()
    assert tb.status == TenantBillingStatus.impagada


def test_webhook_event_repetit_es_idempotent(db, client, monkeypatch):
    _configure_secret(monkeypatch)
    _seed_billing(db, "sub_789")

    payload = (
        b'{"event": "SUBSCRIPTION_INITIATED", "id": "evt_3", '
        b'"data": {"subscription_id": "sub_789", "amount": "10.00", "currency": "EUR"}}'
    )
    headers1 = {"Content-Type": "application/json", **_headers(payload)}
    headers2 = {"Content-Type": "application/json", **_headers(payload)}
    assert client.post("/webhooks/revolut", content=payload, headers=headers1).status_code == 200
    assert client.post("/webhooks/revolut", content=payload, headers=headers2).status_code == 200

    db.expire_all()
    count = db.query(PlatformInvoice).filter_by(revolut_event_id="evt_3").count()
    assert count == 1
