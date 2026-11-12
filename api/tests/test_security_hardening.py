"""Endurecimiento de seguridad (docs/PLAN_SEGURETAT_COMPLIMENT.md, Fase 2)."""

import logging

import pytest

from app import config


def test_secretos_por_defecto_abortan_en_produccion(monkeypatch):
    monkeypatch.setattr(config.get_settings(), "redsys_environment", "production")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        config.assert_production_secrets()


def test_secretos_fuertes_pasan_en_produccion(monkeypatch):
    s = config.get_settings()
    monkeypatch.setattr(s, "redsys_environment", "production")
    monkeypatch.setattr(s, "secret_key", "a" * 40)
    monkeypatch.setattr(config.get_superadmin_settings(), "superadmin_secret_key", "b" * 40)
    config.assert_production_secrets()


def test_secretos_por_defecto_permitidos_fuera_de_produccion(monkeypatch):
    monkeypatch.setattr(config.get_settings(), "redsys_environment", "test")
    config.assert_production_secrets()


def test_csp_report_se_registra(client, caplog):
    with caplog.at_level(logging.WARNING):
        resp = client.post("/csp-report", json={"csp-report": {"violated-directive": "img-src"}})
    assert resp.status_code == 204
    assert any("csp-violation" in r.message for r in caplog.records)


def test_csp_report_basura_no_peta(client):
    resp = client.post("/csp-report", content=b"no es json")
    assert resp.status_code == 204


def _png_bytes() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (2, 2)).save(buf, format="PNG")
    return buf.getvalue()


def test_validate_image_acepta_png_real():
    from app.services.uploads import validate_image_bytes

    validate_image_bytes(_png_bytes(), ".png", (".png", ".jpg"))


def test_validate_image_rechaza_html_renombrado():
    from fastapi import HTTPException

    from app.services.uploads import validate_image_bytes

    with pytest.raises(HTTPException) as exc:
        validate_image_bytes(b"<html><script>alert(1)</script></html>", ".png", (".png",))
    assert exc.value.status_code == 422


def test_validate_image_rechaza_extension_que_no_coincide_con_el_formato():
    from fastapi import HTTPException

    from app.services.uploads import validate_image_bytes

    with pytest.raises(HTTPException):
        validate_image_bytes(_png_bytes(), ".jpg", (".png", ".jpg"))


def test_validate_image_rechaza_demasiado_grande():
    from fastapi import HTTPException

    from app.services.uploads import MAX_IMAGE_BYTES, validate_image_bytes

    with pytest.raises(HTTPException):
        validate_image_bytes(b"0" * (MAX_IMAGE_BYTES + 1), ".png", (".png",))


# --- admin_users: rol y último administrador -----------------------------------------------

def _admin_login(client, db, email="admin@example.com"):
    import contextlib
    import io
    import re

    from sqlalchemy import select

    from app.models import User

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert client.post("/auth/magic-link", json={"email": email}).status_code == 202
    token = re.search(r"token=([\w\-]+)", buf.getvalue()).group(1)
    resp = client.post(f"/auth/magic-link/verify?token={token}")
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    me = db.scalar(select(User).where(User.email == email))
    me.role = "admin"
    db.commit()
    return headers, me


def test_no_es_pot_degradar_ni_desactivar_l_ultim_admin(client, db):
    headers, me = _admin_login(client, db)
    r = client.patch(f"/admin/users/{me.id}", json={"role": "cliente"}, headers=headers)
    assert r.status_code == 409
    r = client.patch(f"/admin/users/{me.id}", json={"active": False}, headers=headers)
    assert r.status_code == 409


def test_rol_invalid_es_rebutjat(client, db):
    headers, me = _admin_login(client, db)
    assert client.patch(f"/admin/users/{me.id}", json={"role": "superuser"}, headers=headers).status_code == 422
    r = client.post("/admin/users", json={"email": "nou@example.com", "role": "root"}, headers=headers)
    assert r.status_code == 422


def test_admin_pot_degradar_si_n_hi_ha_un_altre(client, db):
    from app.models import User

    headers, me = _admin_login(client, db)
    altre = User(email="segon@example.com", role="admin", active=True)
    db.add(altre)
    db.commit()
    assert client.patch(f"/admin/users/{me.id}", json={"role": "cliente"}, headers=headers).status_code == 200


def test_admin_set_password_rebutja_mes_de_72_bytes(client, db):
    headers, me = _admin_login(client, db)
    r = client.post(f"/admin/users/{me.id}/set-password", json={"password": "a" * 73}, headers=headers)
    assert r.status_code == 422


def test_contrasenya_comuna_es_rebutjada_al_registre(client):
    r = client.post("/auth/register", json={"email": "x@example.com", "password": "password123"})
    assert r.status_code == 422
    ok = client.post("/auth/register", json={"email": "x@example.com", "password": "Vinil-Poblenou-77"})
    assert ok.status_code == 202
