"""Tests de los endpoints nativos (`/auth/mobile/*`, ver
docs/ARQUITECTURA_APPS_NATIVAS.md §3.2 y §7bis-2) y del fallback de
resolución de tenant por `X-Tenant-Slug` (§3.1, `app/database.py::get_db`).

`/auth/mobile/magic-link` y su `/verify` resuelven el tenant por el email
(busca en qué tenant(s) es admin) o por el propio token (único a nivel
global) — el cliente nunca necesita saber ni mandar el slug de la tienda
para entrar, solo para las llamadas posteriores (refresh/logout/negocio),
donde ya lo conoce por la respuesta del login."""

import contextlib
import io
import re

from sqlalchemy import select

from app.models import Tenant, User
from app.services.security import hash_password


def _make_admin(db, email: str, tenant_id=None, password: str | None = None) -> User:
    kwargs = {"tenant_id": tenant_id} if tenant_id else {}
    if password:
        kwargs["password_hash"] = hash_password(password)
    user = User(email=email, role="admin", **kwargs)
    db.add(user)
    db.commit()
    return user


def _request_magic_link_tokens(client, email: str) -> list[str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        resp = client.post("/auth/mobile/magic-link", json={"email": email, "language": "ca"})
    assert resp.status_code == 202
    assert resp.json()["detail"] == "Si el email es válido, recibirás un enlace de acceso"
    return re.findall(r"token=([\w\-]+)", buf.getvalue())


def _mobile_login(client, db, email: str) -> dict:
    """Flujo completo y realista: crea el admin, pide el enlace de verdad
    (sin slug), lo verifica. Igual que haría la app."""
    _make_admin(db, email)
    tokens = _request_magic_link_tokens(client, email)
    assert len(tokens) == 1
    resp = client.post(f"/auth/mobile/magic-link/verify?token={tokens[0]}")
    assert resp.status_code == 200
    return resp.json()


def test_login_completo_sin_slug_devuelve_tenant_slug(client, db):
    body = _mobile_login(client, db, "admin-movil@example.com")
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["tenant_slug"] == "test-tenant"
    assert "ulr_refresh" not in client.cookies


def test_email_sin_ninguna_cuenta_admin_responde_generico(client):
    """Anti-enumeración: mismo 202 y mismo texto que si existiera — no debe
    distinguirse desde fuera si el email tiene cuenta admin en algún sitio."""
    tokens = _request_magic_link_tokens(client, "nadie-conocido@example.com")
    assert tokens == []


def test_cuenta_cliente_no_admin_no_recibe_enlace(client, db):
    """Un email con cuenta de CLIENTE (no admin) en la tienda no debe recibir
    ningún enlace de la app de admin — el filtro es por rol, no por tener
    cuenta o no."""
    db.add(User(email="cliente-normal@example.com", role="cliente"))
    db.commit()
    tokens = _request_magic_link_tokens(client, "cliente-normal@example.com")
    assert tokens == []


def test_admin_en_dos_tenants_recibe_un_enlace_por_cada_uno(client, db):
    tenant_b = Tenant(slug="tenant-b", domain="b.testserver", nombre="Tenant B")
    db.add(tenant_b)
    db.commit()
    email = "admin-multi@example.com"
    _make_admin(db, email)  # en el tenant por defecto de `db` (test-tenant)
    _make_admin(db, email, tenant_id=tenant_b.id)

    tokens = _request_magic_link_tokens(client, email)
    assert len(tokens) == 2

    slugs = set()
    for token in tokens:
        resp = client.post(f"/auth/mobile/magic-link/verify?token={token}")
        assert resp.status_code == 200
        slugs.add(resp.json()["tenant_slug"])
    assert slugs == {"test-tenant", "tenant-b"}


def test_verify_rechaza_si_ya_no_es_admin_al_canjearlo(client, db):
    email = "degradado@example.com"
    user = _make_admin(db, email)
    tokens = _request_magic_link_tokens(client, email)
    assert len(tokens) == 1

    user.role = "cliente"
    db.commit()

    resp = client.post(f"/auth/mobile/magic-link/verify?token={tokens[0]}")
    assert resp.status_code == 403


def test_verify_token_invalido_da_400(client):
    resp = client.post("/auth/mobile/magic-link/verify?token=no-existe")
    assert resp.status_code == 400


def test_mobile_refresh_rota_el_token(client, db):
    session = _mobile_login(client, db, "rota@example.com")
    resp = client.post("/auth/mobile/refresh", json={"refresh_token": session["refresh_token"]})
    assert resp.status_code == 200
    new_session = resp.json()
    assert new_session["refresh_token"] != session["refresh_token"]
    assert new_session["access_token"]


def test_mobile_refresh_token_ya_usado_falla(client, db):
    session = _mobile_login(client, db, "usado@example.com")
    first = client.post("/auth/mobile/refresh", json={"refresh_token": session["refresh_token"]})
    assert first.status_code == 200
    second = client.post("/auth/mobile/refresh", json={"refresh_token": session["refresh_token"]})
    assert second.status_code == 401


def test_reuso_de_refresh_token_revoca_toda_la_sesion_del_usuario(client, db):
    """Detección de robo: presentar un token ya rotado no solo se rechaza a
    sí mismo — revoca TODOS los refresh tokens activos del usuario, incluido
    el que sí era legítimo (el que sustituyó al reutilizado)."""
    session = _mobile_login(client, db, "robado@example.com")
    rotated = client.post("/auth/mobile/refresh", json={"refresh_token": session["refresh_token"]})
    assert rotated.status_code == 200
    legit_new_token = rotated.json()["refresh_token"]

    replay = client.post("/auth/mobile/refresh", json={"refresh_token": session["refresh_token"]})
    assert replay.status_code == 401

    legit_attempt = client.post("/auth/mobile/refresh", json={"refresh_token": legit_new_token})
    assert legit_attempt.status_code == 401


def test_mobile_logout_revoca_el_refresh_token(client, db):
    session = _mobile_login(client, db, "logout@example.com")
    resp = client.post("/auth/mobile/logout", json={"refresh_token": session["refresh_token"]})
    assert resp.status_code == 204
    again = client.post("/auth/mobile/refresh", json={"refresh_token": session["refresh_token"]})
    assert again.status_code == 401


def test_login_password_correcto_devuelve_tenant_slug(client, db):
    _make_admin(db, "conpass@example.com", password="Correcta123")
    resp = client.post("/auth/mobile/login", json={"email": "conpass@example.com", "password": "Correcta123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "signed_in"
    assert body["tenant_slug"] == "test-tenant"
    assert body["access_token"] and body["refresh_token"]


def test_login_password_incorrecta_da_401(client, db):
    _make_admin(db, "conpass2@example.com", password="Correcta123")
    resp = client.post("/auth/mobile/login", json={"email": "conpass2@example.com", "password": "Incorrecta"})
    assert resp.status_code == 401


def test_login_usuario_solo_magic_link_sin_password_da_401(client, db):
    _make_admin(db, "solomagic@example.com")  # sin password_hash
    resp = client.post("/auth/mobile/login", json={"email": "solomagic@example.com", "password": "loquesea"})
    assert resp.status_code == 401


def test_login_password_ambigua_en_dos_tenants_pide_elegir(client, db):
    tenant_b = Tenant(slug="tenant-b", domain="b.testserver", nombre="Tenant B")
    db.add(tenant_b)
    db.commit()
    email = "ambiguo@example.com"
    _make_admin(db, email, password="MismaClau123")
    _make_admin(db, email, tenant_id=tenant_b.id, password="MismaClau123")

    resp = client.post("/auth/mobile/login", json={"email": email, "password": "MismaClau123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "choose_tenant"
    assert body["access_token"] is None
    slugs = {t["slug"] for t in body["tenants"]}
    assert slugs == {"test-tenant", "tenant-b"}

    resp2 = client.post(
        "/auth/mobile/login",
        json={"email": email, "password": "MismaClau123", "tenant_slug": "tenant-b"},
    )
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["status"] == "signed_in"
    assert body2["tenant_slug"] == "tenant-b"


def test_login_password_distinta_por_tenant_no_es_ambiguo(client, db):
    """Mismo email, admin en dos tenants, pero CADA tenant con su propia
    contraseña: entrar con la de un tenant no debe ni mostrar el otro como
    opción — cada `User.password_hash` es de su propia fila."""
    tenant_b = Tenant(slug="tenant-b", domain="b.testserver", nombre="Tenant B")
    db.add(tenant_b)
    db.commit()
    email = "distinta@example.com"
    _make_admin(db, email, password="ClauA123")
    _make_admin(db, email, tenant_id=tenant_b.id, password="ClauB123")

    resp = client.post("/auth/mobile/login", json={"email": email, "password": "ClauA123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "signed_in"
    assert body["tenant_slug"] == "test-tenant"


def test_resolucion_de_tenant_por_x_tenant_slug_sin_host_valido(client):
    """Un cliente que no llega con un Host resoluble (como pegaría una app
    nativa: siempre al mismo host de API) debe poder identificar su tenant
    vía `X-Tenant-Slug` — ver `app/tenancy.py::resolve_tenant_by_slug`.
    Esto lo siguen necesitando las llamadas de negocio (p. ej. `/admin/*`),
    a diferencia de `/auth/mobile/magic-link*` (ver tests de arriba)."""
    resp = client.get(
        "/config/public",
        headers={"host": "no-existe.example", "x-tenant-slug": "test-tenant"},
    )
    assert resp.status_code == 200


def test_x_tenant_slug_invalido_sigue_dando_404(client):
    resp = client.get(
        "/config/public",
        headers={"host": "no-existe.example", "x-tenant-slug": "no-existe-tampoco"},
    )
    assert resp.status_code == 404
