"""Tests de seccions (cubetes físiques de la botiga): CRUD admin i filtre
del catàleg públic per al mode 'remena'."""

import contextlib
import io
import re
from decimal import Decimal

from sqlalchemy import select

from app.models import Item, Release, Seccio, User


def _seed_release(db, artista="Artista", titulo="Àlbum", seccio=None) -> Release:
    r = Release(artista=artista, title=titulo, formato="LP", seccio=seccio)
    db.add(r)
    db.commit()
    return r


def _seed_item(db, release, precio="20.00") -> Item:
    item = Item(release_id=release.id, price=Decimal(precio))
    db.add(item)
    db.commit()
    return item


def _login(client, email: str) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert client.post("/auth/magic-link", json={"email": email}).status_code == 202
    token = re.search(r"token=([\w\-]+)", buf.getvalue()).group(1)
    resp = client.post(f"/auth/magic-link/verify?token={token}")
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _admin_token(client, db) -> str:
    access = _login(client, "admin@example.com")
    user = db.scalar(select(User).where(User.email == "admin@example.com"))
    user.role = "admin"
    db.commit()
    return access


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# CRUD admin
# ---------------------------------------------------------------------------

def test_crud_seccio(db, client):
    admin = _admin_token(client, db)

    resp = client.post(
        "/admin/seccions",
        json={"slug": "nacional", "name_ca": "Nacional", "name_es": "Nacional", "color": "#10b981", "position": 1},
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    seccio_id = resp.json()["id"]

    resp = client.get("/admin/seccions", headers=_auth(admin))
    assert resp.status_code == 200
    assert any(s["id"] == seccio_id for s in resp.json())

    resp = client.patch(
        f"/admin/seccions/{seccio_id}",
        json={"slug": "nacional", "name_ca": "Nacional (CAT)", "position": 2},
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    assert resp.json()["name_ca"] == "Nacional (CAT)"

    resp = client.delete(f"/admin/seccions/{seccio_id}", headers=_auth(admin))
    assert resp.status_code == 204
    assert db.get(Seccio, seccio_id) is None


def test_slug_duplicat_rebutjat(db, client):
    admin = _admin_token(client, db)
    client.post("/admin/seccions", json={"slug": "alternatiu", "name_ca": "Alternatiu"}, headers=_auth(admin))
    resp = client.post("/admin/seccions", json={"slug": "alternatiu", "name_ca": "Un altre"}, headers=_auth(admin))
    assert resp.status_code == 409


def test_esborrar_seccio_deixa_releases_sense_classificar(db, client):
    admin = _admin_token(client, db)
    seccio = Seccio(slug="internacional", name_ca="Internacional")
    db.add(seccio)
    db.commit()
    release = _seed_release(db, seccio=seccio)
    seccio_id = seccio.id

    resp = client.delete(f"/admin/seccions/{seccio_id}", headers=_auth(admin))
    assert resp.status_code == 204

    db.refresh(release)
    assert release.section_id is None


# ---------------------------------------------------------------------------
# Catàleg públic
# ---------------------------------------------------------------------------

def test_seccions_publiques_nomes_actives(db, client):
    db.add_all([
        Seccio(slug="nacional", name_ca="Nacional", active=True, position=1),
        Seccio(slug="oculta", name_ca="Oculta", active=False, position=2),
    ])
    db.commit()

    resp = client.get("/catalog/seccions")
    assert resp.status_code == 200
    slugs = [s["slug"] for s in resp.json()]
    assert slugs == ["nacional"]


def test_catalog_filtra_per_seccio(db, client):
    nacional = Seccio(slug="nacional", name_ca="Nacional")
    internacional = Seccio(slug="internacional", name_ca="Internacional")
    db.add_all([nacional, internacional])
    db.commit()

    r1 = _seed_release(db, artista="Antònia Font", seccio=nacional)
    _seed_item(db, r1)
    r2 = _seed_release(db, artista="Blur", seccio=internacional)
    _seed_item(db, r2)
    r3 = _seed_release(db, artista="Sense Classificar")
    _seed_item(db, r3)

    resp = client.get("/catalog?seccio=nacional")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["results"][0]["artista"] == "Antònia Font"
    assert data["results"][0]["seccio"]["slug"] == "nacional"

    resp = client.get("/catalog?seccio=sense-classificar")
    assert resp.json()["total"] == 1
    assert resp.json()["results"][0]["artista"] == "Sense Classificar"


def test_catalog_ordena_alfabeticament_dins_seccio(db, client):
    nacional = Seccio(slug="nacional", name_ca="Nacional")
    db.add(nacional)
    db.commit()

    for artista in ["Manel", "Antònia Font", "Txarango"]:
        r = _seed_release(db, artista=artista, seccio=nacional)
        _seed_item(db, r)

    resp = client.get("/catalog?seccio=nacional")
    artistes = [r["artista"] for r in resp.json()["results"]]
    assert artistes == ["Antònia Font", "Manel", "Txarango"]


def test_catalog_filtra_per_rang_alfabetic(db, client):
    for artista in ["107 Faunos", "Blur", "Manel", "Uf"]:
        r = _seed_release(db, artista=artista)
        _seed_item(db, r)

    resp = client.get("/catalog?rang=0-9")
    assert [r["artista"] for r in resp.json()["results"]] == ["107 Faunos"]

    resp = client.get("/catalog?rang=A-D")
    assert [r["artista"] for r in resp.json()["results"]] == ["Blur"]

    resp = client.get("/catalog?rang=M-P")
    assert [r["artista"] for r in resp.json()["results"]] == ["Manel"]

    resp = client.get("/catalog?rang=U-Z")
    assert [r["artista"] for r in resp.json()["results"]] == ["Uf"]
