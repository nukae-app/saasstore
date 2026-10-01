"""Sondeo incremental de pedidos de Discogs (services/channel_orders.py) e incidencias."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from app.models import (
    ChannelEvent, ConfiguracioBotiga, CondicionItem, Item, ItemStatus, Order, OrderOrigen, OrderStatus, Release, Tenant,
)
from app.services import channel_orders, discogs_sync
from app.services.channel_orders import OrdersPullError, is_due, pull_orders
from app.services.channel_settings import get_settings
from app.tasks.discogs import orders_poll
from app.tenant_secrets import TenantSecrets

UTC = timezone.utc


def _order(oid="1-1", status="New Order", listing=None, last_activity=None, buyer="fan"):
    o = {"id": oid, "status": status, "buyer": {"username": buyer}, "total": {"value": 20.0},
         "items": [{"id": listing}] if listing else [], "shipping_address": "Calle 1"}
    if last_activity:
        o["last_activity"] = last_activity
    return o


def _item(db, codi, condition=CondicionItem.segona_ma, status=ItemStatus.disponible, quantity=1):
    r = Release(artista="A", title="T", formato="LP", discogs_release_id=1)
    db.add(r)
    db.flush()
    it = Item(release_id=r.id, price=Decimal("20.00"), condition=condition, status=status, quantity=quantity)
    db.add(it)
    db.flush()
    it.codi_discogs = codi
    db.commit()
    return it


def _aware(dt):
    """SQLite devuelve fechas sin zona horaria; Postgres con ella."""
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=UTC)


def _tenant(db):
    return db.scalar(select(Tenant))


def _events(db, **filters):
    db.expire_all()
    stmt = select(ChannelEvent).where(ChannelEvent.action == "order_pull")
    return list(db.scalars(stmt.order_by(ChannelEvent.created_at)).all())


@pytest.fixture
def secrets(monkeypatch):
    monkeypatch.setattr(discogs_sync, "get_tenant_secrets", lambda tid: TenantSecrets(discogs_token_prod="tok"))


@pytest.fixture
def feed(monkeypatch, secrets):
    """Pedidos que devuelve Discogs; registra cómo se pidieron."""
    state = {"orders": [], "calls": [], "boom": None}

    def fake_fetch(token, since=None, raise_errors=False, **k):
        state["calls"].append(since)
        if state["boom"]:
            raise state["boom"]
        return state["orders"]

    monkeypatch.setattr(channel_orders, "fetch_open_discogs_orders", fake_fetch)
    return state


# --- Mapeo de estados ---------------------------------------------------------------------

def test_in_progress_se_mapea_a_pagado(db, feed):
    _item(db, 5)
    feed["orders"] = [_order(listing=5, status="In Progress")]
    r = pull_orders(db, _tenant(db))
    assert r["creats"] == 1 and r["estats_desconeguts"] == []
    assert db.scalar(select(Order)).status == OrderStatus.pagado


def test_estado_desconocido_queda_registrado_una_sola_vez(db, feed):
    feed["orders"] = [_order(status="Estado Raro")]
    for _ in range(3):
        r = pull_orders(db, _tenant(db))
    assert r["estats_desconeguts"] == ["Estado Raro"]
    ev = _events(db)
    assert len(ev) == 1 and ev[0].outcome == "skipped" and ev[0].detail["status"] == "Estado Raro"


# --- Incidencias ---------------------------------------------------------------------------

def test_pedido_sin_coincidencia_se_registra_una_vez_aunque_se_repita_el_sondeo(db, feed):
    feed["orders"] = [_order(listing=999999)]
    for _ in range(3):
        r = pull_orders(db, _tenant(db))
    assert r["sense_match"] == 1 and r["sense_match_ids"] == ["1-1"]
    (e,) = _events(db)
    assert e.outcome == "error" and e.detail["kind"] == "sense_match" and e.detail["listings"] == [999999]
    assert db.scalar(select(Order)) is None


def test_conflicto_si_discogs_vende_algo_que_la_app_ya_no_tenia_a_la_venta(db, feed):
    vendido = _item(db, 7, status=ItemStatus.vendido)
    feed["orders"] = [_order(listing=7)]
    r = pull_orders(db, _tenant(db))
    assert r["creats"] == 1 and r["conflictes"] == 1
    order = db.scalar(select(Order))  # el pedido se crea igualmente
    assert order.origin == OrderOrigen.discogs
    (e,) = [x for x in _events(db) if (x.detail or {}).get("kind") == "conflict"]
    assert e.detail["items"] == [str(vendido.id)] and e.order_id == order.id


def test_nou_sin_stock_tambien_es_conflicto_y_con_stock_no(db, feed):
    _item(db, 1, condition=CondicionItem.nou, quantity=0)
    _item(db, 2, condition=CondicionItem.nou, quantity=3)
    feed["orders"] = [_order("a-1", listing=1), _order("b-1", listing=2)]
    assert pull_orders(db, _tenant(db))["conflictes"] == 1


def test_un_pedido_normal_no_genera_incidencias(db, feed):
    _item(db, 3)
    feed["orders"] = [_order(listing=3)]
    pull_orders(db, _tenant(db))
    assert [e.detail.get("kind") for e in _events(db)] == [None]  # solo el evento resumen "ok"


# --- Cursor e incrementalidad --------------------------------------------------------------

def test_primera_vez_sin_cursor_y_despues_usa_el_cursor(db, feed):
    _item(db, 3)
    feed["orders"] = [_order(listing=3, last_activity="2026-10-01T10:00:00+00:00")]
    pull_orders(db, _tenant(db))
    assert feed["calls"][0] is None  # primera vez: sin cursor
    assert _aware(get_settings(db).orders_cursor) == datetime(2026, 10, 1, 10, 0, tzinfo=UTC)

    feed["orders"] = []
    pull_orders(db, _tenant(db))
    assert feed["calls"][1] == datetime(2026, 10, 1, 10, 0, tzinfo=UTC)
    assert _aware(get_settings(db).orders_cursor) == datetime(2026, 10, 1, 10, 0, tzinfo=UTC)  # sin pedidos: se conserva


def test_completa_ignora_el_cursor(db, feed):
    get_settings(db).orders_cursor = datetime(2026, 10, 1, tzinfo=UTC)
    db.commit()
    pull_orders(db, _tenant(db), full=True)
    assert feed["calls"] == [None]


def test_el_cursor_no_avanza_si_algun_pedido_falla(db, feed, monkeypatch):
    feed["orders"] = [_order(last_activity="2026-10-02T10:00:00+00:00")]
    monkeypatch.setattr(
        channel_orders, "sync_discogs_orders",
        lambda db_, token, orders: {"creats": 0, "actualitzats": 0, "sense_match": 0, "errors": 1,
                                    "conflictes": 0, "estats_desconeguts": [], "sense_match_ids": []},
    )
    pull_orders(db, _tenant(db))
    assert get_settings(db).orders_cursor is None
    assert [e.outcome for e in _events(db)] == ["error"]


def test_error_de_discogs_se_guarda_y_se_propaga(db, feed):
    feed["boom"] = httpx.ConnectError("sin red")
    with pytest.raises(OrdersPullError, match="sin red"):
        pull_orders(db, _tenant(db))
    s = get_settings(db)
    assert "sin red" in s.orders_last_result["error"] and s.orders_last_pull_at is not None and s.orders_cursor is None
    assert _events(db)[0].detail["kind"] == "fetch"


def test_sin_token_o_discogs_apagado_no_se_puede_sondear(db, monkeypatch):
    monkeypatch.setattr(discogs_sync, "get_tenant_secrets", lambda tid: TenantSecrets())
    with pytest.raises(OrdersPullError, match="token"):
        pull_orders(db, _tenant(db))


def test_resultado_y_hora_quedan_en_los_ajustes(db, feed):
    _item(db, 3)
    feed["orders"] = [_order(listing=3)]
    pull_orders(db, _tenant(db), now=datetime(2026, 10, 1, 12, 0, tzinfo=UTC))
    s = get_settings(db)
    assert _aware(s.orders_last_pull_at) == datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    assert s.orders_last_result["creats"] == 1 and s.orders_last_result["orders_fetched"] == 1


def test_is_due_respeta_la_frecuencia(db):
    s = get_settings(db)
    now = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    assert is_due(s, now)  # nunca se ha sondeado
    s.orders_last_pull_at = now - timedelta(minutes=9)
    assert not is_due(s, now)
    s.orders_last_pull_at = now - timedelta(minutes=10)
    assert is_due(s, now)


# --- Descarga incremental (paginación y parada) ---------------------------------------------

class _FakeHTTP:
    def __init__(self, pages, record):
        self.pages, self.record = pages, record

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, path, params=None):
        self.record.append(dict(params))
        page = self.pages[params["page"] - 1]
        body = {"orders": page, "pagination": {"pages": len(self.pages)}}
        return httpx.Response(200, json=body, request=httpx.Request("GET", "https://api.discogs.com" + path))


def _fetch_with(monkeypatch, pages, **kw):
    record = []
    monkeypatch.setattr(discogs_sync, "_throttle", lambda *a, **k: None)
    monkeypatch.setattr(discogs_sync, "_client", lambda token: _FakeHTTP(pages, record))
    return discogs_sync.fetch_open_discogs_orders("tok", **kw), record


def test_primera_descarga_pide_solo_los_ultimos_dias_y_ordena_por_actividad(monkeypatch):
    orders, rec = _fetch_with(monkeypatch, [[_order("1")], [_order("2")]])
    assert [o["id"] for o in orders] == ["1", "2"]
    assert rec[0]["sort"] == "last_activity" and rec[0]["sort_order"] == "desc"
    expected = (datetime.now(UTC) - timedelta(days=60)).date().isoformat()
    assert rec[0]["created_after"] == expected


def test_descarga_incremental_se_para_al_llegar_a_actividad_antigua(monkeypatch):
    since = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    page1 = [_order("new", last_activity="2026-10-01T13:00:00+00:00"),
             _order("old", last_activity="2026-10-01T09:00:00+00:00")]  # anterior al cursor - 15 min
    page2 = [_order("older", last_activity="2026-09-01T09:00:00+00:00")]
    orders, rec = _fetch_with(monkeypatch, [page1, page2], since=since)
    assert [o["id"] for o in orders] == ["new", "old"] and len(rec) == 1  # no pidió la página 2
    assert "created_after" not in rec[0]


def test_descarga_incremental_sigue_si_la_pagina_aun_es_reciente(monkeypatch):
    since = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    page1 = [_order("a", last_activity="2026-10-01T13:00:00+00:00")]
    page2 = [_order("b", last_activity="2026-10-01T12:30:00+00:00")]
    orders, rec = _fetch_with(monkeypatch, [page1, page2], since=since)
    assert len(orders) == 2 and len(rec) == 2


def test_descarga_sin_campo_de_actividad_no_se_para_antes_de_tiempo(monkeypatch):
    since = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    orders, rec = _fetch_with(monkeypatch, [[_order("a")], [_order("b")]], since=since)
    assert len(orders) == 2 and len(rec) == 2


def test_errores_de_descarga_son_best_effort_salvo_que_se_pida_propagarlos(monkeypatch):
    def boom_client(token):
        raise httpx.ConnectError("sin red")

    monkeypatch.setattr(discogs_sync, "_throttle", lambda *a, **k: None)
    monkeypatch.setattr(discogs_sync, "_client", boom_client)
    assert discogs_sync.fetch_open_discogs_orders("tok") == []
    with pytest.raises(httpx.ConnectError):
        discogs_sync.fetch_open_discogs_orders("tok", raise_errors=True)


# --- Tarea programada ----------------------------------------------------------------------

def _adopcion(db):
    from app.services.discogs_sync import marcar_adopcio_feta

    marcar_adopcio_feta(db, {})
    db.commit()


def test_tarea_programada_sondea_solo_tras_la_adopcion_y_cuando_toca(db, feed):
    _item(db, 3)
    feed["orders"] = [_order(listing=3)]
    assert orders_poll() == {}  # adopción sin hacer

    _adopcion(db)
    res = orders_poll()
    assert list(res.values())[0]["creats"] == 1

    assert orders_poll() == {}  # recién sondeado: aún no toca (10 min)

    s = get_settings(db)
    s.orders_last_pull_at = datetime.now(UTC) - timedelta(minutes=11)
    db.commit()
    assert len(orders_poll()) == 1


def test_tarea_programada_respeta_el_ajuste_orders_auto_y_funciona_en_solo_lectura(db, feed):
    _adopcion(db)
    get_settings(db).orders_auto = False
    db.commit()
    assert orders_poll() == {}

    get_settings(db).orders_auto = True
    db.scalar(select(ConfiguracioBotiga)).discogs_solo_lectura = True  # bajar pedidos es lectura
    db.commit()
    assert len(orders_poll()) == 1


def test_tarea_programada_no_se_cae_si_discogs_falla(db, feed):
    _adopcion(db)
    feed["boom"] = httpx.ConnectError("sin red")
    res = orders_poll()
    assert "sin red" in list(res.values())[0]["error"]
