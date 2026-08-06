"""Flujo de alta con contraseña: el compte queda inactiu fins que es confirma
l'email (a diferència del magic link, on la possessió de l'email ja queda
provada en el propi flux)."""

import contextlib
import io
import re

EMAIL = "nova@example.com"
PASSWORD = "contrasenya123"


def _register(client, email=EMAIL, password=PASSWORD):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        resp = client.post("/auth/register", json={"email": email, "password": password})
    return resp, buf.getvalue()


def _extract_token(printed: str) -> str:
    return re.search(r"token=([\w\-]+)", printed).group(1)


def test_register_no_crea_sessio_ni_verifica_immediatament(client, db):
    resp, printed = _register(client)
    assert resp.status_code == 202
    assert "refresh_token" not in resp.cookies
    assert "token=" in printed  # s'ha enviat l'enllaç de verificació


def test_login_bloquejat_fins_confirmar_email(client, db):
    _register(client)
    resp = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert resp.status_code == 403
    assert "email" in resp.json()["detail"].lower()


def test_verify_email_activa_el_compte_i_dona_sessio(client, db):
    _, printed = _register(client)
    token = _extract_token(printed)

    resp = client.post(f"/auth/verify-email?token={token}")
    assert resp.status_code == 200
    assert "access_token" in resp.json()

    # Ara sí que pot fer login normal
    resp = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert resp.status_code == 200


def test_verify_email_token_no_es_reutilitzable(client, db):
    _, printed = _register(client)
    token = _extract_token(printed)

    assert client.post(f"/auth/verify-email?token={token}").status_code == 200
    assert client.post(f"/auth/verify-email?token={token}").status_code == 400


def test_verify_email_token_invalid(client, db):
    resp = client.post("/auth/verify-email?token=no-existeix")
    assert resp.status_code == 400


def test_magic_link_token_no_serveix_per_verificar_email(client, db):
    """Els tokens de cada flux estan separats per `purpose`: un token de magic
    link no ha de poder canjear-se com a verificació d'email ni viceversa."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert client.post("/auth/magic-link", json={"email": "algu@example.com"}).status_code == 202
    magic_token = _extract_token(buf.getvalue())

    assert client.post(f"/auth/verify-email?token={magic_token}").status_code == 400

    _, printed = _register(client, email="altra@example.com")
    verify_token = _extract_token(printed)
    assert client.post(f"/auth/magic-link/verify?token={verify_token}").status_code == 400


def test_resend_verification_reenvia_token(client, db):
    _register(client)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        resp = client.post("/auth/resend-verification", json={"email": EMAIL})
    assert resp.status_code == 202
    token = _extract_token(buf.getvalue())
    assert client.post(f"/auth/verify-email?token={token}").status_code == 200


def test_resend_verification_no_filtra_existencia_del_compte(client, db):
    resp = client.post("/auth/resend-verification", json={"email": "no-existeix@example.com"})
    assert resp.status_code == 202


def test_register_email_duplicat(client, db):
    _register(client)
    resp, _ = _register(client)
    assert resp.status_code == 409
