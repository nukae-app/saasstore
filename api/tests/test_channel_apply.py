"""Aplicador del plan de reconciliación (services/channel_apply.py y endpoints /reconcile)."""

import contextlib
import io
import re
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import ChannelEvent, ChannelListing, ConfiguracioBotiga, CondicionItem, Item, ItemStatus, Release, Tenant, User
from app.services import channel_apply, discogs_jobs as jobs
from app.services.channel_apply import ReconcileAbort, run_reconcile, scheduled_actions
from app.services.channel_settings import get_settings
from app.services.discogs import ReadOnlyToken
from app.tasks.discogs import reconcile_apply, reconcile_scheduled
from app.tenant_secrets import TenantSecrets

D = Decimal


class FakeDiscogs:
    """Sustituye a las tres escrituras de Discogs y recuerda qué se pidió."""

    def __init__(self):
        self.calls = []
        self.next_id = 9000
        self.fail_publish = None  # mensaje de error o None
        self.gone = False

    def push(self, token, item_id, rid, precio, estado_disco, estado_funda, notas=None, es_nou=False, *, db=None, actor=None):
        self.calls.append(("push", rid, precio, es_nou, actor))
        if self.fail_publish:
            return None, self.fail_publish
        self.next_id += 1
        return self.next_id, None

    def update(self, token, listing_id, item_id, rid, precio, estado_disco, estado_funda, notas=None, es_nou=False, *, db=None, actor=None):
        self.calls.append(("update", listing_id, precio))
        return (False, "Discogs 404", True) if self.gone else (True, None, False)

    def remove(self, token, codi, *, db=None, item_id=None, actor=None):
        self.calls.append(("remove", codi))
        return True, None


@pytest.fixture
def fake(monkeypatch):
    f = FakeDiscogs()
    monkeypatch.setattr(channel_apply, "push_listing", f.push)
    monkeypatch.setattr(channel_apply, "update_listing", f.update)
    monkeypatch.setattr(channel_apply, "remove_listing", f.remove)
    monkeypatch.setattr("app.services.discogs_sync.get_tenant_secrets", lambda tid: TenantSecrets(discogs_token_prod="tok"))
    return f


def _tenant(db):
    return db.scalar(select(Tenant))


def _mk(db, *, title="T", rid=123, status=ItemStatus.disponible, condition=CondicionItem.segona_ma, quantity=1,
        price="10.00", codi=None, listing=None, published=None):
    r = Release(artista="A", title=title, formato="LP", discogs_release_id=rid)
    db.add(r)
    db.flush()
    it = Item(release_id=r.id, price=D(price), condition=condition, status=status, quantity=quantity,
              estado_disco="Near Mint (NM or M-)" if condition == CondicionItem.segona_ma else None)
    db.add(it)
    db.flush()
    if codi:
        it.codi_discogs = codi
    if listing:
        db.add(ChannelListing(item_id=it.id, external_id=str(codi) if codi else None, status=listing,
                              published_price=D(published) if published else None))
    db.commit()
    return it


def _listing(db, item):
    db.expire_all()
    return db.scalar(select(ChannelListing).where(ChannelListing.item_id == item.id))


def test_publicar_crea_el_listing_y_mantiene_codi_discogs(db, fake):
    it = _mk(db)
    res = run_reconcile(db, _tenant(db), actor="ana@x.com", log_fn=lambda m: None)
    assert fake.calls == [("push", 123, 10.0, False, "ana@x.com")]
    assert res.summary["publicats"] == 1 and res.summary["errors"] == 0
    l = _listing(db, it)
    assert l.status == "publicat" and l.external_id == "9001" and l.published_price == D("10.00") and l.last_error is None
    assert it.codi_discogs == 9001  # la app sigue leyendo codi_discogs
    assert res.rows[0]["accio"] == "publicar" and res.rows[0]["motiu"] == "OK" and res.rows[0]["codi_discogs"] == 9001


def test_publicar_con_error_marca_el_listing_y_sigue(db, fake):
    fake.fail_publish = "Discogs 422: seller settings incomplete"
    a, b = _mk(db, title="A"), _mk(db, title="B")
    res = run_reconcile(db, _tenant(db), log_fn=lambda m: None)
    assert res.summary["errors"] == 2 and res.summary["publicats"] == 0
    l = _listing(db, a)
    assert l.status == "error" and "seller settings" in l.last_error and l.attempts == 1
    assert all(r["accio"] == "error" and "publicar: Discogs 422" in r["motiu"] for r in res.rows)
    assert a.codi_discogs is None


def test_actualizar_precio_y_marcar_404_como_error(db, fake):
    it = _mk(db, price="12.00", codi=5, listing="publicat", published="10.00")
    run_reconcile(db, _tenant(db), log_fn=lambda m: None)
    assert fake.calls == [("update", 5, 12.0)]
    assert _listing(db, it).published_price == D("12.00")

    it2 = _mk(db, price="20.00", codi=6, listing="publicat", published="15.00")
    fake.gone = True
    res = run_reconcile(db, _tenant(db), item_ids={it2.id}, log_fn=lambda m: None)
    l = _listing(db, it2)
    assert l.status == "error" and "404" in l.last_error and res.summary["errors"] == 1


