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
