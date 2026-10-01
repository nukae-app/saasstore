"""Cada funcionalidad conserva SU último resultado y SU historial: lanzar un trabajo de otro tipo no debe
borrar ni mezclar los informes (la ranura de "trabajo en curso" es única, la de resultados no)."""

import contextlib
import io
import re
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import CondicionItem, Item, ItemStatus, Release, User
from app.services import channel_pricing, discogs, discogs_inventory_sync as svc, discogs_jobs as jobs, discogs_sync
from app.tasks.discogs import inventory_sync, pricing_preview
from app.tenant_secrets import TenantSecrets

INV = "/admin/discogs/inventory"
CH = "/admin/channels/discogs"


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
    """Redis en memoria, secretos, Discogs falso (inventario y precios) y colas en línea."""
    store = jobs.MemoryKV()
    monkeypatch.setattr(jobs, "_kv", lambda: store)
    secrets = lambda tid: TenantSecrets(discogs_token_prod="tok")  # noqa: E731
    monkeypatch.setattr("app.routers.admin.discogs_inventory.get_tenant_secrets", secrets)
    monkeypatch.setattr(svc, "get_tenant_secrets", secrets)
    monkeypatch.setattr(discogs_sync, "get_tenant_secrets", secrets)
    state = {"listings": []}
    monkeypatch.setattr(svc, "_fetch_username", lambda token: "la-botiga")
    monkeypatch.setattr(svc, "_fetch_inventory", lambda token, user, limit=0, on_page=None: state["listings"])
    monkeypatch.setattr(discogs, "get_price_suggestions", lambda token, rid: {"Near Mint (NM or M-)": {"currency": "EUR", "value": 20.0}})
    monkeypatch.setattr("app.routers.admin.discogs_inventory.inventory_sync.delay", lambda t, j: inventory_sync(t, j))
    monkeypatch.setattr("app.routers.admin.channel_pricing.pricing_preview.delay", lambda t, j: pricing_preview(t, j))
    return state


def _seed(db):
    r = Release(artista="A", title="T", formato="LP", discogs_release_id=1)
    db.add(r)
    db.flush()
    it = Item(release_id=r.id, price=Decimal("15.00"), condition=CondicionItem.segona_ma, status=ItemStatus.disponible,
              estado_disco="Near Mint (NM or M-)", codi_discogs=1000)
    db.add(it)
    db.commit()
    return it


def test_lanzar_otro_trabajo_no_borra_el_ultimo_resultado_de_cada_tipo(db, client, admin, world):
    item = _seed(db)
    world["listings"] = [{"id": 1000, "price": {"value": "12.00"}, "release": {"id": 1, "description": "A - T"},
                          "condition": "Near Mint (NM or M-)"}]

    client.post(f"{CH}/pricing/preview", json={"limit": 10}, headers=admin)          # 1º: simulación de precios
    precios = client.get(f"{INV}/jobs/current", headers=admin).json()["job"]
    assert precios["mode"] == "pricing_preview" and precios["summary"]["puja"] == 1

    client.post(f"{INV}/jobs", json={"mode": "dry_run"}, headers=admin)              # 2º: simulación de carga
    estado = client.get(f"{INV}/jobs/current", headers=admin).json()
    assert estado["job"]["mode"] == "dry_run"                                        # el "en curso" cambia...

    ultims = estado["ultims"]                                                        # ...pero cada tipo conserva el suyo
    assert ultims["pricing_preview"]["id"] == precios["id"] and ultims["pricing_preview"]["summary"]["puja"] == 1
    assert ultims["inventory_dry_run"]["id"] == estado["job"]["id"] and ultims["inventory_dry_run"]["summary"]["actualitzats"] == 1
    assert set(ultims) == {"pricing_preview", "inventory_dry_run"}

    # y el informe de la simulación de precios sigue siendo accesible y aplicable tras la de carga
    rows = client.get(f"{INV}/jobs/{precios['id']}/rows", headers=admin).json()
    assert [r["accio"] for r in rows["rows"]] == ["repreu_puja"]
    assert client.post(f"{CH}/pricing/apply", json={"job_id": precios["id"]}, headers=admin).json()["aplicats"] == 1
    db.expire_all()
    assert db.get(Item, item.id).price == Decimal("20.00")


def test_cada_tipo_apunta_a_su_ultima_ejecucion(db, client, admin, world):
    _seed(db)
    world["listings"] = [{"id": 1000, "price": {"value": "15.00"}, "release": {"id": 1, "description": "A - T"},
                          "condition": "Near Mint (NM or M-)"}]
    client.post(f"{CH}/pricing/preview", json={"limit": 10}, headers=admin)
    primera = client.get(f"{INV}/jobs/current", headers=admin).json()["job"]["id"]
    from datetime import datetime, timedelta, timezone

    from app.models import ChannelSyncRun

    db.get(ChannelSyncRun, primera).created_at = datetime.now(timezone.utc) - timedelta(minutes=1)  # SQLite: 1 s de resolución
    db.commit()
    client.post(f"{CH}/pricing/preview", json={"limit": 10, "factor": 0.5}, headers=admin)
    segunda = client.get(f"{INV}/jobs/current", headers=admin).json()["job"]["id"]
    assert primera != segunda
    assert client.get(f"{INV}/jobs/current", headers=admin).json()["ultims"]["pricing_preview"]["id"] == segunda


def test_el_historial_se_filtra_por_funcionalidad(db, client, admin, world):
    _seed(db)
    world["listings"] = []
    client.post(f"{CH}/pricing/preview", json={"limit": 10}, headers=admin)
    client.post(f"{INV}/jobs", json={"mode": "dry_run"}, headers=admin)

    todos = client.get(f"{INV}/runs", headers=admin).json()
    assert {r["kind"] for r in todos} == {"pricing_preview", "inventory_dry_run"}

    solo_carga = client.get(f"{INV}/runs?kinds=inventory_dry_run,inventory_apply", headers=admin).json()
    assert [r["kind"] for r in solo_carga] == ["inventory_dry_run"]
    solo_precios = client.get(f"{INV}/runs?kinds=pricing_preview", headers=admin).json()
    assert [r["kind"] for r in solo_precios] == ["pricing_preview"]
    assert client.get(f"{INV}/runs?kinds=reconcile_apply", headers=admin).json() == []


def test_sin_ejecuciones_no_hay_ultimos(db, client, admin, world):
    assert client.get(f"{INV}/jobs/current", headers=admin).json()["ultims"] == {}
