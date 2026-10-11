"""Pestaña Vincular: cola de releases sin discogs_release_id, candidatos por EAN/texto y vinculación."""

import contextlib
import io
import re
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import CondicionItem, Item, ItemStatus, Release, User
from app.routers.admin import channel_vincular
from app.services import discogs, discogs_link

BASE = "/admin/channels/discogs/vincular"


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


@pytest.fixture(autouse=True)
def fake_discogs(monkeypatch):
    calls = {"barcode": [], "text": []}
    state = {"barcode": {}, "text": []}

    def by_barcode(token, ean, per_page=10):
        calls["barcode"].append(ean)
        return state["barcode"].get(ean, [])

    def by_text(token, query, per_page=10):
        calls["text"].append(query)
        return state["text"]

    monkeypatch.setattr(discogs, "search_by_barcode", by_barcode)
    monkeypatch.setattr(discogs, "search_releases", by_text)
    monkeypatch.setattr(discogs_link, "enrich_release_from_discogs", lambda rel, db, token: (db.commit() or True))
    monkeypatch.setattr(channel_vincular, "get_discogs_token_if_enabled", lambda db, tid: "tok")
    return type("F", (), {"calls": calls, "state": state})


def _mk(db, *, artista="Artista", title="Titol", ean=None, rid=None, status=ItemStatus.disponible):
    r = Release(artista=artista, title=title, formato="LP", ean=ean, discogs_release_id=rid)
    db.add(r)
    db.flush()
    db.add(Item(release_id=r.id, price=Decimal("10"), condition=CondicionItem.nou, status=status, quantity=1))
    db.commit()
    return r


def _hit(i, artista="Artista", titulo="Titol"):
    return {"discogs_release_id": i, "artista": artista, "titulo": titulo}


def test_cua_nomes_te_sense_vincular_amb_estoc_actiu(db, client, admin):
    _mk(db, title="Pendent amb EAN", ean="8435000000011")
    _mk(db, title="Pendent sense EAN")
    _mk(db, title="Ja vinculat", rid=5)
    _mk(db, title="Venut", status=ItemStatus.vendido)

    d = client.get(BASE, headers=admin).json()
    assert {r["titulo"] for r in d["rows"]} == {"Pendent amb EAN", "Pendent sense EAN"}
    assert d["counts"] == {"pendents": 2, "ajornats": 0, "amb_ean": 1, "sense_ean": 1}
    assert [r["titulo"] for r in client.get(f"{BASE}?filtre=amb_ean", headers=admin).json()["rows"]] == ["Pendent amb EAN"]


def test_candidats_primer_per_ean_i_si_no_per_text(db, client, admin, fake_discogs):
    r = _mk(db, ean="8435000000011")
    fake_discogs.state["barcode"]["8435000000011"] = [_hit(111)]
    d = client.get(f"{BASE}/{r.id}/candidats", headers=admin).json()
    assert [(c["discogs_release_id"], c["via"]) for c in d["candidats"]] == [(111, "ean")]
    assert fake_discogs.calls["text"] == []

    sense = _mk(db, artista="Altre", title="Disc")
    fake_discogs.state["text"] = [_hit(7, "Altre", "Disc"), _hit(8, "Altre", "Disc (Remix)")]
    c = client.get(f"{BASE}/{sense.id}/candidats", headers=admin).json()["candidats"]
    assert [(x["discogs_release_id"], x["via"], x["exacte"]) for x in c] == [(7, "text", True), (8, "text", False)]


def test_vincular_fixa_id_i_surt_de_la_cua(db, client, admin):
    r = _mk(db, ean="8435000000011")
    resp = client.post(f"{BASE}/{r.id}", json={"discogs_release_id": 4242}, headers=admin)
    assert resp.status_code == 200 and resp.json()["discogs_release_id"] == 4242
    db.expire_all()
    assert db.get(Release, r.id).discogs_release_id == 4242
    assert client.get(BASE, headers=admin).json()["total"] == 0
    # ya vinculado: no se puede volver a vincular
    assert client.post(f"{BASE}/{r.id}", json={"discogs_release_id": 1}, headers=admin).status_code == 409


