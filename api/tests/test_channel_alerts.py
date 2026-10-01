"""Alertas del canal, avisos por correo configurables y auditoría contra Discogs (fase E)."""

import contextlib
import io
import re
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from app.models import (
    ChannelAlert, ChannelListing, ConfiguracioBotiga, CondicionItem, Item, ItemStatus, Release, Tenant, User,
)
from app.services import channel_alerts, channel_audit, channel_notifications, channel_orders, discogs_jobs as jobs
from app.services import discogs_sync
from app.services.channel_audit import AuditAbort, run_audit
from app.services.discogs_sync import marcar_adopcio_feta
from app.tasks.discogs import audit as audit_task
from app.tenant_secrets import TenantSecrets

D = Decimal
BASE = "/admin/channels/discogs"


def _alerts(db, **kw):
    db.expire_all()
    return list(db.scalars(select(ChannelAlert).order_by(ChannelAlert.created_at)).all())


# --- Alertas: deduplicación y ciclo de vida ------------------------------------------------

def test_la_misma_incidencia_no_crea_otra_alerta(db):
    a = channel_alerts.raise_alert(db, "order_sense_match", "order:1", "m1")
    b = channel_alerts.raise_alert(db, "order_sense_match", "order:1", "m1 actualizado")
    db.commit()
    assert a.id == b.id and len(_alerts(db)) == 1 and _alerts(db)[0].message == "m1 actualizado"


def test_resuelta_que_reaparece_se_reabre_y_descartada_no(db):
    a = channel_alerts.raise_alert(db, "listing_error", "item:1", "falla")
    channel_alerts.set_status(db, a.id, "resolved")
    again = channel_alerts.raise_alert(db, "listing_error", "item:1", "falla otra vez")
    assert again.status == "open" and again.occurrences == 2 and again.resolved_at is None

    channel_alerts.set_status(db, a.id, "dismissed")
    channel_alerts.raise_alert(db, "listing_error", "item:1", "sigue fallando")
    db.commit()
    assert _alerts(db)[0].status == "dismissed"  # el usuario la descartó: no se reabre sola


def test_resolve_alerts_por_clave_y_por_conjunto_vigente(db):
    for k in ("a", "b", "c"):
        channel_alerts.raise_alert(db, "audit_price_diff", f"pricediff:{k}", k)
    channel_alerts.raise_alert(db, "listing_error", "item:x", "otro tipo")
    assert channel_alerts.resolve_alerts(db, kind="audit_price_diff", keep_ref_keys={"pricediff:b"}) == 2
    assert channel_alerts.resolve_alerts(db, ref_key="item:x") == 1
    db.commit()
    estado = {a.ref_key: a.status for a in _alerts(db)}
    assert estado == {"pricediff:a": "resolved", "pricediff:b": "open", "pricediff:c": "resolved", "item:x": "resolved"}


def test_listado_filtra_y_cuenta_abiertas_por_severidad(db):
    channel_alerts.raise_alert(db, "order_conflict", "o:1", "x", severity="error")
    channel_alerts.raise_alert(db, "audit_price_diff", "p:1", "y", severity="warning")
    channel_alerts.raise_alert(db, "audit_price_diff", "p:2", "z", severity="warning")
    channel_alerts.set_status(db, channel_alerts.raise_alert(db, "x", "k", "w").id, "resolved")
    db.commit()
    assert channel_alerts.open_counts(db) == {"error": 1, "warning": 2}
    total, rows = channel_alerts.list_alerts(db, status="open", kind="audit_price_diff")
    assert total == 2 and len(rows) == 2


# --- Avisos por correo ------------------------------------------------------------------------

@pytest.fixture
def mails(monkeypatch):
    enviados = []
    monkeypatch.setattr(
        channel_notifications, "send_email", lambda to, subject, body, tenant, db: enviados.append((to, subject, body))
    )
    return enviados


def _user(db, email, role="admin", active=True):
    u = User(email=email, role=role, active=active)
    db.add(u)
    db.commit()
    return u


def test_por_defecto_nadie_recibe_nada(db, mails):
    _user(db, "ana@x.com")
    channel_alerts.raise_alert(db, "order_conflict", "o:1", "conflicto")
    assert channel_notifications.send_pending(db) == 0 and mails == []