def test_retirar_borra_el_listing_y_limpia_codi_discogs(db, fake):
    it = _mk(db, status=ItemStatus.vendido, codi=7, listing="publicat", published="10.00")
    res = run_reconcile(db, _tenant(db), log_fn=lambda m: None)
    assert fake.calls == [("remove", 7)] and res.summary["retirats"] == 1
    assert _listing(db, it).status == "retirat" and it.codi_discogs is None


def test_orden_de_ejecucion_retira_antes_que_actualiza_y_publica(db, fake):
    _mk(db, title="pub")
    _mk(db, title="upd", price="12.00", codi=1, listing="publicat", published="10.00")
    _mk(db, title="ret", status=ItemStatus.retirado, codi=2, listing="publicat", published="10.00")
    run_reconcile(db, _tenant(db), log_fn=lambda m: None)
    assert [c[0] for c in fake.calls] == ["remove", "update", "push"]


def test_se_puede_limitar_por_acciones_y_por_items(db, fake):
    pub = _mk(db, title="pub")
    _mk(db, title="ret", status=ItemStatus.retirado, codi=2, listing="publicat", published="10.00")
    run_reconcile(db, _tenant(db), actions={"publicar"}, log_fn=lambda m: None)
    assert [c[0] for c in fake.calls] == ["push"]

    fake.calls.clear()
    otro = _mk(db, title="otro")
    run_reconcile(db, _tenant(db), item_ids={otro.id}, log_fn=lambda m: None)
    assert [c[0] for c in fake.calls] == ["push"] and _listing(db, pub).status == "publicat"


def test_modo_solo_lectura_y_sin_token_abortan(db, fake, monkeypatch):
    _mk(db)
    db.scalar(select(ConfiguracioBotiga)).discogs_solo_lectura = True
    db.commit()
    with pytest.raises(ReconcileAbort, match="només lectura"):
        run_reconcile(db, _tenant(db), log_fn=lambda m: None)

    db.scalar(select(ConfiguracioBotiga)).discogs_solo_lectura = False
    db.commit()
    monkeypatch.setattr("app.services.discogs_sync.get_tenant_secrets", lambda tid: TenantSecrets())
    with pytest.raises(ReconcileAbort, match="token"):
        run_reconcile(db, _tenant(db), log_fn=lambda m: None)
    assert fake.calls == []


def test_freno_si_retira_mas_del_20_por_ciento(db, fake):
    for k in range(30):  # 30 publicados que ya no están a la venta
        _mk(db, title=f"v{k}", status=ItemStatus.vendido, codi=100 + k, listing="publicat", published="10.00")
    for k in range(20):  # y 20 publicados correctos: 30/50 = 60 %
        _mk(db, title=f"ok{k}", codi=200 + k, listing="publicat", published="10.00")
    with pytest.raises(ReconcileAbort, match="30 de 50"):
        run_reconcile(db, _tenant(db), log_fn=lambda m: None)
    assert fake.calls == []
    res = run_reconcile(db, _tenant(db), force=True, log_fn=lambda m: None)
    assert res.summary["retirats"] == 30


def test_pocas_retiradas_no_activan_el_freno_aunque_sean_mucho_porcentaje(db, fake):
    _mk(db, status=ItemStatus.vendido, codi=1, listing="publicat", published="10.00")
    assert run_reconcile(db, _tenant(db), log_fn=lambda m: None).summary["retirats"] == 1


def test_skip_errors_deja_para_revision_manual_los_listings_en_error(db, fake):
    err = _mk(db, listing="error")
    res = run_reconcile(db, _tenant(db), skip_errors=True, log_fn=lambda m: None)
    assert res.summary["total"] == 0 and fake.calls == []
    run_reconcile(db, _tenant(db), log_fn=lambda m: None)  # a mano sí se reintenta
    assert fake.calls and _listing(db, err).status == "publicat"


def test_recargo_se_aplica_al_precio_publicado(db, fake):
    get_settings(db).recargo_pct = D("10")
    db.commit()
    _mk(db, price="20.00")
    run_reconcile(db, _tenant(db), log_fn=lambda m: None)
    assert fake.calls[0][2] == 22.0


def test_acciones_programadas_dependen_de_la_publicacion_automatica(db):
    s = get_settings(db)
    assert scheduled_actions(s) == {"retirar"}
    s.publicacion_auto = True
    assert scheduled_actions(s) == {"retirar", "publicar", "actualitzar_preu"}


# --- Endpoints ---------------------------------------------------------------------------

BASE = "/admin/channels/discogs"


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
def inline(monkeypatch, fake):
    store = jobs.MemoryKV()
    monkeypatch.setattr(jobs, "_kv", lambda: store)
    monkeypatch.setattr("app.routers.admin.channel_discogs.reconcile_apply.delay", lambda t, j: reconcile_apply(t, j))
    return store


