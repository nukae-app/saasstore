"""Tests de la Fase 5 (ver plan /Users/paumartinez/.claude/plans/swift-gathering-bengio.md):
los secretos de tenant se editan desde el propio admin del tenant
(`/admin/secrets`), no desde el superadmin — que conserva solo lectura de
estado."""

import contextlib
import io
import re

from sqlalchemy import select

from app.models import User
from app.tenant_secrets import TenantSecrets


def _login(client, email: str) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert client.post("/auth/magic-link", json={"email": email}).status_code == 202
    token = re.search(r"token=([\w\-]+)", buf.getvalue()).group(1)
    resp = client.post(f"/auth/magic-link/verify?token={token}")
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _admin_token(client, db) -> str:
    access = _login(client, "admin@example.com")
    user = db.scalar(select(User).where(User.email == "admin@example.com"))
    user.role = "admin"
    db.commit()
    return access


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _fake_secrets_store(monkeypatch):
    """Sustituye get/set_tenant_secret en routers.configuracio por un
    almacén en memoria — los tests no tienen Redis/AWS reales (eso se
    prueba aparte contra LocalStack)."""
    store: dict = {}

    def fake_get(tenant_id):
        return TenantSecrets(**store)

    def fake_set(tenant_id, **fields):
        store.update({k: v for k, v in fields.items() if v is not None})
        return TenantSecrets(**store)

    monkeypatch.setattr("app.routers.configuracio.get_tenant_secrets", fake_get)
    monkeypatch.setattr("app.routers.configuracio.set_tenant_secret", fake_set)
    return store


def test_admin_secrets_round_trip(db, client, monkeypatch):
    _fake_secrets_store(monkeypatch)
    admin = _admin_token(client, db)

    resp = client.get("/admin/secrets", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json() == {
        "redsys_merchant_code": False, "redsys_terminal": False, "redsys_secret_key": False,
        "discogs_token": False, "spotify_client_id": False, "spotify_client_secret": False,
    }

    resp = client.post("/admin/secrets", json={"discogs_token": "fake-token-123"}, headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json()["discogs_token"] is True
    assert resp.json()["redsys_merchant_code"] is False  # no tocado, sigue sin configurar

    # El valor en sí nunca se devuelve, ni siquiera justo después de guardarlo.
    assert "fake-token-123" not in resp.text

    resp = client.get("/admin/secrets", headers=_auth(admin))
    assert resp.json()["discogs_token"] is True


def test_admin_secrets_requiere_admin(client):
    resp = client.get("/admin/secrets")
    assert resp.status_code in (401, 403)


def test_admin_secrets_payload_vacio_falla(db, client, monkeypatch):
    _fake_secrets_store(monkeypatch)
    admin = _admin_token(client, db)
    resp = client.post("/admin/secrets", json={}, headers=_auth(admin))
    assert resp.status_code == 422


def test_superadmin_ya_no_puede_escribir_secretos(client):
    """`POST /superadmin/tenants/{id}/secrets` se eliminó en la Fase 5 —
    el operador solo conserva el GET de solo lectura. La petición nunca
    llega a comprobar el host/la autenticación: la ruta en sí ya no existe,
    así que FastAPI responde 405 (method not allowed) antes que nada."""
    resp = client.post(
        "/superadmin/tenants/00000000-0000-0000-0000-000000000001/secrets",
        json={"discogs_token": "x"},
        headers={"Host": "superadmin.localhost"},
    )
    assert resp.status_code == 405
