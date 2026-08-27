"""Gestió d'altres `PlatformAdmin` des del panell (abans només es podien
crear per `scripts/create_superadmin.py`, sense cap manera de convidar o
desactivar un operador des de la UI). Cobreix create/update i la guarda que
impedeix deixar la plataforma sense cap owner actiu."""

from app.models import PlatformAdmin, PlatformAdminRole
from app.services.security import hash_password

SUPERADMIN_HOST = {"Host": "superadmin.localhost"}


def _create_admin(db, email: str, role: PlatformAdminRole, activo: bool = True) -> PlatformAdmin:
    admin = PlatformAdmin(email=email, password_hash=hash_password("s3cret123"), role=role, activo=activo)
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


def test_support_no_pot_crear_admin(db, client):
    _create_admin(db, "support@example.com", PlatformAdminRole.support)
    token = _login(client, "support@example.com")
    resp = client.post(
        "/superadmin/admins",
        json={"email": "nou@example.com", "password": "s3cret123", "role": "support"},
        headers=_auth(token),
    )
    assert resp.status_code == 403


def test_support_pot_llistar_admins(db, client):
    _create_admin(db, "support2@example.com", PlatformAdminRole.support)
    token = _login(client, "support2@example.com")
    resp = client.get("/superadmin/admins", headers=_auth(token))
    assert resp.status_code == 200


def test_owner_crea_admin_i_queda_auditat(db, client):
    admin = _create_admin(db, "owner@example.com", PlatformAdminRole.owner)
    token = _login(client, "owner@example.com")

    resp = client.post(
        "/superadmin/admins",
        json={"email": "Nou@Example.com", "password": "s3cret123", "nombre": "Nou Operador", "role": "support"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email"] == "nou@example.com"  # normalitzat a minúscules
    assert body["role"] == "support"
    assert body["activo"] is True

    log_resp = client.get("/superadmin/audit-log", headers=_auth(token))
    entries = log_resp.json()
    assert any(
        e["action"] == "admin.create" and e["platform_admin_id"] == str(admin.id)
        for e in entries
    )


def test_contrasenya_curta_es_rebutjada(db, client):
    _create_admin(db, "owner2@example.com", PlatformAdminRole.owner)
    token = _login(client, "owner2@example.com")
    resp = client.post(
        "/superadmin/admins",
        json={"email": "curta@example.com", "password": "1234567", "role": "support"},
        headers=_auth(token),
    )
    assert resp.status_code == 422


def test_email_duplicat_es_rebutjat(db, client):
    _create_admin(db, "owner3@example.com", PlatformAdminRole.owner)
    token = _login(client, "owner3@example.com")
    resp = client.post(
        "/superadmin/admins",
        json={"email": "owner3@example.com", "password": "s3cret123", "role": "support"},
        headers=_auth(token),
    )
    assert resp.status_code == 409


def test_desactivar_un_operador_amb_altres_owners_actius(db, client):
    _create_admin(db, "owner4@example.com", PlatformAdminRole.owner)
    other = _create_admin(db, "owner5@example.com", PlatformAdminRole.owner)
    token = _login(client, "owner4@example.com")

    resp = client.patch(
        f"/superadmin/admins/{other.id}", json={"activo": False}, headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["activo"] is False


def test_no_es_pot_desactivar_lunic_owner_actiu(db, client):
    solo = _create_admin(db, "solo@example.com", PlatformAdminRole.owner)
    token = _login(client, "solo@example.com")

    resp = client.patch(
        f"/superadmin/admins/{solo.id}", json={"activo": False}, headers=_auth(token),
    )
    assert resp.status_code == 409
    # No ha canviat res: encara pot fer servir el seu propi token.
    me = client.get("/superadmin/me", headers=_auth(token))
    assert me.status_code == 200
    assert me.json()["activo"] is True


def test_no_es_pot_degradar_lunic_owner_actiu(db, client):
    solo = _create_admin(db, "solo2@example.com", PlatformAdminRole.owner)
    token = _login(client, "solo2@example.com")

    resp = client.patch(
        f"/superadmin/admins/{solo.id}", json={"role": "support"}, headers=_auth(token),
    )
    assert resp.status_code == 409


def test_degradar_ja_no_es_un_problema_si_hi_ha_un_altre_owner(db, client):
    solo = _create_admin(db, "solo3@example.com", PlatformAdminRole.owner)
    _create_admin(db, "backup@example.com", PlatformAdminRole.owner)
    token = _login(client, "solo3@example.com")

    resp = client.patch(
        f"/superadmin/admins/{solo.id}", json={"role": "support"}, headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "support"


def test_operador_inexistent_dona_404(db, client):
    _create_admin(db, "owner6@example.com", PlatformAdminRole.owner)
    token = _login(client, "owner6@example.com")
    resp = client.patch(
        "/superadmin/admins/00000000-0000-0000-0000-000000000000",
        json={"activo": False}, headers=_auth(token),
    )
    assert resp.status_code == 404
