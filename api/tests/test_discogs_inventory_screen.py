"""Pantalla de sincronización de inventario Discogs -> app (endpoints
/admin/discogs/inventory/* y tarea de Celery). Redis y Celery se sustituyen
por un almacén en memoria y por ejecución en línea."""

import contextlib
import io
import re
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import ConfiguracioBotiga, Item, ItemStatus, Release, User
from app.services import discogs_inventory_sync as svc
from app.services import discogs_jobs as jobs
from app.services.discogs_sync import adopcio_feta
from app.tasks.discogs import inventory_sync
from app.tenant_secrets import TenantSecrets

BASE = "/admin/discogs/inventory"


def _login(client, email: str) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert client.post("/auth/magic-link", json={"email": email}).status_code == 202
    token = re.search(r"token=([\w\-]+)", buf.getvalue()).group(1)
    resp = client.post(f"/auth/magic-link/verify?token={token}")
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture
def admin(db, client):
    access = _login(client, "admin@example.com")
    user = db.scalar(select(User).where(User.email == "admin@example.com"))
    user.role = "admin"
    db.commit()
    return {"Authorization": f"Bearer {access}"}


@pytest.fixture
def kv(monkeypatch):
    store = jobs.MemoryKV()
    monkeypatch.setattr(jobs, "_kv", lambda: store)
    return store


@pytest.fixture
def discogs(monkeypatch, kv):
    """Secretos, red de Discogs y cola de Celery (en línea) falseados."""
    state = {"listings": []}
    secrets = lambda tid: TenantSecrets(discogs_token_prod="tok")  # noqa: E731
    monkeypatch.setattr("app.routers.admin.discogs_inventory.get_tenant_secrets", secrets)
    monkeypatch.setattr(svc, "get_tenant_secrets", secrets)
    monkeypatch.setattr(svc, "_fetch_username", lambda token: "la-botiga")
    monkeypatch.setattr(
        svc, "_fetch_inventory", lambda token, user, limit=0, on_page=None: state["listings"]
    )
    monkeypatch.setattr(
        "app.routers.admin.discogs_inventory.inventory_sync.delay", lambda t, j: inventory_sync(t, j)
    )
    return state


def _listing(codi, precio="10.00"):
    return {
        "id": codi, "price": {"value": precio}, "release": {"id": codi, "description": "Artista - Títol"},
        "condition": "Very Good Plus (VG+)", "sleeve_condition": "VG+", "posted": None,
    }


def _seed(db, n, precio="10.00"):
    items = []
    for k in range(n):
        r = Release(artista=f"Artista{k}", title=f"Títol{k}", formato="LP", discogs_release_id=500 + k)
        db.add(r)
        db.flush()
        it = Item(release_id=r.id, price=Decimal(precio), codi_discogs=1000 + k)
        db.add(it)
        items.append(it)
    db.commit()
    return items


def _current(client, admin) -> dict:
    return client.get(f"{BASE}/jobs/current", headers=admin).json()


def test_simulacion_extremo_a_extremo_no_guarda_nada(db, client, admin, discogs):
    items = _seed(db, 5)
    discogs["listings"] = [_listing(1000 + k, "12.00" if k == 0 else "10.00") for k in range(5)]

    resp = client.post(f"{BASE}/jobs", json={"mode": "dry_run"}, headers=admin)
    assert resp.status_code == 202

    estado = _current(client, admin)
    job = estado["job"]
    assert job["status"] == "done" and job["mode"] == "dry_run"
    assert job["summary"]["actualitzats"] == 1 and job["summary"]["compte_discogs"] == "la-botiga"
    assert estado["ultima_simulacio"]["job_id"] == job["id"]

    db.expire_all()
    assert items[0].price == Decimal("10.00")  # simulación: sin cambios

    rows = client.get(f"{BASE}/jobs/{job['id']}/rows", headers=admin).json()
    assert rows["total"] == 1 and rows["counts"] == {"actualitzar_preu": 1}
    assert rows["rows"][0]["preu_app"] == "10.00" and rows["rows"][0]["preu_discogs"] == "12.00"

    csv_resp = client.get(f"{BASE}/jobs/{job['id']}/report.csv", headers=admin)
    assert csv_resp.status_code == 200 and csv_resp.text.startswith("accio,codi_discogs")
    assert "actualitzar_preu" in csv_resp.text


def test_aplicar_exige_simulacion_previa(db, client, admin, discogs):
    _seed(db, 2)
    discogs["listings"] = [_listing(1000), _listing(1001)]
    resp = client.post(f"{BASE}/jobs", json={"mode": "apply"}, headers=admin)
    assert resp.status_code == 409 and "simulació" in resp.json()["detail"]


