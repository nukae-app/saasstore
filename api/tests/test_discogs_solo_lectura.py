"""Modo "solo lectura" del módulo Discogs (migración por pasos, docs/
PLAN_CANAL_DISCOGS.md): con el interruptor activo, la app solo puede BAJAR
datos de Discogs; cualquier escritura queda bloqueada en un único punto."""

import contextlib
import io
import re
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import select

from app.models import CondicionItem, ConfiguracioBotiga, Item, Release, User
from app.services import discogs, discogs_sync
from app.services.discogs import DiscogsReadOnlyError, ReadOnlyToken, is_read_only
from app.services.discogs_sync import get_discogs_token_if_enabled, resolve_discogs_token, sync_stock_listing
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


def _config(db) -> ConfiguracioBotiga:
    return db.scalar(select(ConfiguracioBotiga))


@pytest.fixture
def secrets(monkeypatch):
    store = {"discogs_token_prod": "tok-prod", "discogs_token_dev": "tok-dev", "discogs_token": "tok-legacy"}
    monkeypatch.setattr(discogs_sync, "get_tenant_secrets", lambda tid: TenantSecrets(**store))
    return store


@pytest.fixture
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("no debe llamar a Discogs")

    monkeypatch.setattr(discogs_sync, "_client", boom)


# --- Capa HTTP: un único punto de bloqueo -----------------------------------------

def test_cliente_solo_lectura_bloquea_escrituras_sin_llegar_a_la_red():
    with discogs._client(ReadOnlyToken("t")) as c:
        for metodo in ("post", "put", "delete", "patch"):
            with pytest.raises(DiscogsReadOnlyError):
                getattr(c, metodo)("/marketplace/listings")


def test_hook_deja_pasar_lecturas():
    for metodo in ("GET", "HEAD"):
        discogs._block_writes(httpx.Request(metodo, "https://api.discogs.com/x"))  # no lanza


def test_token_normal_no_es_solo_lectura():
    assert not is_read_only("tok") and not is_read_only(None) and is_read_only(ReadOnlyToken("tok"))


# --- Resolución del token ---------------------------------------------------------

def test_resolve_token_segun_entorno(monkeypatch):
    s = TenantSecrets(discogs_token="legacy", discogs_token_dev="dev", discogs_token_prod="prod")
    monkeypatch.setattr(discogs_sync, "get_settings", lambda: SimpleNamespace(discogs_token_env="prod"))
    assert resolve_discogs_token(s) == "prod"
    monkeypatch.setattr(discogs_sync, "get_settings", lambda: SimpleNamespace(discogs_token_env="dev"))
    assert resolve_discogs_token(s) == "dev"


def test_resolve_token_cae_al_antiguo(monkeypatch):
    monkeypatch.setattr(discogs_sync, "get_settings", lambda: SimpleNamespace(discogs_token_env="prod"))
    assert resolve_discogs_token(TenantSecrets(discogs_token="legacy", discogs_token_dev="dev")) == "legacy"
    assert resolve_discogs_token(TenantSecrets()) is None


def test_token_efectivo_segun_interruptores(db, secrets):
    tid = _config(db).tenant_id
    assert get_discogs_token_if_enabled(db, tid) == "tok-prod"
    assert not is_read_only(get_discogs_token_if_enabled(db, tid))

    _config(db).discogs_solo_lectura = True
    db.commit()
    token = get_discogs_token_if_enabled(db, tid)
    assert token == "tok-prod" and is_read_only(token)

    _config(db).discogs_habilitat = False
    db.commit()
    assert get_discogs_token_if_enabled(db, tid) is None


# --- Flujos de escritura ----------------------------------------------------------

def _release_item(db, condition=CondicionItem.segona_ma, quantity=1, codi=None):
    r = Release(artista="A", title="T", formato="LP", discogs_release_id=123)
    db.add(r)
    db.flush()
    item = Item(release_id=r.id, price=Decimal("10.00"), condition=condition, quantity=quantity)
    db.add(item)
    db.flush()
    if codi:
        item.codi_discogs = codi
    db.commit()
    return r, item


