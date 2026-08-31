"""Tests de la Fase 1 del roadmap de superadmin (ver plan
/Users/paumartinez/.claude/plans/rustling-foraging-wind.md): roles de
PlatformAdmin (`owner`/`support`) y el audit log de acciones mutables."""

from app.models import PlatformAdmin, PlatformAdminRole
from app.services.security import hash_password

SUPERADMIN_HOST = {"Host": "superadmin.localhost"}


def _create_admin(db, email: str, role: PlatformAdminRole) -> PlatformAdmin:
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


def _tenant_payload(slug: str) -> dict:
    return {
        "slug": slug, "domain": f"{slug}.example.com", "nombre": slug.title(),
        "fiscal_name": slug.title(), "address": "Carrer Fals 1", "vertical_id": "records",
        "legal_form": "sl",
    }


def test_me_devuelve_el_rol(db, client):
    _create_admin(db, "owner@example.com", PlatformAdminRole.owner)
    token = _login(client, "owner@example.com")
    resp = client.get("/superadmin/me", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["role"] == "owner"


def test_support_no_puede_crear_tenant(db, client):
    _create_admin(db, "support@example.com", PlatformAdminRole.support)
    token = _login(client, "support@example.com")
    resp = client.post("/superadmin/tenants", json=_tenant_payload("florqa"), headers=_auth(token))
    assert resp.status_code == 403


def test_owner_puede_crear_tenant_y_queda_auditado(db, client, monkeypatch):
    # seed_translations usa gen_random_uuid() (nativo en Postgres real, ver
    # scripts/seed_translations.py) — no existe en SQLite, motor de estos
    # tests. No es cosa de esta fase arreglarlo: se neutraliza aquí igual
    # que _fake_tenant_secrets neutraliza Redis/AWS en conftest.py.
    monkeypatch.setattr("app.routers.superadmin.seed_translations", lambda *a, **k: None)
    monkeypatch.setattr("app.routers.superadmin.seed_legal_pages", lambda *a, **k: None)

    admin = _create_admin(db, "owner2@example.com", PlatformAdminRole.owner)
    token = _login(client, "owner2@example.com")

    resp = client.post("/superadmin/tenants", json=_tenant_payload("cheeseshop"), headers=_auth(token))
    assert resp.status_code == 201, resp.text
    tenant_id = resp.json()["id"]

    log_resp = client.get("/superadmin/audit-log", headers=_auth(token))
    assert log_resp.status_code == 200
    entries = log_resp.json()
    assert any(
        e["action"] == "tenant.create" and e["target_tenant_id"] == tenant_id
        and e["platform_admin_id"] == str(admin.id)
        for e in entries
    )


def test_support_puede_leer_el_audit_log(db, client):
    _create_admin(db, "support2@example.com", PlatformAdminRole.support)
    token = _login(client, "support2@example.com")
    resp = client.get("/superadmin/audit-log", headers=_auth(token))
    assert resp.status_code == 200


def test_audit_log_requiere_autenticacion(client):
    resp = client.get("/superadmin/audit-log", headers=SUPERADMIN_HOST)
    assert resp.status_code == 401
