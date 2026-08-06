"""Tests del dashboard d'antiguitat de l'estoc (GET /admin/catalog/aging)."""

import contextlib
import io
import re
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.models import Item, ItemStatus, Release, User


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
    user.rol = "admin"
    db.commit()
    return access


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _seed_release(db, artista="Artista", titulo="Àlbum") -> Release:
    r = Release(artista=artista, titulo=titulo, formato="LP")
    db.add(r)
    db.commit()
    return r


def _dias_atras(n: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=n)


def test_aging_agrupa_per_buckets_i_ignora_sense_estoc_disponible(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db)

    db.add_all([
        Item(release_id=r.id, precio=Decimal("10.00"), fecha_entrada=_dias_atras(5)),
        Item(release_id=r.id, precio=Decimal("20.00"), fecha_entrada=_dias_atras(400)),
        # No disponible: no ha de comptar per a l'antiguitat.
        Item(release_id=r.id, precio=Decimal("15.00"), fecha_entrada=_dias_atras(900), status=ItemStatus.vendido),
    ])
    db.commit()

    resp = client.get("/admin/catalog/aging", headers=_auth(admin))
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_disponible"] == 2
    assert data["con_fecha"] == 2
    assert data["sin_fecha"] == 0

    by_key = {b["key"]: b for b in data["buckets"]}
    assert by_key["0_30"]["count"] == 1
    assert Decimal(by_key["0_30"]["valor"]) == Decimal("10.00")
    assert by_key["366_730"]["count"] == 1
    assert Decimal(by_key["366_730"]["valor"]) == Decimal("20.00")


def test_aging_compta_sin_fecha_per_separat(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db)

    db.add(Item(release_id=r.id, precio=Decimal("30.00"), fecha_entrada=None))
    db.commit()

    resp = client.get("/admin/catalog/aging", headers=_auth(admin))
    data = resp.json()

    assert data["sin_fecha"] == 1
    assert Decimal(data["valor_sin_fecha"]) == Decimal("30.00")
    by_key = {b["key"]: b for b in data["buckets"]}
    assert by_key["sin_fecha"]["count"] == 1


def test_aging_coste_total_i_per_bucket(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db)

    db.add_all([
        Item(release_id=r.id, precio=Decimal("10.00"), coste_adquisicion=Decimal("4.00"), fecha_entrada=_dias_atras(5)),
        # Sense coste_adquisicion (legacy de Discogs): no ha de petar, compta com a 0.
        Item(release_id=r.id, precio=Decimal("20.00"), fecha_entrada=_dias_atras(400)),
    ])
    db.commit()

    resp = client.get("/admin/catalog/aging", headers=_auth(admin))
    data = resp.json()

    assert Decimal(data["coste_total"]) == Decimal("4.00")
    by_key = {b["key"]: b for b in data["buckets"]}
    assert Decimal(by_key["0_30"]["coste"]) == Decimal("4.00")
    assert Decimal(by_key["366_730"]["coste"]) == Decimal("0")


def test_aging_items_ordenats_i_origen(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db)

    vell = Item(release_id=r.id, precio=Decimal("25.00"), fecha_entrada=_dias_atras(500), codi_discogs=111)
    nou = Item(release_id=r.id, precio=Decimal("18.00"), fecha_entrada=_dias_atras(10))
    db.add_all([vell, nou])
    db.commit()

    resp = client.get("/admin/catalog/aging/items", headers=_auth(admin))
    assert resp.status_code == 200
    data = resp.json()

    assert data["total"] == 2
    assert data["items"][0]["item_id"] == str(vell.id)
    assert data["items"][0]["origen"] == "discogs"
    assert data["items"][1]["origen"] == "desconegut"


def test_aging_items_filtra_per_bucket(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db)

    recent = Item(release_id=r.id, precio=Decimal("18.00"), fecha_entrada=_dias_atras(10))
    vell = Item(release_id=r.id, precio=Decimal("25.00"), fecha_entrada=_dias_atras(500))
    sense = Item(release_id=r.id, precio=Decimal("12.00"), fecha_entrada=None)
    db.add_all([recent, vell, sense])
    db.commit()

    resp = client.get("/admin/catalog/aging/items?bucket=0_30", headers=_auth(admin))
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["item_id"] == str(recent.id)

    resp = client.get("/admin/catalog/aging/items?bucket=sin_fecha", headers=_auth(admin))
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["item_id"] == str(sense.id)
    assert data["items"][0]["dias"] is None
    assert data["items"][0]["fecha_entrada"] is None


def test_aging_items_bucket_invalid_dona_422(db, client):
    admin = _admin_token(client, db)
    resp = client.get("/admin/catalog/aging/items?bucket=no_existeix", headers=_auth(admin))
    assert resp.status_code == 422


def test_aging_items_pagina(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db)
    db.add_all([
        Item(release_id=r.id, precio=Decimal("10.00"), fecha_entrada=_dias_atras(n))
        for n in (1, 2, 3)
    ])
    db.commit()

    resp = client.get("/admin/catalog/aging/items?limit=2&offset=0", headers=_auth(admin))
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2

    resp = client.get("/admin/catalog/aging/items?limit=2&offset=2", headers=_auth(admin))
    data = resp.json()
    assert len(data["items"]) == 1


def test_aging_edad_media_i_mediana(db, client):
    admin = _admin_token(client, db)
    r = _seed_release(db)

    db.add_all([
        Item(release_id=r.id, precio=Decimal("10.00"), fecha_entrada=_dias_atras(10)),
        Item(release_id=r.id, precio=Decimal("10.00"), fecha_entrada=_dias_atras(20)),
        Item(release_id=r.id, precio=Decimal("10.00"), fecha_entrada=_dias_atras(30)),
    ])
    db.commit()

    resp = client.get("/admin/catalog/aging", headers=_auth(admin))
    data = resp.json()

    assert data["edad_mediana_dias"] == 20
    assert data["edad_media_dias"] == 20.0