def test_cada_usuario_recibe_solo_los_eventos_que_activo_y_agrupados(db, mails):
    ana, bob = _user(db, "ana@x.com"), _user(db, "bob@x.com")
    channel_notifications.set_prefs(db, ana.id, {"order_issue": True})
    channel_notifications.set_prefs(db, bob.id, {"listing_error": True, "order_issue": False})
    for n in range(3):
        channel_alerts.raise_alert(db, "order_sense_match", f"o:{n}", f"pedido {n} sin coincidencia")
    channel_alerts.raise_alert(db, "listing_error", "item:1", "no se pudo publicar X")

    assert channel_notifications.send_pending(db) == 2
    por_destinatario = {to: (subject, body) for to, subject, body in mails}
    assert set(por_destinatario) == {"ana@x.com", "bob@x.com"}
    assert "3 incidència" in por_destinatario["ana@x.com"][0]
    assert por_destinatario["ana@x.com"][1].count("- pedido") == 3  # un solo correo con las tres
    assert "no se pudo publicar X" in por_destinatario["bob@x.com"][1] and "pedido" not in por_destinatario["bob@x.com"][1]
    assert channel_notifications.send_pending(db) == 0  # la cola se vacía


def test_no_se_avisa_a_usuarios_no_admin_ni_inactivos(db, mails):
    cliente, inactivo = _user(db, "c@x.com", role="cliente"), _user(db, "i@x.com", active=False)
    for u in (cliente, inactivo):
        channel_notifications.set_prefs(db, u.id, {"order_issue": True})
    channel_alerts.raise_alert(db, "order_conflict", "o:1", "x")
    assert channel_notifications.send_pending(db) == 0 and mails == []


def test_nuevos_pedidos_un_solo_correo_aunque_lleguen_varios(db, mails):
    ana = _user(db, "ana@x.com")
    channel_notifications.set_prefs(db, ana.id, {"new_order": True})
    n = channel_notifications.notify_new_orders(db, [{"id": "1-1", "buyer": "fan", "total": 20.0},
                                                    {"id": "1-2", "buyer": "otro", "total": 5.5}])
    assert n == 1 and len(mails) == 1 and "2 comanda" in mails[0][1] and "1-2" in mails[0][2]
    assert channel_notifications.notify_new_orders(db, []) == 0


def test_alertas_con_notify_false_no_envian_correo(db, mails):
    ana = _user(db, "ana@x.com")
    channel_notifications.set_prefs(db, ana.id, {"audit_discrepancies": True})
    channel_alerts.raise_alert(db, "audit_price_diff", "p:1", "x", notify=False)
    assert channel_notifications.send_pending(db) == 0


def test_un_fallo_de_envio_no_rompe_el_resto(db, monkeypatch):
    a, b = _user(db, "a@x.com"), _user(db, "b@x.com")
    for u in (a, b):
        channel_notifications.set_prefs(db, u.id, {"sync_failed": True})
    enviados = []

    def flaky(to, subject, body, tenant, db_):
        if to == "a@x.com":
            raise RuntimeError("smtp caído")
        enviados.append(to)

    monkeypatch.setattr(channel_notifications, "send_email", flaky)
    channel_alerts.raise_alert(db, "sync_failed", "job:1", "fallo")
    assert channel_notifications.send_pending(db) == 1 and enviados == ["b@x.com"]


def test_preferencias_validan_claves_y_son_por_usuario(db):
    ana, bob = _user(db, "ana@x.com"), _user(db, "bob@x.com")
    assert not any(channel_notifications.get_prefs(db, ana.id).values())
    channel_notifications.set_prefs(db, ana.id, {"new_order": True, "inventada": True})
    assert channel_notifications.get_prefs(db, ana.id)["new_order"] is True
    assert "inventada" not in channel_notifications.get_prefs(db, ana.id)
    assert channel_notifications.get_prefs(db, bob.id)["new_order"] is False
    channel_notifications.set_prefs(db, ana.id, {"new_order": False})
    assert channel_notifications.get_prefs(db, ana.id)["new_order"] is False


# --- Integración con pedidos y aplicador --------------------------------------------------------

