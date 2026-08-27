"""Tests de la Fase 3 del roadmap de superadmin (ver plan
/Users/paumartinez/.claude/plans/rustling-foraging-wind.md): UI/API de
tenant_features — confirma que el camino de escritura del superadmin
converge en la misma fila TenantFeature que ya escribía
ConfiguracioBotiga.discogs_habilitat/.subscripcions_actives (Fase 7)."""

from sqlalchemy import select

from app.models import ConfiguracioBotiga, PlatformAdmin, PlatformAdminRole, Tenant
from app.services.security import hash_password
from app.tenancy import scoped_to

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


def _owner_token(db, client, email="owner@example.com") -> str:
    _create_admin(db, email, PlatformAdminRole.owner)
    return _login(client, email)


def _seed_tenant_with_config(db, slug: str) -> Tenant:
    tenant = Tenant(slug=slug, domain=f"{slug}.example.com", nombre=slug.title(), vertical_id="records")
    db.add(tenant)
    db.flush()
    with scoped_to(db, tenant.id):
        db.add(ConfiguracioBotiga(fiscal_name=slug.title(), address="Carrer Fals 1"))
        db.commit()
    db.refresh(tenant)
    return tenant


def test_features_por_defecto_desactivadas(db, client):
    tenant = _seed_tenant_with_config(db, "florqa")
    token = _owner_token(db, client)
    resp = client.get(f"/superadmin/tenants/{tenant.id}/features", headers=_auth(token))
    assert resp.status_code == 200
    assert {f["feature_key"]: f["enabled"] for f in resp.json()} == {
        "discogs_sync": False, "subscriptions": False,
    }


def test_toggle_feature_desconocida_falla(db, client):
    tenant = _seed_tenant_with_config(db, "florqa")
    token = _owner_token(db, client)
    resp = client.patch(
        f"/superadmin/tenants/{tenant.id}/features/no-existe", json={"enabled": True}, headers=_auth(token),
    )
    assert resp.status_code == 404


def test_support_no_puede_tocar_features(db, client):
    tenant = _seed_tenant_with_config(db, "florqa")
    _create_admin(db, "support@example.com", PlatformAdminRole.support)
    token = _login(client, "support@example.com")
    resp = client.patch(
        f"/superadmin/tenants/{tenant.id}/features/discogs_sync", json={"enabled": True}, headers=_auth(token),
    )
    assert resp.status_code == 403


def test_toggle_feature_queda_auditado_y_converge_con_configuraciobotiga(db, client):
    tenant = _seed_tenant_with_config(db, "florqa")
    token = _owner_token(db, client)

    resp = client.patch(
        f"/superadmin/tenants/{tenant.id}/features/discogs_sync", json={"enabled": True}, headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json() == {"feature_key": "discogs_sync", "label": "Discogs sync", "enabled": True}

    listed = client.get(f"/superadmin/tenants/{tenant.id}/features", headers=_auth(token)).json()
    assert {f["feature_key"]: f["enabled"] for f in listed}["discogs_sync"] is True

    entries = client.get("/superadmin/audit-log", headers=_auth(token)).json()
    assert any(
        e["action"] == "tenant_feature.toggle" and e["target_tenant_id"] == str(tenant.id)
        and e["details"] == {"feature_key": "discogs_sync", "enabled": True}
        for e in entries
    )

    # Mismo camino de lectura que ya usa el resto del backend (p.ej.
    # require_discogs_enabled en routers/admin.py) — confirma que ambos
    # caminos de escritura (esta API y ConfiguracioBotiga) convergen en la
    # misma fila TenantFeature.
    with scoped_to(db, tenant.id):
        config = db.scalar(select(ConfiguracioBotiga).where(ConfiguracioBotiga.tenant_id == tenant.id))
        assert config.discogs_habilitat is True