def test_aplicar_tras_simular_guarda_marca_adopcion_y_se_bloquea(db, client, admin, discogs):
    items = _seed(db, 5)
    discogs["listings"] = [_listing(1000 + k, "12.00" if k == 0 else "10.00") for k in range(5)]
    assert client.post(f"{BASE}/jobs", json={"mode": "dry_run"}, headers=admin).status_code == 202

    assert client.post(f"{BASE}/jobs", json={"mode": "apply"}, headers=admin).status_code == 202
    job = _current(client, admin)["job"]
    assert job["status"] == "done" and job["mode"] == "apply" and job["summary"]["adopcio_marcada"] is True

    db.expire_all()
    assert items[0].price == Decimal("12.00")
    assert adopcio_feta(db) is not None

    resp = client.post(f"{BASE}/jobs", json={"mode": "apply"}, headers=admin)
    assert resp.status_code == 409 and "adopció" in resp.json()["detail"]


def test_aplicar_con_inventario_vacio_aborta_y_lo_muestra(db, client, admin, discogs):
    items = _seed(db, 3)
    discogs["listings"] = []
    client.post(f"{BASE}/jobs", json={"mode": "dry_run"}, headers=admin)  # la simulación solo avisa
    sim = _current(client, admin)["job"]
    assert sim["status"] == "done" and sim["summary"]["avisos"]

    client.post(f"{BASE}/jobs", json={"mode": "apply"}, headers=admin)
    job = _current(client, admin)["job"]
    assert job["status"] == "error" and "cap listing" in job["error"]
    db.expire_all()
    assert all(i.status == ItemStatus.disponible for i in items)  # no se ha retirado nada


def test_no_se_pueden_lanzar_dos_a_la_vez(db, client, admin, discogs):
    tenant_id = db.scalar(select(ConfiguracioBotiga)).tenant_id
    jobs.start_job(tenant_id, "dry_run", {})  # queda en "queued"
    resp = client.post(f"{BASE}/jobs", json={"mode": "dry_run"}, headers=admin)
    assert resp.status_code == 409


def test_trabajo_encallado_se_reporta_y_permite_relanzar(db, client, admin, discogs, kv):
    tenant_id = db.scalar(select(ConfiguracioBotiga)).tenant_id
    job = jobs.start_job(tenant_id, "dry_run", {})
    jobs.update_job(
        tenant_id, job["id"], status="running",
        updated_at=(jobs._now() - timedelta(minutes=30)).isoformat(timespec="seconds"),
    )
    # update_job renueva updated_at: se fuerza el valor antiguo directamente
    raw = jobs._load(jobs._key_job(tenant_id))
    raw["updated_at"] = (jobs._now() - timedelta(minutes=30)).isoformat(timespec="seconds")
    jobs._save(jobs._key_job(tenant_id), raw)

    assert _current(client, admin)["job"]["status"] == "stalled"
    discogs["listings"] = [_listing(1000)]
    _seed(db, 1)
    assert client.post(f"{BASE}/jobs", json={"mode": "dry_run"}, headers=admin).status_code == 202


def test_sin_token_devuelve_409(db, client, admin, discogs, monkeypatch):
    monkeypatch.setattr(
        "app.routers.admin.discogs_inventory.get_tenant_secrets", lambda tid: TenantSecrets()
    )
    resp = client.post(f"{BASE}/jobs", json={"mode": "dry_run"}, headers=admin)
    assert resp.status_code == 409 and "token" in resp.json()["detail"]


def test_discogs_desactivado_da_404(db, client, admin, discogs):
    db.scalar(select(ConfiguracioBotiga)).discogs_habilitat = False
    db.commit()
    assert client.get(f"{BASE}/jobs/current", headers=admin).status_code == 404


def test_requiere_admin(client):
    assert client.get(f"{BASE}/jobs/current").status_code in (401, 403)


def test_filas_se_filtran_por_accion_y_texto(db, client, admin, discogs):
    _seed(db, 4)
    discogs["listings"] = [_listing(1000, "11.00"), _listing(1001, "12.00")]  # 2 cambian precio, 2 se retiran
    client.post(f"{BASE}/jobs", json={"mode": "dry_run"}, headers=admin)
    job_id = _current(client, admin)["job"]["id"]

    todo = client.get(f"{BASE}/jobs/{job_id}/rows", headers=admin).json()
    assert todo["counts"] == {"actualitzar_preu": 2, "retirar": 2}

    retirar = client.get(f"{BASE}/jobs/{job_id}/rows?accio=retirar", headers=admin).json()
    assert retirar["total"] == 2

    buscar = client.get(f"{BASE}/jobs/{job_id}/rows?q=artista3", headers=admin).json()
    assert buscar["total"] == 1 and buscar["rows"][0]["accio"] == "retirar"

    assert client.get(f"{BASE}/jobs/inexistente/rows", headers=admin).status_code == 404