def _item(db, codi=None, status=ItemStatus.disponible, condition=CondicionItem.segona_ma, quantity=1, rid=1):
    r = Release(artista="A", title="T", formato="LP", discogs_release_id=rid)
    db.add(r)
    db.flush()
    it = Item(release_id=r.id, price=D("20.00"), condition=condition, status=status, quantity=quantity)
    db.add(it)
    db.flush()
    if codi:
        it.codi_discogs = codi
    db.commit()
    return it


def _tenant(db):
    return db.scalar(select(Tenant))


def test_pedido_sin_coincidencia_genera_alerta_y_aviso(db, mails, monkeypatch):
    ana = _user(db, "ana@x.com")
    channel_notifications.set_prefs(db, ana.id, {"order_issue": True})
    db.commit()
    monkeypatch.setattr(discogs_sync, "get_tenant_secrets", lambda tid: TenantSecrets(discogs_token_prod="tok"))
    monkeypatch.setattr(
        channel_orders, "fetch_open_discogs_orders",
        lambda token, **k: [{"id": "9-1", "status": "New Order", "buyer": {"username": "fan"}, "items": [{"id": 777}]}],
    )
    channel_orders.pull_orders(db, _tenant(db))
    (a,) = _alerts(db)
    assert a.kind == "order_sense_match" and a.severity == "error" and a.external_id == "9-1"
    assert len(mails) == 1 and "9-1" in mails[0][2]

    channel_orders.pull_orders(db, _tenant(db), full=True)  # se vuelve a ver: no se duplica ni se vuelve a avisar
    assert len(_alerts(db)) == 1 and len(mails) == 1


def test_fallo_del_sondeo_abre_alerta_y_se_cierra_al_recuperarse(db, mails, monkeypatch):
    monkeypatch.setattr(discogs_sync, "get_tenant_secrets", lambda tid: TenantSecrets(discogs_token_prod="tok"))
    estado = {"boom": True}

    def fetch(token, **k):
        if estado["boom"]:
            raise httpx.ConnectError("sin red")
        return []

    monkeypatch.setattr(channel_orders, "fetch_open_discogs_orders", fetch)
    with pytest.raises(channel_orders.OrdersPullError):
        channel_orders.pull_orders(db, _tenant(db))
    assert [(a.kind, a.status) for a in _alerts(db)] == [("orders_poll_failed", "open")]

    estado["boom"] = False
    channel_orders.pull_orders(db, _tenant(db))
    assert [(a.kind, a.status) for a in _alerts(db)] == [("orders_poll_failed", "resolved")]


# --- Auditoría ---------------------------------------------------------------------------------

@pytest.fixture
def discogs(monkeypatch):
    state = {"listings": []}
    monkeypatch.setattr(discogs_sync, "get_tenant_secrets", lambda tid: TenantSecrets(discogs_token_prod="tok"))
    monkeypatch.setattr(channel_audit, "_fetch_username", lambda token: "la-botiga")
    monkeypatch.setattr(channel_audit, "_fetch_inventory", lambda token, user, limit=0, on_page=None: state["listings"])
    return state


def _listing(codi, precio="20.00"):
    return {"id": codi, "price": {"value": precio}, "release": {"id": codi, "description": "X - Y"}}


def _published(db, codi, price="20.00"):
    it = _item(db, codi=codi)  # el reflejo automático ya crea el vínculo "publicat" al asignar codi_discogs
    db.scalar(select(ChannelListing).where(ChannelListing.item_id == it.id)).published_price = D(price)
    db.commit()
    return it


def _adopcion(db):
    marcar_adopcio_feta(db, {})
    db.commit()


def test_auditoria_detecta_las_tres_diferencias(db, discogs):
    _adopcion(db)
    ok = _published(db, 1)
    precio = _published(db, 2, price="20.00")
    perdido = _published(db, 3)
    discogs["listings"] = [_listing(1), _listing(2, "25.00"), _listing(99)]  # 99: huérfano; 3 ya no está

    res = run_audit(db, _tenant(db), log_fn=lambda m: None)
    s = res.summary
    assert (s["orfes"], s["no_a_discogs"], s["preus"]) == (1, 1, 1) and s["listings_discogs"] == 3 and s["publicats_app"] == 3
    assert {r["accio"] for r in res.rows} == {"orfe_discogs", "no_a_discogs", "preu_diferent"}
    por_kind = {a.kind: a for a in _alerts(db) if a.kind != "audit_summary"}
    assert por_kind["audit_orphan_listing"].external_id == "99"
    assert por_kind["audit_missing_listing"].item_id == perdido.id
    assert por_kind["audit_price_diff"].item_id == precio.id and por_kind["audit_price_diff"].detail == {"app": 20.0, "discogs": 25.0}
    assert ok.id not in {a.item_id for a in _alerts(db)}


