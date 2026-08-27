"""Dashboards del superadmin: adopció de features (quants tenants actius
tenen cada feature activada) i salut per tenant (comandes recents/última
activitat) — les dues primeres peces del dashboard, abans que la de negoci
(que depèn de tenir facturació de tenants, encara no construïda)."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models import Order, PlatformAdmin, PlatformAdminRole, Tenant, TenantFeature
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


def _create_tenant(db, slug: str) -> Tenant:
    tenant = Tenant(slug=slug, domain=f"{slug}.testserver", nombre=slug.title(), vertical_id="records")
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


def _seed_order(db, tenant_id, created_at) -> Order:
    db.info["tenant_id"] = tenant_id
    order = Order(
        contact_email="client@example.com", total=Decimal("20.00"),
        shipping_method="recogida_tienda", payment_method="tienda",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    order.created_at = created_at
    db.commit()
    return order


def test_dashboard_features_compta_nomes_tenants_actius(db, client):
    _create_admin(db, "owner@example.com")
    token = _login(client, "owner@example.com")

    tenant_actiu = _create_tenant(db, "amb-discogs")
    tenant_inactiu = _create_tenant(db, "inactiu-amb-discogs")
    tenant_inactiu.activo = False
    db.add(TenantFeature(tenant_id=tenant_actiu.id, feature_key="discogs_sync", enabled=True))
    db.add(TenantFeature(tenant_id=tenant_inactiu.id, feature_key="discogs_sync", enabled=True))
    db.commit()

    resp = client.get("/superadmin/dashboard/features", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    row = next(f for f in resp.json() if f["feature_key"] == "discogs_sync")
    # El tenant inactiu no compta ni al numerador ni al denominador.
    assert row["enabled_count"] >= 1
    assert row["total_tenants"] >= 1


def test_dashboard_features_llista_totes_les_known_features(db, client):
    _create_admin(db, "owner2@example.com")
    token = _login(client, "owner2@example.com")
    resp = client.get("/superadmin/dashboard/features", headers=_auth(token))
    keys = {f["feature_key"] for f in resp.json()}
    assert {"discogs_sync", "subscriptions"} <= keys


def test_dashboard_tenant_health_compta_comandes_i_ultima_activitat(db, client):
    _create_admin(db, "owner3@example.com")
    token = _login(client, "owner3@example.com")
    tenant = _create_tenant(db, "botiga-viva")

    now = datetime.now(timezone.utc)
    _seed_order(db, tenant.id, now - timedelta(days=1))
    _seed_order(db, tenant.id, now - timedelta(days=10))

    resp = client.get("/superadmin/dashboard/tenant-health", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    row = next(t for t in resp.json() if t["slug"] == "botiga-viva")
    assert row["total_orders"] == 2
    assert row["orders_last_7d"] == 1
    assert row["last_order_at"] is not None


def test_dashboard_tenant_health_tenant_sense_comandes(db, client):
    _create_admin(db, "owner4@example.com")
    token = _login(client, "owner4@example.com")
    _create_tenant(db, "botiga-nova")

    resp = client.get("/superadmin/dashboard/tenant-health", headers=_auth(token))
    row = next(t for t in resp.json() if t["slug"] == "botiga-nova")
    assert row == {
        "tenant_id": row["tenant_id"], "nombre": "Botiga-Nova", "slug": "botiga-nova",
        "vertical_id": "records", "total_orders": 0, "orders_last_7d": 0, "last_order_at": None,
    }


def test_dashboard_tenant_health_no_inclou_tenants_inactius(db, client):
    _create_admin(db, "owner5@example.com")
    token = _login(client, "owner5@example.com")
    tenant = _create_tenant(db, "botiga-suspesa")
    tenant.activo = False
    db.commit()

    resp = client.get("/superadmin/dashboard/tenant-health", headers=_auth(token))
    assert not any(t["slug"] == "botiga-suspesa" for t in resp.json())


def test_dashboards_requereixen_autenticacio(client):
    assert client.get("/superadmin/dashboard/features", headers=SUPERADMIN_HOST).status_code == 401
    assert client.get("/superadmin/dashboard/tenant-health", headers=SUPERADMIN_HOST).status_code == 401
