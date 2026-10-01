"""Precios de mercado de Discogs y reprecio (services/channel_pricing.py y endpoints)."""

import contextlib
import io
import re
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from app.models import ChannelEvent, CondicionItem, Item, ItemStatus, Release, Tenant, User
from app.services import channel_pricing as cp
from app.services import discogs, discogs_jobs as jobs, discogs_sync
from app.services.channel_settings import get_settings
from app.tasks.discogs import pricing_preview
from app.tenant_secrets import TenantSecrets

D = Decimal
BASE = "/admin/channels/discogs/pricing"
SUG = {
    "Mint (M)": {"currency": "EUR", "value": 30.0},
    "Near Mint (NM or M-)": {"currency": "EUR", "value": 20.0},
    "Very Good Plus (VG+)": {"currency": "EUR", "value": 14.0},
}


def _http_error(status, text=""):
    return httpx.HTTPStatusError(
        str(status), request=httpx.Request("GET", "https://api.discogs.com/x"),
        response=httpx.Response(status, text=text),
    )


@pytest.fixture
def market(monkeypatch):
    """Secretos, caché en memoria y respuestas de Discogs falseadas."""
    state = {"sug": SUG, "stats": {"lowest_price": {"value": 9.5, "currency": "EUR"}, "num_for_sale": 4},
             "calls": [], "boom": None}
    store = jobs.MemoryKV()
    monkeypatch.setattr(jobs, "_kv", lambda: store)
    monkeypatch.setattr(discogs_sync, "get_tenant_secrets", lambda tid: TenantSecrets(discogs_token_prod="tok"))

    def get_sug(token, rid):
        state["calls"].append(("sug", rid))
        if state["boom"]:
            raise state["boom"]
        return state["sug"]

    monkeypatch.setattr(discogs, "get_price_suggestions", get_sug)
    monkeypatch.setattr(discogs, "get_release_stats", lambda token, rid: state["calls"].append(("stats", rid)) or state["stats"])
    monkeypatch.setattr(discogs, "get_fee", lambda token, price: {"value": round(price * 0.09, 2), "currency": "EUR"})
    return state


def _mk(db, *, rid=1, price="20.00", estado="Near Mint (NM or M-)", condition=CondicionItem.segona_ma,
        status=ItemStatus.disponible, quantity=1, title="T"):
    r = Release(artista="A", title=title, formato="LP", discogs_release_id=rid)
    db.add(r)
    db.flush()
    it = Item(release_id=r.id, price=D(price), condition=condition, status=status, quantity=quantity,
              estado_disco=estado if condition == CondicionItem.segona_ma else None)
    db.add(it)
    db.commit()
    return it


def _tenant(db):
    return db.scalar(select(Tenant))


# --- Cálculo -----------------------------------------------------------------------------------

def test_clave_de_sugerencia_segun_estado_y_nou_es_mint(db):
    assert cp.condition_key(_mk(db)) == "Near Mint (NM or M-)"
    assert cp.condition_key(_mk(db, estado="Very Good Plus (VG+)")) == "Very Good Plus (VG+)"
    assert cp.condition_key(_mk(db, condition=CondicionItem.nou)) == "Mint (M)"


@pytest.mark.parametrize("valor,paso,esperado", [("13.74", "0.5", "13.50"), ("13.76", "0.5", "14.00"),
                                                  ("13.745", "0", "13.75"), ("9.99", "1", "10.00")])
def test_redondeo(valor, paso, esperado):
    assert cp.round_to(D(valor), D(paso)) == D(esperado)


def test_propuesta_descuenta_el_recargo_del_canal():
    assert cp.propose(D("22.00"), factor=1.0, step=0.5, recargo_pct=10) == D("20.00")
    assert cp.propose(D("20.00"), factor=0.9, step=0.5, recargo_pct=0) == D("18.00")


# --- Consulta con caché -------------------------------------------------------------------------

def test_la_consulta_se_cachea(db, market):
    a = cp.market_for_release("tok", 5)
    b = cp.market_for_release("tok", 5)
    assert a == b and a["suggestions"]["Mint (M)"]["value"] == 30.0 and a["stats"]["num_for_sale"] == 4
    assert market["calls"] == [("sug", 5), ("stats", 5)]  # la segunda no llama a Discogs