def test_auditoria_cierra_sola_las_alertas_que_ya_no_aplican(db, discogs):
    _adopcion(db)
    _published(db, 2)
    discogs["listings"] = [_listing(2, "25.00"), _listing(99)]
    run_audit(db, _tenant(db), log_fn=lambda m: None)
    assert sum(a.status == "open" for a in _alerts(db)) == 3  # huérfano + precio + resumen

    discogs["listings"] = [_listing(2, "20.00")]  # alguien lo arregló
    res = run_audit(db, _tenant(db), log_fn=lambda m: None)
    assert res.summary["orfes"] == res.summary["preus"] == 0
    assert all(a.status == "resolved" for a in _alerts(db))


def test_auditoria_resumen_unico_y_un_solo_aviso_aunque_persistan(db, discogs, mails):
    ana = _user(db, "ana@x.com")
    channel_notifications.set_prefs(db, ana.id, {"audit_discrepancies": True})
    _adopcion(db)
    discogs["listings"] = [_listing(c) for c in (91, 92, 93)]
    run_audit(db, _tenant(db), log_fn=lambda m: None)
    channel_notifications.send_pending(db)
    assert len(mails) == 1 and "3 diferències" in mails[0][2]

    run_audit(db, _tenant(db), log_fn=lambda m: None)  # las diferencias persisten: no hay otro correo
    channel_notifications.send_pending(db)
    assert len(mails) == 1


def test_auditoria_limita_las_alertas_individuales_pero_cuenta_todo(db, discogs, monkeypatch):
    monkeypatch.setattr(channel_audit, "MAX_ALERTS_PER_KIND", 5)
    _adopcion(db)
    discogs["listings"] = [_listing(c) for c in range(1000, 1012)]
    res = run_audit(db, _tenant(db), log_fn=lambda m: None)
    assert res.summary["orfes"] == 12 and len(res.rows) == 12
    assert sum(a.kind == "audit_orphan_listing" for a in _alerts(db)) == 5


def test_auditoria_exige_adopcion_y_token_pero_funciona_en_solo_lectura(db, discogs, monkeypatch):
    with pytest.raises(AuditAbort, match="càrrega inicial"):
        run_audit(db, _tenant(db), log_fn=lambda m: None)
    _adopcion(db)
    db.scalar(select(ConfiguracioBotiga)).discogs_solo_lectura = True  # solo lee de Discogs
    db.commit()
    assert run_audit(db, _tenant(db), log_fn=lambda m: None).summary["orfes"] == 0
    monkeypatch.setattr(discogs_sync, "get_tenant_secrets", lambda tid: TenantSecrets())
    with pytest.raises(AuditAbort, match="token"):
        run_audit(db, _tenant(db), log_fn=lambda m: None)


# --- Endpoints --------------------------------------------------------------------------------

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


def test_endpoint_alertas_lista_y_actua(db, client, admin):
    a = channel_alerts.raise_alert(db, "order_conflict", "o:1", "conflicto", severity="error")
    channel_alerts.raise_alert(db, "audit_price_diff", "p:1", "precio")
    db.commit()
    d = client.get(f"{BASE}/alerts", headers=admin).json()
    assert d["total"] == 2 and d["open"] == {"error": 1, "warning": 1}
    assert client.get(f"{BASE}/alerts?kind=order_conflict", headers=admin).json()["total"] == 1

    r = client.post(f"{BASE}/alerts/{a.id}", json={"action": "dismiss"}, headers=admin).json()
    assert r["status"] == "dismissed"
    assert client.get(f"{BASE}/alerts", headers=admin).json()["total"] == 1
    assert client.get(f"{BASE}/alerts?status=dismissed", headers=admin).json()["total"] == 1
    assert client.get(f"{BASE}/alerts?status=all", headers=admin).json()["total"] == 2
    assert client.post(f"{BASE}/alerts/{a.id}", json={"action": "reopen"}, headers=admin).json()["status"] == "open"
    assert client.post(f"{BASE}/alerts/{a.id}", json={"action": "boom"}, headers=admin).status_code == 422
    assert client.post(f"{BASE}/alerts/00000000-0000-0000-0000-000000000000", json={"action": "resolve"}, headers=admin).status_code == 404


