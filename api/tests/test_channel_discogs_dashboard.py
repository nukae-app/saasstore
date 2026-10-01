"""Endpoints del centro de control /admin/channels/discogs (Resum, Listings, ajustes, actividad)."""

import contextlib
import io
import re
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import (
    ChannelEvent, ChannelListing, ConfiguracioBotiga, CondicionItem, Item, ItemStatus, Order, OrderOrigen,
    OrderStatus, Release, User,
)

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


def _mk(db, *, artista="A", title="T", rid=123, status=ItemStatus.disponible, condition=CondicionItem.segona_ma,
        quantity=1, price="10.00", codi=None, listing=None, published=None, estado="Near Mint (NM or M-)"):
    r = Release(artista=artista, title=title, formato="LP", discogs_release_id=rid)
    db.add(r)
    db.flush()
    it = Item(release_id=r.id, price=Decimal(price), condition=condition, status=status, quantity=quantity,
              estado_disco=estado)
    db.add(it)
    db.flush()
    if codi:
        it.codi_discogs = codi
    if listing:
        db.add(ChannelListing(item_id=it.id, external_id=str(codi) if codi else None, status=listing,
                              published_price=Decimal(published) if published else None))
    db.commit()
    return it


def test_resumen_cuenta_estados_acciones_y_valor(db, client, admin):
    _mk(db, title="Publicado", codi=1, listing="publicat", published="10.00")
    _mk(db, title="Precio distinto", codi=2, listing="publicat", published="8.00", price="12.00")
    _mk(db, title="Pendiente")
    _mk(db, title="Sin release", rid=None)
    _mk(db, title="Vendido pero publicado", status=ItemStatus.vendido, codi=3, listing="publicat", published="5.00")

    d = client.get(f"{BASE}/overview", headers=admin).json()
    assert d["estat_canal"] == {"publicat": 3, "pendent": 1, "sense_release": 1}
    assert d["accions"] == {"actualitzar_preu": 1, "publicar": 1, "vincular_release": 1, "retirar": 1}
    assert d["valor_publicat"] == 23.0  # 10 + 8 + 5 (precio publicado)
    assert d["items_a_la_venda"] == 5 and d["comandes_obertes"] == 0 and d["ultima_execucio"] is None
    assert d["settings"]["publicacion_auto"] is False and d["settings"]["sync_auto"] is True


def test_resumen_cuenta_pedidos_de_discogs_abiertos_y_errores_recientes(db, client, admin):
    for estado, origen in ((OrderStatus.pagado, OrderOrigen.discogs), (OrderStatus.enviado, OrderOrigen.discogs),
                           (OrderStatus.pagado, OrderOrigen.web)):
        db.add(Order(contact_email="x@y.z", status=estado, total=Decimal("1"), shipping_method="envio", origin=origen))
    db.add(ChannelEvent(action="publish", outcome="error", error="boom"))
    db.add(ChannelEvent(action="publish", outcome="ok"))
    db.commit()
    d = client.get(f"{BASE}/overview", headers=admin).json()
    assert d["comandes_obertes"] == 1 and d["errors_24h"] == 1


def test_listings_filtra_ordena_y_pagina(db, client, admin):
    _mk(db, artista="Zeta", title="Ok", codi=1, listing="publicat", published="10.00")
    _mk(db, artista="Beta", title="Pendiente")
    _mk(db, artista="Alfa", title="Nou", condition=CondicionItem.nou, quantity=2, estado=None)

    todo = client.get(f"{BASE}/listings", headers=admin).json()
    assert todo["total"] == 3
    assert [r["artista"] for r in todo["rows"]] == ["Alfa", "Beta", "Zeta"]  # primero lo que requiere acción
    assert todo["counts_accio"] == {"publicar": 2, "ok": 1}

    pend = client.get(f"{BASE}/listings?estat=pendent", headers=admin).json()
    assert pend["total"] == 2 and pend["counts_estat"] == {"publicat": 1, "pendent": 2}

    assert client.get(f"{BASE}/listings?accio=ok", headers=admin).json()["rows"][0]["artista"] == "Zeta"
    assert client.get(f"{BASE}/listings?condicio=nou", headers=admin).json()["total"] == 1
    assert client.get(f"{BASE}/listings?q=beta", headers=admin).json()["total"] == 1
    assert client.get(f"{BASE}/listings?q=1", headers=admin).json()["total"] >= 1  # busca por id de listing
    assert len(client.get(f"{BASE}/listings?limit=1&offset=1", headers=admin).json()["rows"]) == 1


def test_listings_expone_los_campos_que_necesita_la_tabla(db, client, admin):
    it = _mk(db, codi=7, listing="publicat", published="9.00", price="10.00")
    (row,) = client.get(f"{BASE}/listings", headers=admin).json()["rows"]
    assert row["item_id"] == str(it.id) and row["external_id"] == "7" and row["accio"] == "actualitzar_preu"
    assert row["price"] == 10.0 and row["published_price"] == 9.0 and row["estat_canal"] == "publicat"
    assert row["discogs_release_id"] == 123 and row["condicio"] == "segona_ma"


def test_ajustes_por_defecto_y_actualizacion_parcial(db, client, admin):
    d = client.get(f"{BASE}/settings", headers=admin).json()
    assert d["publicacion_auto"] is False and d["sync_auto"] is True and d["recargo_pct"] == 0.0
    assert d["orders_auto"] is True and d["orders_poll_minutes"] == 10

    d = client.put(f"{BASE}/settings", json={"publicacion_auto": True, "recargo_pct": 12.5}, headers=admin).json()
    assert d["publicacion_auto"] is True and d["recargo_pct"] == 12.5 and d["sync_auto"] is True
    assert client.get(f"{BASE}/settings", headers=admin).json()["publicacion_auto"] is True


@pytest.mark.parametrize("payload", [{"recargo_pct": -1}, {"recargo_pct": 101}, {"orders_poll_minutes": 1},
                                     {"orders_poll_minutes": 1000}])
def test_ajustes_validan_rangos(db, client, admin, payload):
    assert client.put(f"{BASE}/settings", json=payload, headers=admin).status_code == 422


def test_el_recargo_cambia_las_acciones_propuestas(db, client, admin):
    _mk(db, codi=1, listing="publicat", published="10.00", price="10.00")
    assert client.get(f"{BASE}/listings", headers=admin).json()["rows"][0]["accio"] == "ok"
    client.put(f"{BASE}/settings", json={"recargo_pct": 10}, headers=admin)
    row = client.get(f"{BASE}/listings", headers=admin).json()["rows"][0]
    assert row["accio"] == "actualitzar_preu" and row["target_price"] == 11.0


def test_actividad_se_filtra_y_pagina(db, client, admin):
    for outcome in ("ok", "error", "skipped"):
        db.add(ChannelEvent(action="publish", outcome=outcome, actor="ana"))
    db.add(ChannelEvent(action="remove", outcome="ok"))
    db.commit()
    d = client.get(f"{BASE}/events", headers=admin).json()
    assert d["total"] == 4
    assert client.get(f"{BASE}/events?outcome=error", headers=admin).json()["total"] == 1
    assert client.get(f"{BASE}/events?action=remove", headers=admin).json()["total"] == 1
    assert len(client.get(f"{BASE}/events?limit=2", headers=admin).json()["events"]) == 2


def test_requiere_admin_y_discogs_activo(db, client, admin):
    assert client.get(f"{BASE}/overview").status_code in (401, 403)
    db.scalar(select(ConfiguracioBotiga)).discogs_habilitat = False
    db.commit()
    assert client.get(f"{BASE}/overview", headers=admin).status_code == 404
