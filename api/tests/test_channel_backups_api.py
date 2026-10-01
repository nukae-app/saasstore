"""Endpoints de copias (Configuració › Còpies de seguretat), copia de Discogs y copias automáticas."""

import contextlib
import gzip
import io
import json
import re
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from app.models import ChannelBackup, CondicionItem, Item, ItemStatus, Release, User
from app.services import catalog_backup as cb
from app.services import discogs, discogs_backup, discogs_inventory_sync as svc, discogs_jobs as jobs, discogs_sync
from app.tasks.discogs import backup as backup_task
from app.tasks.discogs import inventory_sync
from app.tenant_secrets import TenantSecrets

D = Decimal
BASE = "/admin/channels/discogs/backups"
INV = "/admin/discogs/inventory"


def _login(client, email):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert client.post("/auth/magic-link", json={"email": email}).status_code == 202
    token = re.search(r"token=([\w\-]+)", buf.getvalue()).group(1)
    return client.post(f"/auth/magic-link/verify?token={token}").json()["access_token"]


@pytest.fixture
def admin(db, client):
    access = _login(client, "admin@example.com")
    db.scalar(select(User).where(User.email == "admin@example.com")).role = "admin"
    db.commit()
    return {"Authorization": f"Bearer {access}"}


@pytest.fixture
def world(monkeypatch):
    store = jobs.MemoryKV()
    monkeypatch.setattr(jobs, "_kv", lambda: store)
    secrets = lambda tid: TenantSecrets(discogs_token_prod="tok")  # noqa: E731
    monkeypatch.setattr(discogs_sync, "get_tenant_secrets", secrets)
    monkeypatch.setattr(svc, "get_tenant_secrets", secrets)
    monkeypatch.setattr("app.routers.admin.discogs_inventory.get_tenant_secrets", secrets)
    monkeypatch.setattr("app.routers.admin.channel_backups.backup_task.delay", lambda t, j: backup_task(t, j))
    monkeypatch.setattr("app.routers.admin.discogs_inventory.inventory_sync.delay", lambda t, j: inventory_sync(t, j))
    return store


def _item(db, *, title="T", price="10.00", codi=None):
    r = Release(artista="A", title=title, formato="LP", discogs_release_id=1)
    db.add(r)
    db.flush()
    it = Item(release_id=r.id, price=D(price), condition=CondicionItem.segona_ma, status=ItemStatus.disponible)
    db.add(it)
    db.flush()
    if codi:
        it.codi_discogs = codi
    db.commit()
    return it


# --- Catálogo: crear, listar, descargar, borrar ----------------------------------------------------

def test_crear_listar_descargar_y_borrar_una_copia_del_catalogo(db, client, admin):
    _item(db, codi=100)
    r = client.post(f"{BASE}/catalog", json={"label": "  antes de probar  "}, headers=admin)
    assert r.status_code == 201
    b = r.json()
    assert b["kind"] == "catalog" and b["label"] == "antes de probar" and b["created_by"] == "admin@example.com"
    assert b["summary"]["items"] == 1 and "payload" not in b

    assert [x["id"] for x in client.get(BASE, headers=admin).json()] == [b["id"]]
    assert client.get(f"{BASE}?kind=discogs_inventory", headers=admin).json() == []
    assert client.get(f"{BASE}?kind=otro", headers=admin).status_code == 422

    d = client.get(f"{BASE}/{b['id']}/download", headers=admin)
    assert d.status_code == 200 and d.headers["content-type"] == "application/gzip"
    assert ".json.gz" in d.headers["content-disposition"]
    assert json.loads(gzip.decompress(d.content))["tables"]["items"][0]["price"] == "10.00"
    assert client.get(f"{BASE}/{b['id']}/download?formato=csv", headers=admin).status_code == 422  # csv solo para Discogs

    assert client.delete(f"{BASE}/{b['id']}", headers=admin).status_code == 204
    assert client.get(BASE, headers=admin).json() == []
    assert client.delete(f"{BASE}/{b['id']}", headers=admin).status_code == 404


def test_requiere_admin_y_discogs_activo(db, client, admin):
    assert client.get(BASE).status_code in (401, 403)
    from app.models import ConfiguracioBotiga

    db.scalar(select(ConfiguracioBotiga)).discogs_habilitat = False
    db.commit()
    assert client.get(BASE, headers=admin).status_code == 404


# --- Restaurar -----------------------------------------------------------------------------------

def test_restaurar_de_extremo_a_extremo_con_vista_previa_y_confirmacion(db, client, admin, world):
    it = _item(db, price="10.00")
    bid = client.post(f"{BASE}/catalog", json={}, headers=admin).json()["id"]
    it.price = D("33.00")
    db.commit()

    p = client.post(f"{BASE}/{bid}/restore/preview", headers=admin).json()
    assert p["counts"]["items"]["update"] == 1 and p["conflicts_total"] == 0
    assert p["sample"][0]["changes"]["price"] == ["33.00", "10.00"]
    db.expire_all()
    assert db.get(Item, it.id).price == D("33.00")   # la vista previa no cambia nada

    assert client.post(f"{BASE}/{bid}/restore", json={}, headers=admin).status_code == 422          # sin confirmar
    r = client.post(f"{BASE}/{bid}/restore", json={"confirm": True}, headers=admin)
    assert r.status_code == 200 and r.json()["restored"] is True
    db.expire_all()
    assert db.get(Item, it.id).price == D("10.00")
    tipos = {b["trigger"] for b in client.get(BASE, headers=admin).json()}
    assert tipos == {"manual", "pre_restore"}


