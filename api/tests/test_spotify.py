"""§19 (docs/ARQUITECTURA_CORE_VERTICAL.md): Spotify només té sentit per a
discos (compara artistes escoltats contra el catàleg musical) — el kill
switch global (`spotify_enabled`) ja no és suficient sol, cal que el
vertical del tenant sigui `records`."""

from sqlalchemy import select

from app.models import Tenant


def test_spotify_enabled_per_a_vertical_records(db, client):
    resp = client.get("/auth/spotify/enabled")
    assert resp.status_code == 200
    assert resp.json() == {"enabled": True}


def test_spotify_deshabilitat_fora_del_vertical_discos(db, client):
    tenant = db.get(Tenant, db.info["tenant_id"])
    tenant.vertical_id = "floristry"
    db.commit()

    resp = client.get("/auth/spotify/enabled")
    assert resp.status_code == 200
    assert resp.json() == {"enabled": False}

    # Les rutes protegides (init/status/library...) responen 404, com si el
    # mòdul no existís, igual que amb el kill switch global.
    assert client.post("/auth/spotify/init").status_code in (401, 404)
    assert client.get("/auth/spotify/status").status_code in (401, 404)