# --- Historial persistente (fase A) ------------------------------------------------------

def test_historial_persiste_la_simulacion_y_sobrevive_a_redis(db, client, admin, discogs, kv):
    from app.models import ChannelSyncRun

    _seed(db, 3)
    discogs["listings"] = [_listing(1000, "11.00"), _listing(1001), _listing(1002)]
    client.post(f"{BASE}/jobs", json={"mode": "dry_run"}, headers=admin)
    job_id = _current(client, admin)["job"]["id"]

    runs = client.get(f"{BASE}/runs", headers=admin).json()
    assert [(r["id"], r["kind"], r["status"], r["rows_count"]) for r in runs] == [
        (job_id, "inventory_dry_run", "done", 1)
    ]
    assert runs[0]["summary"]["actualitzats"] == 1 and runs[0]["finished_at"] is not None

    db.expire_all()
    run = db.get(ChannelSyncRun, job_id)
    assert run.report[0]["accio"] == "actualitzar_preu" and run.report[0]["preu_discogs"] == "11.00"

    kv.data.clear()  # Redis caducado/perdido: el informe sigue disponible desde la BD
    rows = client.get(f"{BASE}/jobs/{job_id}/rows", headers=admin)
    assert rows.status_code == 200 and rows.json()["total"] == 1
    assert client.get(f"{BASE}/jobs/{job_id}/report.csv", headers=admin).status_code == 200


def test_historial_guarda_los_abortos(db, client, admin, discogs):
    _seed(db, 2)
    discogs["listings"] = []
    client.post(f"{BASE}/jobs", json={"mode": "dry_run"}, headers=admin)
    client.post(f"{BASE}/jobs", json={"mode": "apply"}, headers=admin)

    runs = client.get(f"{BASE}/runs", headers=admin).json()
    apply_run = next(r for r in runs if r["kind"] == "inventory_apply")
    assert apply_run["status"] == "error" and "cap listing" in apply_run["error"]


def test_aplicar_deja_channel_listings_alineado_con_los_vinculos(db, client, admin, discogs):
    from app.models import ChannelListing

    items = _seed(db, 2)  # el reflejo automático ya crea el vínculo al asignar codi_discogs
    discogs["listings"] = [_listing(1000), _listing(1001)]
    client.post(f"{BASE}/jobs", json={"mode": "dry_run"}, headers=admin)
    client.post(f"{BASE}/jobs", json={"mode": "apply"}, headers=admin)
    job = _current(client, admin)["job"]
    assert job["summary"]["channel_listings"] == {"creats": 0, "actualitzats": 0, "retirats": 0}  # nada que reparar
    db.expire_all()
    ls = db.scalars(select(ChannelListing)).all()
    assert {l.external_id for l in ls} == {"1000", "1001"} and {l.item_id for l in ls} == {i.id for i in items}
    assert all(l.status == "publicat" for l in ls)


def test_aplicar_crea_el_vinculo_de_los_items_nuevos_que_vienen_de_discogs(db, client, admin, discogs, monkeypatch):
    from app.models import ChannelListing

    _seed(db, 1)
    nuevo = Release(artista="Nou", title="Disc", formato="LP", discogs_release_id=777)
    db.add(nuevo)
    db.commit()
    monkeypatch.setattr(svc, "_find_or_create_release", lambda db_, token, rid, desc: db_.get(Release, nuevo.id))
    nuevo_listing = _listing(3000)
    nuevo_listing["release"]["id"] = 777
    discogs["listings"] = [_listing(1000), nuevo_listing]
    client.post(f"{BASE}/jobs", json={"mode": "dry_run"}, headers=admin)
    client.post(f"{BASE}/jobs", json={"mode": "apply"}, headers=admin)
    db.expire_all()
    assert {l.external_id for l in db.scalars(select(ChannelListing)).all()} == {"1000", "3000"}


def test_trabajo_en_marcha_antiguo_y_no_actual_se_muestra_encallado(db):
    from app.models import ChannelSyncRun
    from app.services import channel_runs

    old = ChannelSyncRun(id="a" * 32, kind="inventory_dry_run", status="running", options={})
    db.add(old)
    db.commit()
    db.refresh(old)
    old.created_at = jobs._now() - timedelta(minutes=30)
    assert channel_runs.effective_status(old, current_job=None) == "stalled"
    assert channel_runs.effective_status(old, current_job={"id": old.id, "status": "running"}) == "running"
    old.status = "done"
    assert channel_runs.effective_status(old, current_job=None) == "done"