def test_no_se_restaura_con_un_trabajo_en_marcha(db, client, admin, world):
    _item(db)
    bid = client.post(f"{BASE}/catalog", json={}, headers=admin).json()["id"]
    tenant_id = db.scalar(select(ChannelBackup)).tenant_id
    jobs.start_job(tenant_id, "dry_run", {})
    r = client.post(f"{BASE}/{bid}/restore", json={"confirm": True}, headers=admin)
    assert r.status_code == 409 and "treball en marxa" in r.json()["detail"]


def test_la_copia_de_discogs_no_se_puede_restaurar(db, client, admin, world, monkeypatch):
    b = ChannelBackup(id="d" * 32, kind="discogs_inventory", trigger="manual", payload=gzip.compress(b"{}"))
    db.add(b)
    db.commit()
    assert client.post(f"{BASE}/{b.id}/restore/preview", headers=admin).status_code == 422
    assert client.post(f"{BASE}/{b.id}/restore", json={"confirm": True}, headers=admin).status_code == 422
    assert client.post(f"{BASE}/{'0' * 32}/restore/preview", headers=admin).status_code == 404


# --- Copia de Discogs ----------------------------------------------------------------------------

def _listing(codi, estado="For Sale"):
    return {"id": codi, "status": estado, "price": {"value": 12.5, "currency": "EUR"},
            "release": {"id": 7, "description": "Artista - Título", "format": "LP", "catalog_number": "X1"},
            "condition": "Mint (M)", "sleeve_condition": "Mint (M)", "comments": "ok", "posted": "2026-01-01"}


@pytest.fixture
def discogs_feed(monkeypatch, world):
    state = {"orders": [{"id": "1-1", "status": "Shipped"}], "boom_status": None}
    monkeypatch.setattr(discogs, "get_identity", lambda token: "la-botiga")

    def fake_paged(path, token, key, params, on_page=None):
        if key == "orders":
            return state["orders"]
        if params["status"] == "For Sale":
            return [_listing(1), _listing(2)]
        if params["status"] == "Draft":
            return [_listing(3, "Draft")]
        raise httpx.HTTPStatusError("400", request=httpx.Request("GET", "http://x"), response=httpx.Response(400))

    monkeypatch.setattr(discogs_backup, "get_paged", fake_paged)
    return state


def test_copia_de_discogs_guarda_inventario_y_pedidos_y_se_descarga_en_json_y_csv(db, client, admin, discogs_feed):
    assert client.post(f"{BASE}/discogs", json={"orders": True}, headers=admin).status_code == 202
    job = client.get(f"{INV}/jobs/current", headers=admin).json()["job"]
    assert job["mode"] == "discogs_backup" and job["status"] == "done"
    assert job["summary"]["listings_total"] == 3 and job["summary"]["comandes"] == 1

    (b,) = client.get(f"{BASE}?kind=discogs_inventory", headers=admin).json()
    assert b["summary"]["compte"] == "la-botiga" and b["summary"]["listings_per_estat"] == {"For Sale": 2, "Draft": 1}
    assert set(b["summary"]["estats_fallats"]) == {"Suspended", "Expired"} and b["created_by"] == "admin@example.com"

    data = json.loads(gzip.decompress(client.get(f"{BASE}/{b['id']}/download", headers=admin).content))
    assert len(data["inventory"]) == 3 and data["orders"] == [{"id": "1-1", "status": "Shipped"}] and data["compte"] == "la-botiga"
    csv_resp = client.get(f"{BASE}/{b['id']}/download?formato=csv", headers=admin)
    assert csv_resp.headers["content-type"].startswith("text/csv")
    lineas = csv_resp.text.strip().splitlines()
    assert lineas[0].startswith("listing_id,status,release_id") and len(lineas) == 4 and "Artista - Título" in lineas[1]


def test_copia_de_discogs_sin_pedidos_y_en_modo_solo_lectura(db, client, admin, discogs_feed):
    from app.models import ConfiguracioBotiga

    db.scalar(select(ConfiguracioBotiga)).discogs_solo_lectura = True   # solo lee de Discogs
    db.commit()
    assert client.post(f"{BASE}/discogs", json={"orders": False}, headers=admin).status_code == 202
    job = client.get(f"{INV}/jobs/current", headers=admin).json()["job"]
    assert job["status"] == "done" and job["summary"]["comandes"] is None
    (b,) = client.get(BASE, headers=admin).json()
    assert json.loads(gzip.decompress(db.get(ChannelBackup, b["id"]).payload))["orders"] is None


