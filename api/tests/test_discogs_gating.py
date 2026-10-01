"""El interruptor `discogs_habilitat` debe respetarse en TODOS los flujos que
escriben en Discogs (alta/borrado de items, borrado masivo), no solo en las
rutas `/admin/discogs/*`. Ver docs/PLAN_CANAL_DISCOGS.md, fase 0."""

import contextlib
import io
import re
from decimal import Decimal

from sqlalchemy import select

from app.models import ConfiguracioBotiga, Item, Release, User
from app.services.channel_settings import get_settings
from app.tenant_secrets import TenantSecrets


def _login(client, email: str) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert client.post("/auth/magic-link", json={"email": email}).status_code == 202
    token = re.search(r"token=([\w\-]+)", buf.getvalue()).group(1)
    resp = client.post(f"/auth/magic-link/verify?token={token}")
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _admin(client, db) -> dict:
    access = _login(client, "admin@example.com")
    user = db.scalar(select(User).where(User.email == "admin@example.com"))
    user.role = "admin"
    db.commit()
    return {"Authorization": f"Bearer {access}"}


def _setup(db, monkeypatch, habilitat: bool):
    monkeypatch.setattr(
        "app.services.discogs_sync.get_tenant_secrets", lambda tid: TenantSecrets(discogs_token="tok")
    )
    config = db.scalar(select(ConfiguracioBotiga))
    config.discogs_habilitat = habilitat
    get_settings(db).publicacion_auto = True  # estos tests prueban el interruptor, no la publicación manual
    db.commit()
    calls = {"push": [], "remove": []}

    def fake_push(token, **kw):
        calls["push"].append(token)
        return 999 if token else None  # como el real: sin token no hace nada

    def fake_remove(token, codi, **kw):
        calls["remove"].append(token)
        return True

    monkeypatch.setattr("app.routers.admin.items.push_item_to_discogs", fake_push)
    monkeypatch.setattr("app.routers.admin.items.remove_item_from_discogs", fake_remove)
    release = Release(artista="A", title="T", formato="LP", discogs_release_id=123)
    db.add(release)
    db.commit()
    return release, calls


def test_alta_item_no_publica_en_discogs_si_interruptor_apagado(db, client, monkeypatch):
    release, calls = _setup(db, monkeypatch, habilitat=False)
    headers = _admin(client, db)

    resp = client.post("/admin/items", json={"release_id": str(release.id), "price": "20.00"}, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["codi_discogs"] is None
    # el helper devuelve token=None -> push_item_to_discogs recibe None (no-op real)
    assert calls["push"] == [None]


def test_alta_item_publica_en_discogs_si_interruptor_encendido(db, client, monkeypatch):
    release, calls = _setup(db, monkeypatch, habilitat=True)
    headers = _admin(client, db)

    resp = client.post("/admin/items", json={"release_id": str(release.id), "price": "20.00"}, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["codi_discogs"] == 999
    assert calls["push"] == ["tok"]


def test_borrar_item_no_llama_a_discogs_con_token_si_interruptor_apagado(db, client, monkeypatch):
    release, calls = _setup(db, monkeypatch, habilitat=False)
    headers = _admin(client, db)
    item = Item(release_id=release.id, price=Decimal("10.00"))
    db.add(item)
    db.flush()
    item.codi_discogs = 555
    db.commit()

    resp = client.delete(f"/admin/items/{item.id}", headers=headers)
    assert resp.status_code == 204
    assert calls["remove"] == [None]


def test_alta_item_no_publica_por_defecto_porque_la_publicacion_es_manual(db, client, monkeypatch):
    release, calls = _setup(db, monkeypatch, habilitat=True)
    get_settings(db).publicacion_auto = False
    db.commit()
    headers = _admin(client, db)

    resp = client.post("/admin/items", json={"release_id": str(release.id), "price": "20.00"}, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["codi_discogs"] is None and calls["push"] == []  # queda "pendent" en el centro de control


def test_reponer_stock_nou_tampoco_publica_en_manual(db, monkeypatch):
    from app.models import CondicionItem
    from app.services.discogs_sync import sync_stock_listing

    release, calls = _setup(db, monkeypatch, habilitat=True)
    monkeypatch.setattr(
        "app.services.discogs_sync.push_item_to_discogs",
        lambda token, **kw: calls["push"].append(token) or 999,
    )
    get_settings(db).publicacion_auto = False
    item = Item(release_id=release.id, price=Decimal("10.00"), condition=CondicionItem.nou, quantity=2)
    db.add(item)
    db.commit()
    sync_stock_listing(db, item, "tok")
    assert calls["push"] == [] and item.codi_discogs is None

    get_settings(db).publicacion_auto = True
    sync_stock_listing(db, item, "tok")
    assert calls["push"] == ["tok"] and item.codi_discogs == 999
