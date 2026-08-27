"""CRUD de `PlatformPlan` i estat de facturació per tenant
(`TenantBilling`/`PlatformInvoice`) des del superadmin — la part del flux de
facturació que NO depèn de credencials reals de Revolut (ver
models/platform.py per context: `revolut_*` s'edita a mà mentre no hi ha
integració provada)."""

from app.models import PlatformAdmin, PlatformAdminRole, PlatformInvoice, PlatformInvoiceStatus, TenantBilling
from app.services.security import hash_password

SUPERADMIN_HOST = {"Host": "superadmin.localhost"}


def _create_admin(db, email: str, role: PlatformAdminRole = PlatformAdminRole.owner) -> PlatformAdmin:
    admin = PlatformAdmin(email=email, password_hash=hash_password("s3cret123"), role=role)
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


def _plan_payload(name: str = "Bàsic") -> dict:
    return {"name": name, "price": "29.00", "currency": "EUR", "billing_period": "monthly"}


def test_support_no_pot_crear_pla(db, client):
    _create_admin(db, "support@example.com", PlatformAdminRole.support)
    token = _login(client, "support@example.com")
    resp = client.post("/superadmin/plans", json=_plan_payload(), headers=_auth(token))
    assert resp.status_code == 403


def test_owner_crea_pla_i_queda_auditat(db, client):
    admin = _create_admin(db, "owner@example.com")
    token = _login(client, "owner@example.com")

    resp = client.post("/superadmin/plans", json=_plan_payload(), headers=_auth(token))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "Bàsic"
    assert body["price"] == "29.00"
    assert body["active"] is True

    log_resp = client.get("/superadmin/audit-log", headers=_auth(token))
    entries = log_resp.json()
    assert any(
        e["action"] == "plan.create" and e["platform_admin_id"] == str(admin.id)
        for e in entries
    )


def test_editar_pla_actualitza_preu(db, client):
    _create_admin(db, "owner2@example.com")
    token = _login(client, "owner2@example.com")
    plan = client.post("/superadmin/plans", json=_plan_payload(), headers=_auth(token)).json()

    resp = client.patch(
        f"/superadmin/plans/{plan['id']}", json={"price": "39.00", "active": False}, headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["price"] == "39.00"
    assert resp.json()["active"] is False


def test_tenant_billing_per_defecte_es_sense_pla(db, client):
    _create_admin(db, "owner3@example.com")
    token = _login(client, "owner3@example.com")
    tenant_id = db.info["tenant_id"]

    resp = client.get(f"/superadmin/tenants/{tenant_id}/billing", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "sense_pla"
    assert body["plan_id"] is None
    assert body["plan_name"] is None


def test_assignar_pla_inexistent_dona_422(db, client):
    _create_admin(db, "owner4@example.com")
    token = _login(client, "owner4@example.com")
    tenant_id = db.info["tenant_id"]

    resp = client.patch(
        f"/superadmin/tenants/{tenant_id}/billing",
        json={"plan_id": "00000000-0000-0000-0000-000000000000"}, headers=_auth(token),
    )
    assert resp.status_code == 422


def test_assignar_pla_i_marcar_pendent_targeta(db, client):
    admin = _create_admin(db, "owner5@example.com")
    token = _login(client, "owner5@example.com")
    tenant_id = db.info["tenant_id"]
    plan = client.post("/superadmin/plans", json=_plan_payload(), headers=_auth(token)).json()

    resp = client.patch(
        f"/superadmin/tenants/{tenant_id}/billing",
        json={"plan_id": plan["id"], "status": "pendent_targeta"}, headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["plan_id"] == plan["id"]
    assert body["plan_name"] == "Bàsic"
    assert body["status"] == "pendent_targeta"

    log_resp = client.get("/superadmin/audit-log", headers=_auth(token))
    entries = log_resp.json()
    assert any(
        e["action"] == "tenant_billing.update" and e["platform_admin_id"] == str(admin.id)
        and e["target_tenant_id"] == str(tenant_id)
        for e in entries
    )


def test_llistat_de_factures_del_tenant(db, client):
    _create_admin(db, "owner6@example.com")
    token = _login(client, "owner6@example.com")
    tenant_id = db.info["tenant_id"]
    db.add(PlatformInvoice(
        tenant_id=tenant_id, amount="29.00", currency="EUR", status=PlatformInvoiceStatus.pagada,
    ))
    db.commit()

    resp = client.get(f"/superadmin/tenants/{tenant_id}/invoices", headers=_auth(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["status"] == "pagada"


def test_billing_de_tenant_inexistent_dona_404(db, client):
    _create_admin(db, "owner7@example.com")
    token = _login(client, "owner7@example.com")
    resp = client.get(
        "/superadmin/tenants/00000000-0000-0000-0000-000000000000/billing", headers=_auth(token),
    )
    assert resp.status_code == 404