def test_copia_de_discogs_exige_token_y_no_se_solapa_con_otro_trabajo(db, client, admin, discogs_feed, monkeypatch):
    jobs.start_job(db.info["tenant_id"], "dry_run", {})
    assert client.post(f"{BASE}/discogs", json={}, headers=admin).status_code == 409
    jobs._kv().data.clear()
    monkeypatch.setattr(discogs_sync, "get_tenant_secrets", lambda tid: TenantSecrets())
    r = client.post(f"{BASE}/discogs", json={}, headers=admin)
    assert r.status_code == 409 and "token" in r.json()["detail"]


def test_si_for_sale_falla_la_copia_de_discogs_se_ve_como_error(db, client, admin, discogs_feed, monkeypatch):
    def boom(path, token, key, params, on_page=None):
        raise httpx.ConnectError("sin red")

    monkeypatch.setattr(discogs_backup, "get_paged", boom)
    client.post(f"{BASE}/discogs", json={}, headers=admin)
    job = client.get(f"{INV}/jobs/current", headers=admin).json()["job"]
    assert job["status"] == "error" and client.get(BASE, headers=admin).json() == []


# --- Copias automáticas antes de cambiar el catálogo en bloque --------------------------------------

def test_la_carga_real_guarda_antes_una_copia_y_la_simulacion_no(db, client, admin, world, monkeypatch):
    _item(db, codi=1000, price="10.00")
    monkeypatch.setattr(svc, "_fetch_username", lambda token: "la-botiga")
    monkeypatch.setattr(svc, "_fetch_inventory", lambda token, user, limit=0, on_page=None: [
        {"id": 1000, "price": {"value": "12.00"}, "release": {"id": 1, "description": "A - T"},
         "condition": "Very Good Plus (VG+)", "sleeve_condition": "VG+", "posted": None}])

    client.post(f"{INV}/jobs", json={"mode": "dry_run"}, headers=admin)
    assert client.get(BASE, headers=admin).json() == []                      # simular no guarda copia

    client.post(f"{INV}/jobs", json={"mode": "apply"}, headers=admin)
    job = client.get(f"{INV}/jobs/current", headers=admin).json()["job"]
    (b,) = client.get(BASE, headers=admin).json()
    assert b["trigger"] == "pre_load" and b["label"] == "Abans de la càrrega inicial" and b["created_by"] == "admin@example.com"
    assert job["summary"]["copia_previa"] == b["id"]
    db.expire_all()
    assert db.scalar(select(Item)).price == D("12.00")

    # y se puede volver atrás: restaurar esa copia devuelve el precio de antes
    r = client.post(f"{BASE}/{b['id']}/restore", json={"confirm": True}, headers=admin)
    assert r.status_code == 200
    db.expire_all()
    assert db.scalar(select(Item)).price == D("10.00")


def test_si_no_se_puede_guardar_la_copia_previa_la_carga_real_aborta(db, client, admin, world, monkeypatch):
    it = _item(db, codi=1000, price="10.00")
    monkeypatch.setattr(svc, "_fetch_username", lambda token: "la-botiga")
    monkeypatch.setattr(svc, "_fetch_inventory", lambda token, user, limit=0, on_page=None: [
        {"id": 1000, "price": {"value": "12.00"}, "release": {"id": 1, "description": "A - T"}, "condition": "Mint (M)"}])
    client.post(f"{INV}/jobs", json={"mode": "dry_run"}, headers=admin)

    def falla(*a, **k):
        raise RuntimeError("disco lleno")

    monkeypatch.setattr(svc, "create_snapshot", falla)
    client.post(f"{INV}/jobs", json={"mode": "apply"}, headers=admin)
    job = client.get(f"{INV}/jobs/current", headers=admin).json()["job"]
    assert job["status"] == "error" and "disco lleno" in job["error"]
    db.expire_all()
    assert db.get(Item, it.id).price == D("10.00")   # no se tocó nada


def test_aplicar_precios_guarda_antes_una_copia(db, client, admin, world, monkeypatch):
    it = _item(db, price="15.00")
    monkeypatch.setattr(discogs, "get_price_suggestions", lambda token, rid: {"Very Good Plus (VG+)": {"currency": "EUR", "value": 20.0}})
    it.estado_disco = "Very Good Plus (VG+)"
    db.commit()
    from app.tasks.discogs import pricing_preview

    monkeypatch.setattr("app.routers.admin.channel_pricing.pricing_preview.delay", lambda t, j: pricing_preview(t, j))
    client.post("/admin/channels/discogs/pricing/preview", json={"limit": 10}, headers=admin)
    job = client.get(f"{INV}/jobs/current", headers=admin).json()["job"]
    assert client.get(BASE, headers=admin).json() == []
    client.post("/admin/channels/discogs/pricing/apply", json={"job_id": job["id"]}, headers=admin)
    (b,) = client.get(BASE, headers=admin).json()
    assert b["trigger"] == "pre_prices"
    client.post(f"{BASE}/{b['id']}/restore", json={"confirm": True}, headers=admin)
    db.expire_all()
    assert db.get(Item, it.id).price == D("15.00")