def test_alta_de_item_en_solo_lectura_no_publica(db, client, secrets, no_network):
    _config(db).discogs_solo_lectura = True
    db.commit()
    headers = _admin(client, db)
    release, _ = _release_item(db)

    resp = client.post("/admin/items", json={"release_id": str(release.id), "price": "20.00"}, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["codi_discogs"] is None  # sin llamada a Discogs (no_network lo garantiza)


def test_endpoints_push_y_remove_devuelven_409_en_solo_lectura(db, client, secrets, no_network):
    _config(db).discogs_solo_lectura = True
    db.commit()
    headers = _admin(client, db)
    _, item = _release_item(db)
    _, listado = _release_item(db, codi=555)

    assert client.post(f"/admin/discogs/sync/items/{item.id}/push", headers=headers).status_code == 409
    assert client.delete(f"/admin/discogs/sync/items/{listado.id}/listing", headers=headers).status_code == 409


def test_sync_stock_listing_no_desvincula_el_listing_en_solo_lectura(db, secrets, no_network):
    _, item = _release_item(db, condition=CondicionItem.nou, quantity=0, codi=999)
    sync_stock_listing(db, item, ReadOnlyToken("tok"))
    assert item.codi_discogs == 999  # el listing sigue vivo en Discogs: no se pierde el vínculo


def test_escrituras_de_servicio_son_noop_en_solo_lectura(no_network):
    ro = ReadOnlyToken("tok")
    assert discogs_sync.push_item_to_discogs(ro, "i", 1, 10.0, None, None) is None
    assert discogs_sync.remove_item_from_discogs(ro, 5) is False
    assert discogs_sync.push_shipped_status(ro, "1-1", "T", "C") is False


# --- Interruptor y secretos --------------------------------------------------------

def test_interruptor_se_cambia_por_patch(db, client):
    headers = _admin(client, db)
    resp = client.patch("/admin/configuracio", json={"discogs_solo_lectura": True}, headers=headers)
    assert resp.status_code == 200 and resp.json()["discogs_solo_lectura"] is True
    db.expire_all()
    assert _config(db).discogs_solo_lectura is True
    resp = client.patch("/admin/configuracio", json={"discogs_solo_lectura": False}, headers=headers)
    assert resp.json()["discogs_solo_lectura"] is False


def _fake_secret_store(monkeypatch):
    store: dict = {}
    monkeypatch.setattr("app.routers.configuracio.get_tenant_secrets", lambda tid: TenantSecrets(**store))

    def fake_set(tid, **fields):
        store.update({k: v for k, v in fields.items() if v is not None})
        return TenantSecrets(**store)

    monkeypatch.setattr("app.routers.configuracio.set_tenant_secret", fake_set)
    monkeypatch.setattr("app.routers.configuracio.discogs.get_identity", lambda token: "la-botiga")
    return store


def test_primer_token_prod_activa_solo_lectura_automaticamente(db, client, monkeypatch):
    _fake_secret_store(monkeypatch)
    headers = _admin(client, db)
    assert _config(db).discogs_solo_lectura is False

    resp = client.post("/admin/secrets", json={"discogs_token_prod": "tok"}, headers=headers)
    assert resp.status_code == 200 and resp.json()["discogs_token_prod"] is True
    db.expire_all()
    assert _config(db).discogs_solo_lectura is True


def test_token_prod_respeta_una_decision_explicita_previa(db, client, monkeypatch):
    _fake_secret_store(monkeypatch)
    headers = _admin(client, db)
    client.patch("/admin/configuracio", json={"discogs_solo_lectura": False}, headers=headers)  # decisión explícita

    client.post("/admin/secrets", json={"discogs_token_prod": "tok"}, headers=headers)
    db.expire_all()
    assert _config(db).discogs_solo_lectura is False


def test_token_prod_no_fuerza_solo_lectura_si_la_adopcion_ya_esta_hecha(db, client, monkeypatch):
    from app.services.discogs_sync import marcar_adopcio_feta

    _fake_secret_store(monkeypatch)
    headers = _admin(client, db)
    marcar_adopcio_feta(db, {})
    db.commit()

    client.post("/admin/secrets", json={"discogs_token_prod": "tok"}, headers=headers)
    db.expire_all()
    assert _config(db).discogs_solo_lectura is False


def test_tokens_dev_y_prod_tambien_se_validan(db, client, monkeypatch):
    store = _fake_secret_store(monkeypatch)

    def bad(token):
        raise httpx.HTTPStatusError("401", request=httpx.Request("GET", "http://x"), response=httpx.Response(401))

    monkeypatch.setattr("app.routers.configuracio.discogs.get_identity", bad)
    headers = _admin(client, db)
    for campo in ("discogs_token_dev", "discogs_token_prod"):
        assert client.post("/admin/secrets", json={campo: "mal"}, headers=headers).status_code == 422
    assert store == {}