def test_ajustes_de_vendedor_incompletos_se_explican(db, market):
    market["boom"] = _http_error(403, "You must fill out your seller settings first")
    with pytest.raises(cp.PricingAbort, match="ajustes de venedor"):
        cp.market_for_release("tok", 5)
    market["boom"] = _http_error(500, "boom")
    with pytest.raises(httpx.HTTPStatusError):
        cp.market_for_release("tok", 6)


# --- Vista previa masiva ------------------------------------------------------------------------

def _run(db, **kw):
    return cp.run_pricing_preview(db, _tenant(db), log_fn=lambda m: None, **kw)


def test_vista_previa_clasifica_puja_baja_igual_y_sin_sugerencia(db, market):
    puja = _mk(db, rid=1, price="15.00")                                  # sugerido 20 -> sube
    baja = _mk(db, rid=2, price="30.00")                                  # sugerido 20 -> baja
    igual = _mk(db, rid=3, price="20.00")                                 # igual
    sin = _mk(db, rid=4, price="10.00", estado="Good (G)")                # Discogs no sugiere G
    res = _run(db)
    por_item = {r["item_id"]: r for r in res.rows}
    assert por_item[puja.id]["accio"] == "repreu_puja" and por_item[puja.id]["preu_proposat"] == D("20.00")
    assert por_item[baja.id]["accio"] == "repreu_baixa"
    assert por_item[igual.id]["accio"] == "igual" and por_item[sin.id]["accio"] == "sense_suggeriment"
    s = res.summary
    assert (s["puja"], s["baixa"], s["igual"], s["sense_suggeriment"], s["errors"]) == (1, 1, 1, 1, 0)
    assert por_item[puja.id]["preu_app"] == D("15.00") and por_item[puja.id]["preu_discogs"] == D("20.0")


def test_umbral_y_factor_y_recargo(db, market):
    _mk(db, rid=1, price="19.00")  # sugerido 20: -5 % de diferencia con el umbral por defecto (5) -> sube
    assert _run(db).rows[0]["accio"] == "repreu_puja"
    assert _run(db, min_diff_pct=10).rows[0]["accio"] == "igual"

    get_settings(db).recargo_pct = D("10")  # con recargo, la app debe valer 20/1,10 = 18,18 -> 18.00
    db.commit()
    assert _run(db).rows[0]["preu_proposat"] == D("18.00")


def test_solo_considera_items_a_la_venta_con_release_vinculado_y_respeta_limite_y_seleccion(db, market):
    a, b = _mk(db, rid=1, title="a"), _mk(db, rid=2, title="b")
    _mk(db, rid=3, status=ItemStatus.vendido)
    _mk(db, rid=None)
    _mk(db, rid=4, condition=CondicionItem.nou, quantity=0)
    assert {r["item_id"] for r in _run(db).rows} == {a.id, b.id}
    assert len(_run(db, limit=1).rows) == 1
    assert [r["item_id"] for r in _run(db, item_ids={b.id}).rows] == [b.id]


def test_moneda_distinta_o_un_release_con_error_no_paran_al_resto(db, market, monkeypatch):
    _mk(db, rid=1)
    _mk(db, rid=2)
    market["sug"] = {"Near Mint (NM or M-)": {"currency": "USD", "value": 20.0}}
    res = _run(db)
    assert {r["accio"] for r in res.rows} == {"error"} and "USD" in res.rows[0]["motiu"]

    market["sug"] = SUG
    original = discogs.get_price_suggestions

    def flaky(token, rid):
        if rid == 1:
            raise _http_error(500, "boom")
        return original(token, rid)

    monkeypatch.setattr(discogs, "get_price_suggestions", flaky)
    jobs._kv().data.clear()
    res = _run(db)
    assert sorted(r["accio"] for r in res.rows) == ["error", "igual"] and res.summary["errors"] == 1


def test_ajustes_de_vendedor_incompletos_abortan_toda_la_vista_previa(db, market):
    _mk(db)
    market["boom"] = _http_error(403, "seller settings")
    with pytest.raises(cp.PricingAbort):
        _run(db)


