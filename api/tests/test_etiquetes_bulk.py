"""POST /admin/etiquetes/{id}/assignar: etiquetar en bloque por ids o criterios."""

from sqlalchemy import select

from app.models import Etiqueta, ReleaseEtiqueta
from tests.test_admin_catalog_filters import _admin, _release, _seed


def _etiqueta(db) -> Etiqueta:
    e = Etiqueta(slug="jazz_picks", name_ca="Jazz Picks")
    db.add(e)
    db.commit()
    return e


def _con(db, e):
    return set(db.scalars(select(ReleaseEtiqueta.release_id).where(ReleaseEtiqueta.etiqueta_id == e.id)).all())


def test_assignar_per_ids_es_idempotent_i_treu(db, client):
    h = _admin(client, db)
    a, b, c = _seed(db)
    e = _etiqueta(db)
    url = f"/admin/etiquetes/{e.id}/assignar"

    r = client.post(url, json={"release_ids": [str(a.id), str(b.id)]}, headers=h)
    assert r.json()["afectats"] == 2
    assert _con(db, e) == {a.id, b.id}

    r = client.post(url, json={"release_ids": [str(a.id), str(c.id)]}, headers=h)
    assert (r.json()["afectats"], r.json()["ja_estaven"]) == (1, 1)

    r = client.post(url, json={"accio": "treure", "release_ids": [str(a.id), str(b.id)]}, headers=h)
    assert r.json()["afectats"] == 2
    assert _con(db, e) == {c.id}


def test_assignar_per_criteris_i_previsualitzar(db, client):
    h = _admin(client, db)
    a, b, c = _seed(db)
    e = _etiqueta(db)
    url = f"/admin/etiquetes/{e.id}/assignar"
    criteris = {"genero": ["Jazz"]}  # a i c

    r = client.post(url, json={"criteris": criteris, "previsualitzar": True}, headers=h)
    assert (r.json()["afectats"], r.json()["aplicat"]) == (2, False)
    assert _con(db, e) == set()

    client.post(url, json={"criteris": criteris}, headers=h)
    assert _con(db, e) == {a.id, c.id}


def test_assignar_valida_entrada(db, client):
    h = _admin(client, db)
    e = _etiqueta(db)
    assert client.post(f"/admin/etiquetes/{e.id}/assignar", json={}, headers=h).status_code == 422
    assert client.post("/admin/etiquetes/9999/assignar", json={"release_ids": []}, headers=h).status_code == 404