def test_endpoint_preferencias_de_aviso_son_del_usuario_que_las_cambia(db, client, admin):
    d = client.get(f"{BASE}/notifications", headers=admin).json()
    assert [e["key"] for e in d["events"]] == ["new_order", "order_issue", "listing_error", "sync_failed", "audit_discrepancies"]
    assert not any(e["enabled"] for e in d["events"])

    d = client.put(f"{BASE}/notifications", json={"prefs": {"new_order": True}}, headers=admin).json()
    assert {e["key"]: e["enabled"] for e in d["events"]}["new_order"] is True
    assert client.put(f"{BASE}/notifications", json={"prefs": {"inventado": True}}, headers=admin).status_code == 422

    otro = _login(client, "otro@example.com")
    db.scalar(select(User).where(User.email == "otro@example.com")).role = "admin"
    db.commit()
    d2 = client.get(f"{BASE}/notifications", headers={"Authorization": f"Bearer {otro}"}).json()
    assert not any(e["enabled"] for e in d2["events"])  # las preferencias de uno no afectan a otro


def test_endpoint_auditoria_lanza_trabajo_y_resuelve_condiciones(db, client, admin, discogs, monkeypatch):
    store = jobs.MemoryKV()
    monkeypatch.setattr(jobs, "_kv", lambda: store)
    monkeypatch.setattr("app.routers.admin.channel_discogs.audit_task.delay", lambda t, j: audit_task(t, j))
    monkeypatch.setattr("app.routers.admin.channel_discogs.get_discogs_token_if_enabled", lambda db_, tid: "tok")

    assert client.post(f"{BASE}/audit", headers=admin).status_code == 409  # sin carga inicial
    _adopcion(db)
    discogs["listings"] = [_listing(99)]
    assert client.post(f"{BASE}/audit", headers=admin).status_code == 202
    job = client.get("/admin/discogs/inventory/jobs/current", headers=admin).json()["job"]
    assert job["mode"] == "audit" and job["status"] == "done" and job["summary"]["orfes"] == 1
    runs = client.get("/admin/discogs/inventory/runs", headers=admin).json()
    assert runs[0]["kind"] == "audit"
    ov = client.get(f"{BASE}/overview", headers=admin).json()
    assert ov["alertes_obertes"]["warning"] >= 1


def test_fallo_inesperado_o_programado_de_un_trabajo_genera_alerta(db, monkeypatch, mails):
    from app.tasks import discogs as tasks

    store = jobs.MemoryKV()
    monkeypatch.setattr(jobs, "_kv", lambda: store)
    ana = _user(db, "ana@x.com")
    channel_notifications.set_prefs(db, ana.id, {"sync_failed": True})
    db.commit()
    tid = str(_tenant(db).id)

    def boom(*a, **k):
        raise RuntimeError("explotó")

    job = jobs.start_job(tid, "reconcile", {"actor": "x"})
    tasks._execute(tid, job["id"], boom)
    (a,) = _alerts(db)
    assert a.kind == "sync_failed" and a.severity == "error" and "explotó" in a.message
    assert len(mails) == 1

    # un aborto lanzado por una persona NO genera alerta (ya lo ve en pantalla); el programado sí
    def abort(*a, **k):
        raise tasks.ReconcileAbort("freno")

    manual = jobs.start_job(tid, "reconcile", {"actor": "x"})
    tasks._execute(tid, manual["id"], abort)
    programado = jobs.start_job(tid, "reconcile", {"actor": "sistema", "scheduled": True})
    tasks._execute(tid, programado["id"], abort)
    assert [x.ref_key for x in _alerts(db)] == [f"job:{job['id']}", f"job:{programado['id']}"]
