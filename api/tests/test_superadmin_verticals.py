"""CRUD de `Vertical` des del superadmin: abans només hi havia `GET
/superadmin/verticals` (llegint el seed manual) — donar d'alta un vertical
nou exigia una migració a mà. Aquest test cobreix create/update i el filtre
`include_inactive`."""

from app.models import PlatformAdmin, PlatformAdminRole, Vertical
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


def _vertical_payload(vertical_id: str = "merch") -> dict:
    return {"id": vertical_id, "name_ca": "Merxandatge", "name_es": "Merchandising", "name_en": "Merch"}


def test_support_no_pot_crear_vertical(db, client):
    _create_admin(db, "support@example.com", PlatformAdminRole.support)
    token = _login(client, "support@example.com")
    resp = client.post("/superadmin/verticals", json=_vertical_payload(), headers=_auth(token))
    assert resp.status_code == 403


def test_owner_crea_vertical_i_queda_auditat(db, client):
    admin = _create_admin(db, "owner@example.com", PlatformAdminRole.owner)
    token = _login(client, "owner@example.com")

    resp = client.post("/superadmin/verticals", json=_vertical_payload(), headers=_auth(token))
    assert resp.status_code == 201, resp.text
    assert resp.json() == {
        "id": "merch", "name_ca": "Merxandatge", "name_es": "Merchandising", "name_en": "Merch", "active": True,
        "catalog_provider": None, "product_archetype": None, "default_features": {},
    }

    list_resp = client.get("/superadmin/verticals", headers=_auth(token))
    assert any(v["id"] == "merch" for v in list_resp.json())


def test_crear_vertical_amb_catalog_provider_i_archetype_valids(db, client):
    admin = _create_admin(db, "owner2@example.com", PlatformAdminRole.owner)
    token = _login(client, "owner2@example.com")

    payload = {
        **_vertical_payload("books"),
        "catalog_provider": "discogs", "product_archetype": "media_catalog",
        "default_features": {"subscriptions": True},
    }
    resp = client.post("/superadmin/verticals", json=payload, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    assert resp.json()["catalog_provider"] == "discogs"
    assert resp.json()["product_archetype"] == "media_catalog"
    assert resp.json()["default_features"] == {"subscriptions": True}


def test_catalog_provider_no_implementat_es_rebutjat(db, client):
    admin = _create_admin(db, "owner3@example.com", PlatformAdminRole.owner)
    token = _login(client, "owner3@example.com")

    payload = {**_vertical_payload("wine"), "catalog_provider": "vivino"}
    resp = client.post("/superadmin/verticals", json=payload, headers=_auth(token))
    assert resp.status_code == 422


def test_product_archetype_desconegut_es_rebutjat(db, client):
    admin = _create_admin(db, "owner4@example.com", PlatformAdminRole.owner)
    token = _login(client, "owner4@example.com")

    payload = {**_vertical_payload("toys"), "product_archetype": "no_existeix"}
    resp = client.post("/superadmin/verticals", json=payload, headers=_auth(token))
    assert resp.status_code == 422


def test_default_features_amb_clau_desconeguda_es_rebutjat(db, client):
    admin = _create_admin(db, "owner6@example.com", PlatformAdminRole.owner)
    token = _login(client, "owner6@example.com")

    payload = {**_vertical_payload("craft_beer"), "default_features": {"instagram_ads": True}}
    resp = client.post("/superadmin/verticals", json=payload, headers=_auth(token))
    assert resp.status_code == 422


def test_update_vertical_amb_product_archetype_invalid_es_rebutjat(db, client):
    admin = _create_admin(db, "owner5@example.com", PlatformAdminRole.owner)
    token = _login(client, "owner5@example.com")
    client.post("/superadmin/verticals", json=_vertical_payload("cheese"), headers=_auth(token))

    resp = client.patch(
        "/superadmin/verticals/cheese", json={"product_archetype": "inventado"}, headers=_auth(token),
    )
    assert resp.status_code == 422

    log_resp = client.get("/superadmin/audit-log", headers=_auth(token))
    entries = log_resp.json()
    assert any(
        e["action"] == "vertical.create" and e["platform_admin_id"] == str(admin.id)
        for e in entries
    )


def test_id_invalid_es_rebutjat(db, client):
    _create_admin(db, "owner2@example.com", PlatformAdminRole.owner)
    token = _login(client, "owner2@example.com")
    resp = client.post(
        "/superadmin/verticals", json=_vertical_payload("Not Valid!"), headers=_auth(token),
    )
    assert resp.status_code == 422


def test_id_duplicat_es_rebutjat(db, client):
    _create_admin(db, "owner3@example.com", PlatformAdminRole.owner)
    token = _login(client, "owner3@example.com")
    client.post("/superadmin/verticals", json=_vertical_payload("dup"), headers=_auth(token))
    resp = client.post("/superadmin/verticals", json=_vertical_payload("dup"), headers=_auth(token))
    assert resp.status_code == 409


def test_desactivar_vertical_el_treu_del_llistat_per_defecte(db, client):
    admin = _create_admin(db, "owner4@example.com", PlatformAdminRole.owner)
    token = _login(client, "owner4@example.com")
    client.post("/superadmin/verticals", json=_vertical_payload("legacy"), headers=_auth(token))

    resp = client.patch(
        "/superadmin/verticals/legacy", json={"active": False}, headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["active"] is False

    default_list = client.get("/superadmin/verticals", headers=_auth(token)).json()
    assert not any(v["id"] == "legacy" for v in default_list)

    full_list = client.get(
        "/superadmin/verticals", params={"include_inactive": True}, headers=_auth(token),
    ).json()
    assert any(v["id"] == "legacy" for v in full_list)

    log_resp = client.get("/superadmin/audit-log", headers=_auth(token))
    entries = log_resp.json()
    assert any(
        e["action"] == "vertical.update" and e["platform_admin_id"] == str(admin.id)
        for e in entries
    )


def test_update_vertical_inexistent_dona_404(db, client):
    _create_admin(db, "owner5@example.com", PlatformAdminRole.owner)
    token = _login(client, "owner5@example.com")
    resp = client.patch(
        "/superadmin/verticals/no-existeix", json={"active": False}, headers=_auth(token),
    )
    assert resp.status_code == 404