def test_sin_token_aborta(db, market, monkeypatch):
    monkeypatch.setattr(discogs_sync, "get_tenant_secrets", lambda tid: TenantSecrets())
    with pytest.raises(cp.PricingAbort, match="token"):
        _run(db)


# --- Aplicar ------------------------------------------------------------------------------------

def _rows_for(db, market):
    return [{**r, "item_id": str(r["item_id"]), "preu_app": str(r["preu_app"]),
             "preu_proposat": str(r["preu_proposat"]) if r["preu_proposat"] is not None else None}
            for r in _run(db).rows]


def test_aplicar_cambia_el_precio_en_la_app_y_deja_evento(db, market):
    it = _mk(db, price="15.00")
    rows = _rows_for(db, market)
    res = cp.apply_prices(db, rows, None, "ana@x.com")
    db.commit()
    assert res == {"aplicats": 1, "saltats": []}
    db.refresh(it)
    assert it.price == D("20.00")
    (e,) = db.scalars(select(ChannelEvent).where(ChannelEvent.action == "price_change")).all()
    assert e.actor == "ana@x.com" and e.detail == {"from": 15.0, "to": 20.0, "source": "discogs_suggestion"}


def test_aplicar_salta_lo_que_cambio_o_ya_no_se_vende_y_respeta_la_seleccion(db, market):
    a, b, c = _mk(db, rid=1, price="15.00"), _mk(db, rid=2, price="15.00"), _mk(db, rid=3, price="15.00")
    rows = _rows_for(db, market)
    a.price = D("16.00")  # alguien lo editó después de la simulación
    b.status = ItemStatus.vendido
    db.commit()
    res = cp.apply_prices(db, rows, {str(a.id), str(b.id)}, None)
    motivos = {s["item_id"]: s["motiu"] for s in res["saltats"]}
    assert res["aplicats"] == 0
    assert "ha canviat" in motivos[str(a.id)] and "ja no està a la venda" in motivos[str(b.id)]
    db.refresh(c)
    assert c.price == D("15.00")  # no estaba seleccionado


# --- Endpoints ----------------------------------------------------------------------------------

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


def test_endpoints_de_mercado_y_comision(db, client, admin, market):
    d = client.get(f"{BASE}/release/77", headers=admin).json()
    assert d["suggestions"]["Mint (M)"]["value"] == 30.0 and d["stats"]["lowest_price"]["value"] == 9.5
    assert client.get(f"{BASE}/fee?price=20", headers=admin).json() == {"value": 1.8, "currency": "EUR"}
    assert client.get(f"{BASE}/fee?price=0", headers=admin).status_code == 422
    market["boom"] = _http_error(403, "seller settings")
    assert client.get(f"{BASE}/release/78", headers=admin).status_code == 409


def test_endpoint_vista_previa_y_aplicar_de_extremo_a_extremo(db, client, admin, market, monkeypatch):
    monkeypatch.setattr("app.routers.admin.channel_pricing.pricing_preview.delay", lambda t, j: pricing_preview(t, j))
    it = _mk(db, price="15.00")
    assert client.post(f"{BASE}/preview", json={"limit": 10}, headers=admin).status_code == 202
    job = client.get("/admin/discogs/inventory/jobs/current", headers=admin).json()["job"]
    assert job["mode"] == "pricing_preview" and job["status"] == "done" and job["summary"]["puja"] == 1

    runs = client.get("/admin/discogs/inventory/runs", headers=admin).json()
    assert runs[0]["kind"] == "pricing_preview"

    res = client.post(f"{BASE}/apply", json={"job_id": job["id"]}, headers=admin).json()
    assert res["aplicats"] == 1
    db.expire_all()
    assert db.get(Item, it.id).price == D("20.00")


def test_aplicar_exige_una_simulacion_de_precios_acabada(db, client, admin, market):
    assert client.post(f"{BASE}/apply", json={"job_id": "inexistente"}, headers=admin).status_code == 404


def test_vista_previa_valida_parametros(db, client, admin, market):
    for payload in ({"factor": 0}, {"factor": 5}, {"limit": 0}, {"limit": 100000}, {"min_diff_pct": -1}):
        assert client.post(f"{BASE}/preview", json=payload, headers=admin).status_code == 422