def test_vincular_avisa_si_el_id_ja_el_te_un_altre_release(db, client, admin):
    _mk(db, title="Existent", rid=99)
    r = _mk(db, title="Nou")
    resp = client.post(f"{BASE}/{r.id}", json={"discogs_release_id": 99}, headers=admin)
    assert resp.status_code == 409 and resp.json()["detail"]["titulo"] == "Existent"
    ok = client.post(f"{BASE}/{r.id}", json={"discogs_release_id": 99, "force": True}, headers=admin)
    assert ok.status_code == 200


def test_ajornar_treu_de_pendents_i_es_pot_desfer(db, client, admin):
    r = _mk(db)
    assert client.post(f"{BASE}/{r.id}/ajornar", json={}, headers=admin).status_code == 200
    d = client.get(BASE, headers=admin).json()
    assert d["rows"] == [] and d["counts"]["ajornats"] == 1
    assert len(client.get(f"{BASE}?filtre=ajornats", headers=admin).json()["rows"]) == 1
    client.post(f"{BASE}/{r.id}/ajornar", json={"ajornat": False}, headers=admin)
    assert client.get(BASE, headers=admin).json()["total"] == 1


def test_auto_vincula_nomes_candidat_unic_per_ean(db, client, admin, fake_discogs):
    unic = _mk(db, title="Unic", ean="1111111111116")
    ambigu = _mk(db, title="Ambigu", ean="2222222222222")
    buit = _mk(db, title="Buit", ean="3333333333333")
    sense_ean = _mk(db, title="Sense EAN")
    fake_discogs.state["barcode"] = {
        "1111111111116": [_hit(1)], "2222222222222": [_hit(2), _hit(3)], "3333333333333": [],
    }

    res = client.post(f"{BASE}/auto", headers=admin).json()
    assert (res["revisats"], res["vinculats"], res["ambigus"], res["sense_resultat"]) == (3, 1, 1, 1)
    db.expire_all()
    assert db.get(Release, unic.id).discogs_release_id == 1
    assert db.get(Release, ambigu.id).discogs_release_id is None
    assert db.get(Release, buit.id).discogs_release_id is None
    assert db.get(Release, sense_ean.id).discogs_release_id is None

    # segunda pasada inmediata: ya se miraron hace menos de 24h, no se repite la llamada a Discogs
    fake_discogs.calls["barcode"].clear()
    assert client.post(f"{BASE}/auto", headers=admin).json()["revisats"] == 0
    assert fake_discogs.calls["barcode"] == []


def test_auto_no_vincula_si_el_id_ja_es_d_un_altre(db, client, admin, fake_discogs):
    _mk(db, title="Existent", rid=1)
    r = _mk(db, title="Nou", ean="1111111111116")
    fake_discogs.state["barcode"] = {"1111111111116": [_hit(1)]}
    res = client.post(f"{BASE}/auto", headers=admin).json()
    assert res["vinculats"] == 0 and res["ambigus"] == 1
    db.expire_all()
    assert db.get(Release, r.id).discogs_release_id is None


def test_prova_api_retorna_estat_http_i_resultats(db, client, admin, monkeypatch):
    class Resp:
        status_code = 200
        is_success = True
        headers = {"content-type": "application/json", "X-Discogs-Ratelimit-Remaining": "57"}
        text = ""

        def json(self):
            return {"pagination": {"items": 1}, "results": [{"id": 9, "title": "A - B", "year": "2026"}]}

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, path, params=None):
            assert path == "/database/search" and params["barcode"] == "8435000000011"
            return Resp()

    monkeypatch.setattr(discogs, "_client", lambda token: FakeClient())
    monkeypatch.setattr(discogs, "_throttle", lambda: None)
    d = client.get(f"{BASE}/prova?ean=8435 000-000011", headers=admin).json()
    assert d["http_status"] == 200 and d["ratelimit_restant"] == "57"
    assert [(x["discogs_release_id"], x["artista"]) for x in d["resultats"]] == [(9, "A")]
    assert client.get(f"{BASE}/prova?ean=abc", headers=admin).status_code == 422