def test_preview_cuenta_acciones_y_avisa_del_freno(db, client, admin, fake):
    _mk(db, title="pub")
    _mk(db, title="ret", status=ItemStatus.retirado, codi=2, listing="publicat", published="10.00")
    d = client.post(f"{BASE}/reconcile/preview", json={}, headers=admin).json()
    assert d["total"] == 2 and d["counts"] == {"publicar": 1, "retirar": 1} and d["guard"] is None
    assert {r["titol"] for r in d["sample"]} == {"pub", "ret"}
    assert client.post(f"{BASE}/reconcile/preview", json={"actions": ["publicar"]}, headers=admin).json()["total"] == 1
    assert fake.calls == []  # la vista previa no toca Discogs


def test_reconcile_endpoint_lanza_el_trabajo_y_deja_historial(db, client, admin, inline, fake):
    it = _mk(db)
    resp = client.post(f"{BASE}/reconcile", json={"actions": ["publicar"]}, headers=admin)
    assert resp.status_code == 202
    job = client.get("/admin/discogs/inventory/jobs/current", headers=admin).json()["job"]
    assert job["status"] == "done" and job["mode"] == "reconcile" and job["summary"]["publicats"] == 1
    assert fake.calls[0][4] == "admin@example.com"  # actor = usuario que lo lanzó
    assert _listing(db, it).status == "publicat"

    runs = client.get("/admin/discogs/inventory/runs", headers=admin).json()
    assert runs[0]["kind"] == "reconcile_apply" and runs[0]["status"] == "done"
    rows = client.get(f"/admin/discogs/inventory/jobs/{job['id']}/rows", headers=admin).json()
    assert rows["rows"][0]["accio"] == "publicar" and rows["rows"][0]["motiu"] == "OK"


def test_reconcile_endpoint_rechaza_solo_lectura_sin_nada_que_hacer_y_concurrencia(db, client, admin, inline, fake):
    db.scalar(select(ConfiguracioBotiga)).discogs_solo_lectura = True
    db.commit()
    assert client.post(f"{BASE}/reconcile", json={}, headers=admin).status_code == 409

    db.scalar(select(ConfiguracioBotiga)).discogs_solo_lectura = False
    db.commit()
    assert client.post(f"{BASE}/reconcile", json={}, headers=admin).status_code == 409  # nada que hacer

    _mk(db)
    tenant_id = db.scalar(select(ConfiguracioBotiga)).tenant_id
    jobs.start_job(tenant_id, "dry_run", {})  # ya hay un trabajo en marcha
    assert client.post(f"{BASE}/reconcile", json={}, headers=admin).status_code == 409


def test_freno_visible_como_error_de_aborto_en_el_trabajo(db, client, admin, inline, fake):
    for k in range(30):
        _mk(db, title=f"v{k}", status=ItemStatus.vendido, codi=100 + k, listing="publicat", published="10.00")
    client.post(f"{BASE}/reconcile", json={}, headers=admin)
    job = client.get("/admin/discogs/inventory/jobs/current", headers=admin).json()["job"]
    assert job["status"] == "error" and job["error_kind"] == "abort" and fake.calls == []


# --- Tarea programada --------------------------------------------------------------------

def _adopcion_hecha(db):
    from app.services.discogs_sync import marcar_adopcio_feta

    marcar_adopcio_feta(db, {})
    db.commit()


def test_programada_retira_solo_y_no_publica_en_manual(db, fake, inline, monkeypatch):
    _adopcion_hecha(db)
    ret = _mk(db, status=ItemStatus.vendido, codi=2, listing="publicat", published="10.00")
    pub = _mk(db, title="pendiente")
    assert reconcile_scheduled() == {"lanzados": 1}
    assert [c[0] for c in fake.calls] == ["remove"]
    assert _listing(db, ret).status == "retirat" and _listing(db, pub) is None


def test_programada_no_hace_nada_sin_adopcion_en_solo_lectura_o_con_sync_apagado(db, fake, inline):
    _mk(db, status=ItemStatus.vendido, codi=2, listing="publicat", published="10.00")
    assert reconcile_scheduled() == {"lanzados": 0}  # adopción sin hacer

    _adopcion_hecha(db)
    get_settings(db).sync_auto = False
    db.commit()
    assert reconcile_scheduled() == {"lanzados": 0}

    get_settings(db).sync_auto = True
    db.scalar(select(ConfiguracioBotiga)).discogs_solo_lectura = True
    db.commit()
    assert reconcile_scheduled() == {"lanzados": 0} and fake.calls == []


def test_programada_con_publicacion_automatica_tambien_publica_y_actualiza(db, fake, inline):
    _adopcion_hecha(db)
    get_settings(db).publicacion_auto = True
    db.commit()
    _mk(db, title="pendiente")
    _mk(db, title="precio", price="12.00", codi=1, listing="publicat", published="10.00")
    assert reconcile_scheduled() == {"lanzados": 1}
    assert sorted(c[0] for c in fake.calls) == ["push", "update"]
