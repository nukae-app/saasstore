"""Tests de l'exportació experimental a Holded (Fase 5) — mockejant
`push_ledger_entry` (mai es truca Holded de veritat als tests)."""

from sqlalchemy import select

from app.models import User
from app.tenant_secrets import TenantSecrets


def _admin_token(client, db) -> str:
    import contextlib
    import io
    import re

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert client.post("/auth/magic-link", json={"email": "admin@example.com"}).status_code == 202
    token = re.search(r"token=([\w\-]+)", buf.getvalue()).group(1)
    resp = client.post(f"/auth/magic-link/verify?token={token}")
    user = db.scalar(select(User).where(User.email == "admin@example.com"))
    user.role = "admin"
    db.commit()
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _crear_despesa(client, token):
    resp = client.post(
        "/admin/despeses",
        json={
            "invoice_date": "2026-07-05", "supplier_name": "Test", "category": "subministraments",
            "concept": "Test", "taxable_base": "100.00", "vat_pct": "21.00",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201


def test_export_holded_sense_mapeig_marca_error(client, db):
    token = _admin_token(client, db)
    _crear_despesa(client, token)

    resp = client.post(
        "/admin/holded/export",
        json={"year": 2026, "mes_desde": 7, "mes_fins": 7, "account_mapping": {"628": "hld_1"}},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["resultats"]) == 1
    assert body["resultats"][0]["status"] == "error"
    assert "472" in body["resultats"][0]["detail"] or "400" in body["resultats"][0]["detail"]


def test_export_holded_amb_mapeig_complet_crida_holded(client, db, monkeypatch):
    token = _admin_token(client, db)
    _crear_despesa(client, token)

    crides = []

    def fake_push(api_key, *, date_iso, description, lines):
        assert api_key == "test-holded-key"
        crides.append((date_iso, description, lines))
        return {"id": "hld_entry_1"}

    import app.routers.comptabilitat.holded as holded_router
    monkeypatch.setattr(holded_router, "push_ledger_entry", fake_push)

    resp = client.post(
        "/admin/holded/export",
        json={
            "year": 2026, "mes_desde": 7, "mes_fins": 7,
            "account_mapping": {"628": "hld_628", "472": "hld_472", "400": "hld_400"},
        },
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["resultats"][0]["status"] == "ok"
    assert len(crides) == 1
    assert len(crides[0][2]) == 3  # 3 apunts (628, 472, 400)


def test_export_holded_sense_api_key_dona_422(client, db, monkeypatch):
    token = _admin_token(client, db)
    _crear_despesa(client, token)

    import app.routers.comptabilitat.holded as holded_router
    monkeypatch.setattr(holded_router, "get_tenant_secrets", lambda tenant_id: TenantSecrets())

    resp = client.post(
        "/admin/holded/export",
        json={"year": 2026, "mes_desde": 7, "mes_fins": 7, "account_mapping": {}},
        headers=_auth(token),
    )
    assert resp.status_code == 422


def test_export_holded_error_de_holded_es_reporta_no_es_propaga(client, db, monkeypatch):
    token = _admin_token(client, db)
    _crear_despesa(client, token)

    import app.routers.comptabilitat.holded as holded_router
    from app.services.holded_export import HoldedExportError

    def fake_push_fail(*args, **kwargs):
        raise HoldedExportError("Holded ha respost 401: unauthorized")

    monkeypatch.setattr(holded_router, "push_ledger_entry", fake_push_fail)

    resp = client.post(
        "/admin/holded/export",
        json={
            "year": 2026, "mes_desde": 7, "mes_fins": 7,
            "account_mapping": {"628": "hld_628", "472": "hld_472", "400": "hld_400"},
        },
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["resultats"][0]["status"] == "error"
    assert "401" in body["resultats"][0]["detail"]
