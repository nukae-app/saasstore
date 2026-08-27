"""Apartat "Banc" del superadmin — separat de Plans a petició de l'usuari
(2026-08-27): aquí es respon "està connectada la integració de pagaments?"
i "qui paga i qui no" de forma agregada, en lloc de tenir-ho escampat entre
la pantalla de Plans i el detall de cada tenant un per un."""

from app.models import (
    PlatformAdmin, PlatformAdminRole, PlatformInvoice, PlatformInvoiceStatus, PlatformPlan,
    Tenant, TenantBilling, TenantBillingStatus,
)
from app.services.security import hash_password

SUPERADMIN_HOST = {"Host": "superadmin.localhost"}


def _create_admin(db, email: str) -> PlatformAdmin:
    admin = PlatformAdmin(email=email, password_hash=hash_password("s3cret123"), role=PlatformAdminRole.owner)
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def _login(client, email: str) -> str:
    resp = client.post(
        "/superadmin/login", json={"email": email, "password": "s3cret123"}, headers=SUPERADMIN_HOST,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", **SUPERADMIN_HOST}


def test_status_sense_signing_secret_configurat(db, client, monkeypatch):
    from app.config import get_superadmin_settings
    monkeypatch.setattr(get_superadmin_settings(), "revolut_webhook_signing_secret", "")
    _create_admin(db, "owner@example.com")
    token = _login(client, "owner@example.com")

    resp = client.get("/superadmin/banc/status", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["webhook_configured"] is False


def test_status_amb_signing_secret_configurat_i_factures(db, client, monkeypatch):
    from app.config import get_superadmin_settings
    monkeypatch.setattr(get_superadmin_settings(), "revolut_webhook_signing_secret", "whsec_test")
    _create_admin(db, "owner2@example.com")
    token = _login(client, "owner2@example.com")
    tenant_id = db.info["tenant_id"]
    db.add(PlatformInvoice(tenant_id=tenant_id, amount="10.00", currency="EUR", status=PlatformInvoiceStatus.pagada))
    db.commit()

    resp = client.get("/superadmin/banc/status", headers=_auth(token))
    body = resp.json()
    assert body["webhook_configured"] is True
    assert body["invoices_count"] >= 1
    assert body["last_invoice_at"] is not None


def test_banc_tenants_reflecteix_pla_i_estat_assignats(db, client):
    _create_admin(db, "owner3@example.com")
    token = _login(client, "owner3@example.com")
    tenant_id = db.info["tenant_id"]

    plan = PlatformPlan(name="Bàsic", price="29.00", currency="EUR")
    db.add(plan)
    db.flush()
    db.add(TenantBilling(tenant_id=tenant_id, plan_id=plan.id, status=TenantBillingStatus.activa))
    db.commit()

    resp = client.get("/superadmin/banc/tenants", headers=_auth(token))
    assert resp.status_code == 200
    row = next(r for r in resp.json() if r["tenant_id"] == str(tenant_id))
    assert row["plan_name"] == "Bàsic"
    assert row["status"] == "activa"


def test_banc_tenants_sense_billing_es_sense_pla(db, client):
    _create_admin(db, "owner4@example.com")
    token = _login(client, "owner4@example.com")
    tenant_id = db.info["tenant_id"]

    resp = client.get("/superadmin/banc/tenants", headers=_auth(token))
    row = next(r for r in resp.json() if r["tenant_id"] == str(tenant_id))
    assert row["status"] == "sense_pla"
    assert row["plan_name"] is None


def test_banc_tenants_no_inclou_tenants_inactius(db, client):
    _create_admin(db, "owner5@example.com")
    token = _login(client, "owner5@example.com")
    other = Tenant(slug="inactiu-banc", domain="inactiu-banc.testserver", nombre="Inactiu", vertical_id="records", activo=False)
    db.add(other)
    db.commit()

    resp = client.get("/superadmin/banc/tenants", headers=_auth(token))
    assert not any(r["slug"] == "inactiu-banc" for r in resp.json())


def test_banc_invoices_llista_global_amb_nom_de_tenant(db, client):
    _create_admin(db, "owner6@example.com")
    token = _login(client, "owner6@example.com")
    tenant_id = db.info["tenant_id"]
    db.add(PlatformInvoice(tenant_id=tenant_id, amount="15.00", currency="EUR", status=PlatformInvoiceStatus.fallida))
    db.commit()

    resp = client.get("/superadmin/banc/invoices", headers=_auth(token))
    assert resp.status_code == 200
    assert any(inv["tenant_nombre"] == "Test Tenant" and inv["status"] == "fallida" for inv in resp.json())


def test_banc_requereix_autenticacio(client):
    assert client.get("/superadmin/banc/status", headers=SUPERADMIN_HOST).status_code == 401
    assert client.get("/superadmin/banc/tenants", headers=SUPERADMIN_HOST).status_code == 401
    assert client.get("/superadmin/banc/invoices", headers=SUPERADMIN_HOST).status_code == 401
