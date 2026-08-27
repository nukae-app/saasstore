"""Tests de la Fase 2 del roadmap de superadmin (ver plan
/Users/paumartinez/.claude/plans/rustling-foraging-wind.md): editar
tenant, suspender/reactivar (Tenant.activo) y su efecto real sobre el
resto de la API (no solo el flag)."""

from app.models import PlatformAdmin, PlatformAdminRole, Tenant
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


def _seed_tenant(db, slug: str, domain: str) -> Tenant:
    tenant = Tenant(slug=slug, domain=domain, nombre=slug.title(), vertical_id="records")
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


def _owner_token(db, client, email="owner@example.com") -> str:
    _create_admin(db, email, PlatformAdminRole.owner)
    return _login(client, email)


def test_get_tenant(db, client):
    tenant = _seed_tenant(db, "florqa", "florqa.example.com")
    token = _owner_token(db, client)
    resp = client.get(f"/superadmin/tenants/{tenant.id}", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["domain"] == "florqa.example.com"


def test_update_nombre_y_queda_auditado(db, client):
    tenant = _seed_tenant(db, "florqa", "florqa.example.com")
    token = _owner_token(db, client)

    resp = client.patch(
        f"/superadmin/tenants/{tenant.id}", json={"nombre": "Flor QA Nou"}, headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["nombre"] == "Flor QA Nou"

    entries = client.get("/superadmin/audit-log", headers=_auth(token)).json()
    assert any(
        e["action"] == "tenant.update" and e["target_tenant_id"] == str(tenant.id)
        and e["details"] == {"nombre": "Flor QA Nou"}
        for e in entries
    )


def test_update_domain_duplicado_falla(db, client):
    _seed_tenant(db, "florqa", "florqa.example.com")
    otro = _seed_tenant(db, "cheeseshop", "cheeseshop.example.com")
    token = _owner_token(db, client)

    resp = client.patch(
        f"/superadmin/tenants/{otro.id}", json={"domain": "florqa.example.com"}, headers=_auth(token),
    )
    assert resp.status_code == 409


def test_update_vertical_invalido_falla(db, client):
    tenant = _seed_tenant(db, "florqa", "florqa.example.com")
    token = _owner_token(db, client)
    resp = client.patch(
        f"/superadmin/tenants/{tenant.id}", json={"vertical_id": "no-existe"}, headers=_auth(token),
    )
    assert resp.status_code == 422


def test_support_no_puede_editar_tenant(db, client):
    tenant = _seed_tenant(db, "florqa", "florqa.example.com")
    _create_admin(db, "support@example.com", PlatformAdminRole.support)
    token = _login(client, "support@example.com")
    resp = client.patch(
        f"/superadmin/tenants/{tenant.id}", json={"nombre": "Hackeat"}, headers=_auth(token),
    )
    assert resp.status_code == 403


def test_suspender_tenant_corta_su_api_de_verdad(db, client):
    """No solo el flag: un tenant suspendido deja de resolverse por su
    dominio (ver tenancy.py::resolve_tenant_by_domain + database.py::get_db),
    así que cualquier request tenant-scoped a su dominio debe dar 404."""
    tenant = _seed_tenant(db, "florqa", "florqa.example.com")
    token = _owner_token(db, client)

    # Antes de suspender: el dominio resuelve con normalidad (catálogo
    # público, sin auth).
    resp = client.get("/catalog", headers={"Host": "florqa.example.com"})
    assert resp.status_code == 200

    suspend = client.patch(
        f"/superadmin/tenants/{tenant.id}", json={"activo": False}, headers=_auth(token),
    )
    assert suspend.status_code == 200
    assert suspend.json()["activo"] is False

    resp = client.get("/catalog", headers={"Host": "florqa.example.com"})
    assert resp.status_code == 404

    entries = client.get("/superadmin/audit-log", headers=_auth(token)).json()
    assert any(
        e["action"] == "tenant.suspend" and e["target_tenant_id"] == str(tenant.id) for e in entries
    )

    reactivate = client.patch(
        f"/superadmin/tenants/{tenant.id}", json={"activo": True}, headers=_auth(token),
    )
    assert reactivate.status_code == 200
    resp = client.get("/catalog", headers={"Host": "florqa.example.com"})
    assert resp.status_code == 200

    entries = client.get("/superadmin/audit-log", headers=_auth(token)).json()
    assert any(
        e["action"] == "tenant.reactivate" and e["target_tenant_id"] == str(tenant.id) for e in entries
    )
