"""Registro de actividad de los canales (channel_events): cada intento de escribir
en Discogs deja una fila, también cuando no se escribe (modo solo lectura)."""

import contextlib
import io
import re
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from app.models import ChannelEvent, ConfiguracioBotiga, Item, Release, User
from app.services import discogs, discogs_sync
from app.services.channel_events import record_event
from app.services.discogs import ReadOnlyToken
from app.tenant_secrets import TenantSecrets


def _events(db):
    db.expire_all()
    return list(db.scalars(select(ChannelEvent).order_by(ChannelEvent.created_at)).all())


def _item(db, codi=None):
    r = Release(artista="A", title="T", formato="LP", discogs_release_id=123)
    db.add(r)
    db.flush()
    it = Item(release_id=r.id, price=Decimal("10.00"))
    db.add(it)
    db.flush()
    if codi:
        it.codi_discogs = codi
    db.commit()
    return it


class _FakeClient:
    """Sustituye al cliente HTTP: devuelve la respuesta que fije el test."""

    def __init__(self, status=201, json_body=None, text="", boom=None):
        self.status, self.body, self.text_, self.boom = status, json_body or {}, text, boom

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def _resp(self):
        if self.boom:
            raise self.boom
        request = httpx.Request("POST", "https://api.discogs.com/x")
        if self.text_:
            return httpx.Response(self.status, text=self.text_, request=request)
        return httpx.Response(self.status, json=self.body, request=request)

    post = delete = lambda self, *a, **k: self._resp()


@pytest.fixture
def fake_http(monkeypatch):
    monkeypatch.setattr(discogs_sync, "_throttle", lambda *a, **k: None)

    def install(**kw):
        monkeypatch.setattr(discogs_sync, "_client", lambda token: _FakeClient(**kw))

    return install


def test_publicar_ok_registra_evento_con_el_listing(db, fake_http):
    it = _item(db)
    fake_http(status=201, json_body={"listing_id": 777})
    assert discogs_sync.push_item_to_discogs("tok", it.id, 123, 10.0, None, None, db=db, actor="ana@x.com") == 777
    db.commit()
    (e,) = _events(db)
    assert (e.action, e.outcome, e.external_id, e.actor, e.item_id) == ("publish", "ok", "777", "ana@x.com", it.id)
    assert e.detail["price"] == 10.0 and e.channel == "discogs"


def test_publicar_rechazado_registra_error(db, fake_http):
    it = _item(db)
    fake_http(status=422, text="seller settings incomplete")
    assert discogs_sync.push_item_to_discogs("tok", it.id, 123, 10.0, None, None, db=db) is None
    db.commit()
    (e,) = _events(db)
    assert (e.outcome, e.actor) == ("error", "sistema") and "422" in e.error and "seller" in e.error


def test_publicar_con_excepcion_de_red_registra_error(db, fake_http):
    it = _item(db)
    fake_http(boom=httpx.ConnectError("sin red"))
    assert discogs_sync.push_item_to_discogs("tok", it.id, 123, 10.0, None, None, db=db) is None
    db.commit()
    assert _events(db)[0].outcome == "error" and "sin red" in _events(db)[0].error


def test_solo_lectura_registra_skipped_sin_llamar_a_discogs(db, monkeypatch):
    monkeypatch.setattr(discogs_sync, "_client", lambda t: pytest.fail("no debe llamar a Discogs"))
    it = _item(db)
    ro = ReadOnlyToken("tok")
    assert discogs_sync.push_item_to_discogs(ro, it.id, 123, 10.0, None, None, db=db) is None
    assert discogs_sync.remove_item_from_discogs(ro, 555, db=db, item_id=it.id) is False
    assert discogs_sync.push_shipped_status(ro, "1-1", "T", "C", db=db) is False
    db.commit()
    assert [(e.action, e.outcome) for e in _events(db)] == [
        ("publish", "skipped"), ("remove", "skipped"), ("ship", "skipped"),
    ]
    assert "només lectura" in _events(db)[0].detail["motiu"]


def test_retirar_ok_y_error(db, fake_http):
    it = _item(db)
    fake_http(status=204)
    assert discogs_sync.remove_item_from_discogs("tok", 555, db=db, item_id=it.id) is True
    fake_http(status=500)
    assert discogs_sync.remove_item_from_discogs("tok", 555, db=db, item_id=it.id) is False
    db.commit()
    assert [(e.action, e.outcome, e.external_id) for e in _events(db)] == [
        ("remove", "ok", "555"), ("remove", "error", "555"),
    ]


def test_marcar_enviado_registra_ok_con_seguimiento(db, fake_http):
    fake_http(status=201)
    assert discogs_sync.push_shipped_status("tok", "99-1", "TRACK1", "Correos", db=db) is True
    db.commit()
    (e,) = _events(db)
    assert (e.action, e.outcome, e.external_id) == ("ship", "ok", "99-1")
    assert e.detail == {"seguiment": "TRACK1", "transportista": "Correos"}


def test_sin_token_o_sin_db_no_registra_nada(db, fake_http):
    it = _item(db)
    assert discogs_sync.push_item_to_discogs(None, it.id, 123, 10.0, None, None, db=db) is None
    fake_http(status=204)
    assert discogs_sync.remove_item_from_discogs("tok", 5) is True  # sin db: no registra
    db.commit()
    assert _events(db) == []


def test_record_event_nunca_rompe_la_operacion():
    record_event(None, "publish", "ok")  # sin db: no hace nada
    record_event(object(), "publish", "ok")  # db inválida: solo traza, no lanza


# --- Endpoints manuales: actor = usuario admin ----------------------------------------

def _login(client, email):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert client.post("/auth/magic-link", json={"email": email}).status_code == 202
    token = re.search(r"token=([\w\-]+)", buf.getvalue()).group(1)
    return client.post(f"/auth/magic-link/verify?token={token}").json()["access_token"]


def test_endpoint_manual_de_publicar_registra_al_usuario(db, client, monkeypatch, fake_http):
    monkeypatch.setattr(discogs_sync, "get_tenant_secrets", lambda tid: TenantSecrets(discogs_token_prod="tok"))
    access = _login(client, "ana@example.com")
    db.scalar(select(User).where(User.email == "ana@example.com")).role = "admin"
    db.commit()
    it = _item(db)
    fake_http(status=201, json_body={"listing_id": 888})

    resp = client.post(f"/admin/discogs/sync/items/{it.id}/push", headers={"Authorization": f"Bearer {access}"})
    assert resp.status_code == 200 and resp.json()["codi_discogs"] == 888
    (e,) = _events(db)
    assert (e.action, e.outcome, e.actor) == ("publish", "ok", "ana@example.com")
