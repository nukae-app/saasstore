"""Tests del CRUD admin de `Page` (ver models/storefront.py::Page,
routers/pages.py y docs/ARQUITECTURA_DISENY_FIGMA.md §3)."""

import contextlib
import io
import re

from sqlalchemy import select

from app.models import Pagina, Page, User


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


def test_create_page(db, client):
    admin = _admin_token(client, db)
    resp = client.post("/admin/pages", json={"slug": "sobre-nosaltres"}, headers=_auth(admin))
    assert resp.status_code == 201
    body = resp.json()
    assert body["slug"] == "sobre-nosaltres"
    assert body["draft_tree"] == {}
    assert body["published_tree"] is None


def test_create_page_slug_reservat(db, client):
    admin = _admin_token(client, db)
    resp = client.post("/admin/pages", json={"slug": "checkout"}, headers=_auth(admin))
    assert resp.status_code == 422


def test_create_page_slug_format_invalid(db, client):
    admin = _admin_token(client, db)
    resp = client.post("/admin/pages", json={"slug": "Sobre Nosaltres!"}, headers=_auth(admin))
    assert resp.status_code == 422


def test_create_page_slug_duplicat(db, client):
    admin = _admin_token(client, db)
    assert client.post("/admin/pages", json={"slug": "contacte"}, headers=_auth(admin)).status_code == 201
    resp = client.post("/admin/pages", json={"slug": "contacte"}, headers=_auth(admin))
    assert resp.status_code == 409


def test_create_page_colisio_amb_pagina_estatica(db, client):
    db.add(Pagina(slug="podcast", name="Podcast"))
    db.commit()
    admin = _admin_token(client, db)
    resp = client.post("/admin/pages", json={"slug": "podcast"}, headers=_auth(admin))
    assert resp.status_code == 409


def test_get_page(db, client):
    admin = _admin_token(client, db)
    client.post("/admin/pages", json={"slug": "agenda-especial"}, headers=_auth(admin))
    resp = client.get("/admin/pages/agenda-especial", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json()["slug"] == "agenda-especial"


def test_get_page_no_trobada(db, client):
    admin = _admin_token(client, db)
    resp = client.get("/admin/pages/no-existeix", headers=_auth(admin))
    assert resp.status_code == 404


def test_update_page_draft_tree(db, client):
    admin = _admin_token(client, db)
    client.post("/admin/pages", json={"slug": "landing"}, headers=_auth(admin))
    tree = {"id": "ROOT", "type": "Stack", "props": {}, "style": {}, "children": []}
    resp = client.patch("/admin/pages/landing", json={"draft_tree": tree}, headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json()["draft_tree"] == tree
    # persisteix de veritat, no només a la resposta
    resp2 = client.get("/admin/pages/landing", headers=_auth(admin))
    assert resp2.json()["draft_tree"] == tree


def test_delete_page(db, client):
    admin = _admin_token(client, db)
    client.post("/admin/pages", json={"slug": "temporal"}, headers=_auth(admin))
    assert client.delete("/admin/pages/temporal", headers=_auth(admin)).status_code == 204
    assert client.get("/admin/pages/temporal", headers=_auth(admin)).status_code == 404
    assert db.scalar(select(Page).where(Page.slug == "temporal")) is None


def test_pages_requereix_admin(client):
    resp = client.get("/admin/pages")
    assert resp.status_code in (401, 403)


def test_publish_page(db, client):
    admin = _admin_token(client, db)
    client.post("/admin/pages", json={"slug": "landing2"}, headers=_auth(admin))
    tree = {"id": "ROOT", "type": "Stack", "props": {}, "style": {}, "children": []}
    client.patch("/admin/pages/landing2", json={"draft_tree": tree}, headers=_auth(admin))
    resp = client.post("/admin/pages/landing2/publish", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json()["published_tree"] == tree


def test_create_page_requires_nodes_tipus_desconegut(db, client):
    admin = _admin_token(client, db)
    resp = client.post(
        "/admin/pages",
        json={"slug": "checkout-nou", "requires_nodes": ["qualsevol_cosa"]},
        headers=_auth(admin),
    )
    assert resp.status_code == 422


def test_publish_page_falten_nodes_obligatoris(db, client):
    admin = _admin_token(client, db)
    client.post(
        "/admin/pages",
        json={"slug": "checkout-protegit", "requires_nodes": ["checkout_form", "cart_summary"]},
        headers=_auth(admin),
    )
    tree = {"id": "ROOT", "type": "Stack", "props": {}, "style": {}, "children": []}
    client.patch("/admin/pages/checkout-protegit", json={"draft_tree": tree}, headers=_auth(admin))
    resp = client.post("/admin/pages/checkout-protegit/publish", headers=_auth(admin))
    assert resp.status_code == 422
    assert "checkout_form" in resp.json()["detail"]
    assert "cart_summary" in resp.json()["detail"]
    # no s'ha publicat res
    resp2 = client.get("/admin/pages/checkout-protegit", headers=_auth(admin))
    assert resp2.json()["published_tree"] is None


def test_publish_page_amb_nodes_obligatoris_presents(db, client):
    admin = _admin_token(client, db)
    client.post(
        "/admin/pages",
        json={"slug": "checkout-ok", "requires_nodes": ["checkout_form"]},
        headers=_auth(admin),
    )
    tree = {
        "id": "ROOT",
        "type": "Stack",
        "props": {},
        "style": {},
        "children": [{"id": "n1", "type": "checkout_form", "props": {}, "style": {}, "children": []}],
    }
    client.patch("/admin/pages/checkout-ok", json={"draft_tree": tree}, headers=_auth(admin))
    resp = client.post("/admin/pages/checkout-ok/publish", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json()["published_tree"] == tree


def test_public_page_no_publicada_404(db, client):
    admin = _admin_token(client, db)
    client.post("/admin/pages", json={"slug": "esborrany"}, headers=_auth(admin))
    resp = client.get("/config/public/pages/esborrany")
    assert resp.status_code == 404


def test_public_page_publicada(db, client):
    admin = _admin_token(client, db)
    client.post("/admin/pages", json={"slug": "publica"}, headers=_auth(admin))
    tree = {"id": "ROOT", "type": "Stack", "props": {}, "style": {}, "children": []}
    client.patch("/admin/pages/publica", json={"draft_tree": tree}, headers=_auth(admin))
    client.post("/admin/pages/publica/publish", headers=_auth(admin))
    resp = client.get("/config/public/pages/publica")
    assert resp.status_code == 200
    body = resp.json()
    assert body["published_tree"] == tree
    assert "draft_tree" not in body
