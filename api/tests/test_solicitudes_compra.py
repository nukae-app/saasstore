"""Tests del flux de sol·licituds de compra: sol·licitud (sense proveïdor) ->
resoldre cap a una comanda real d'un proveïdor concret."""

import contextlib
import io
import re
import uuid

from sqlalchemy import select

from app.models import (
    CondicionItem, Item, ItemStatus, Proveedor, Release, SolicitudCompra, SolicitudCompraLinea, User,
)


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


def _seed_proveedor(db, nombre="DistroX", email="prov@example.com") -> Proveedor:
    p = Proveedor(nombre=nombre, email=email)
    db.add(p)
    db.commit()
    return p


def test_crear_solicitud_con_release_existente(db, client):
    admin = _admin_token(client, db)
    release = _seed_release(db)

    payload = {
        "lineas": [{"release_id": str(release.id), "cantidad": 2, "notas": "reposició"}],
    }
    resp = client.post("/admin/solicitudes-compra", json=payload, headers=_auth(admin))
    assert resp.status_code == 201
    body = resp.json()
    assert body["estado"] == "oberta"
    assert body["origen"] == "manual"
    assert len(body["lineas"]) == 1
    assert body["lineas"][0]["artista"] == "Artista"
    assert body["lineas"][0]["cantidad"] == 2
    assert body["lineas"][0]["resuelta"] is False


def test_crear_solicitud_con_disco_no_catalogado(db, client):
    admin = _admin_token(client, db)

    payload = {
        "lineas": [{"artista": "Nou Grup", "titulo": "Nou Disc", "sello": "Segell X", "cantidad": 1}],
    }
    resp = client.post("/admin/solicitudes-compra", json=payload, headers=_auth(admin))
    assert resp.status_code == 201
    body = resp.json()
    assert body["lineas"][0]["release_id"] is None
    assert body["lineas"][0]["artista"] == "Nou Grup"


def test_crear_solicitud_sin_release_ni_artista_falla(db, client):
    admin = _admin_token(client, db)
    payload = {"lineas": [{"cantidad": 1}]}
    resp = client.post("/admin/solicitudes-compra", json=payload, headers=_auth(admin))
    assert resp.status_code == 422


def test_resolver_solicitud_crea_comanda(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = _seed_release(db)

    solicitud = client.post(
        "/admin/solicitudes-compra",
        json={"lineas": [{"release_id": str(release.id), "cantidad": 3}]},
        headers=_auth(admin),
    ).json()
    linea_id = solicitud["lineas"][0]["id"]

    resp = client.post(
        "/admin/solicitudes-compra/resolver",
        json={
            "proveedor_id": str(prov.id),
            "fecha": "2026-06-01T10:00:00",
            "lineas": [{"solicitud_linea_id": linea_id, "precio_unitario_estimado": "10.00"}],
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    comanda = resp.json()
    assert comanda["proveedor_id"] == str(prov.id)
    assert comanda["lineas"][0]["cantidad"] == 3

    solicitud_actualitzada = client.get(
        f"/admin/solicitudes-compra/{solicitud['id']}", headers=_auth(admin)
    ).json()
    assert solicitud_actualitzada["estado"] == "resolta"
    assert solicitud_actualitzada["lineas"][0]["resuelta"] is True
    assert solicitud_actualitzada["lineas"][0]["comanda_linea_id"] == comanda["lineas"][0]["id"]


def test_resolver_solicitud_sense_release_falla(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)

    solicitud = client.post(
        "/admin/solicitudes-compra",
        json={"lineas": [{"artista": "X", "titulo": "Y", "cantidad": 1}]},
        headers=_auth(admin),
    ).json()
    linea_id = solicitud["lineas"][0]["id"]

    resp = client.post(
        "/admin/solicitudes-compra/resolver",
        json={
            "proveedor_id": str(prov.id),
            "fecha": "2026-06-01T10:00:00",
            "lineas": [{"solicitud_linea_id": linea_id}],
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 422


def test_resolver_linia_ya_resuelta_falla(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = _seed_release(db)

    solicitud = client.post(
        "/admin/solicitudes-compra",
        json={"lineas": [{"release_id": str(release.id), "cantidad": 1}]},
        headers=_auth(admin),
    ).json()
    linea_id = solicitud["lineas"][0]["id"]
    resolver_payload = {
        "proveedor_id": str(prov.id), "fecha": "2026-06-01T10:00:00",
        "lineas": [{"solicitud_linea_id": linea_id}],
    }
    assert client.post("/admin/solicitudes-compra/resolver", json=resolver_payload, headers=_auth(admin)).status_code == 201

    resp = client.post("/admin/solicitudes-compra/resolver", json=resolver_payload, headers=_auth(admin))
    assert resp.status_code == 409


def test_partial_resolution_manté_solicitud_oberta(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    r1 = _seed_release(db, artista="A1", titulo="T1")
    r2 = _seed_release(db, artista="A2", titulo="T2")

    solicitud = client.post(
        "/admin/solicitudes-compra",
        json={"lineas": [
            {"release_id": str(r1.id), "cantidad": 1},
            {"release_id": str(r2.id), "cantidad": 1},
        ]},
        headers=_auth(admin),
    ).json()
    linea1_id = solicitud["lineas"][0]["id"]

    client.post(
        "/admin/solicitudes-compra/resolver",
        json={
            "proveedor_id": str(prov.id), "fecha": "2026-06-01T10:00:00",
            "lineas": [{"solicitud_linea_id": linea1_id}],
        },
        headers=_auth(admin),
    )

    solicitud_actualitzada = client.get(
        f"/admin/solicitudes-compra/{solicitud['id']}", headers=_auth(admin)
    ).json()
    assert solicitud_actualitzada["estado"] == "oberta"
    resueltas = [l["resuelta"] for l in solicitud_actualitzada["lineas"]]
    assert sorted(resueltas) == [False, True]


def test_eliminar_linia_resolta_falla(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = _seed_release(db)

    solicitud = client.post(
        "/admin/solicitudes-compra",
        json={"lineas": [{"release_id": str(release.id), "cantidad": 1}]},
        headers=_auth(admin),
    ).json()
    linea_id = solicitud["lineas"][0]["id"]
    client.post(
        "/admin/solicitudes-compra/resolver",
        json={
            "proveedor_id": str(prov.id), "fecha": "2026-06-01T10:00:00",
            "lineas": [{"solicitud_linea_id": linea_id}],
        },
        headers=_auth(admin),
    )

    resp = client.delete(f"/admin/solicitudes-compra/{solicitud['id']}/lineas/{linea_id}", headers=_auth(admin))
    assert resp.status_code == 409


def test_cancelar_solicitud(db, client):
    admin = _admin_token(client, db)
    release = _seed_release(db)
    solicitud = client.post(
        "/admin/solicitudes-compra",
        json={"lineas": [{"release_id": str(release.id), "cantidad": 1}]},
        headers=_auth(admin),
    ).json()

    resp = client.patch(f"/admin/solicitudes-compra/{solicitud['id']}/cancelar", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json()["estado"] == "cancelada"

    resp2 = client.patch(f"/admin/solicitudes-compra/{solicitud['id']}/cancelar", headers=_auth(admin))
    assert resp2.status_code == 409


def test_eliminar_solicitud_sense_resoldre(db, client):
    admin = _admin_token(client, db)
    release = _seed_release(db)
    solicitud = client.post(
        "/admin/solicitudes-compra",
        json={"lineas": [{"release_id": str(release.id), "cantidad": 1}]},
        headers=_auth(admin),
    ).json()

    resp = client.delete(f"/admin/solicitudes-compra/{solicitud['id']}", headers=_auth(admin))
    assert resp.status_code == 204
    assert db.get(SolicitudCompra, uuid.UUID(solicitud["id"])) is None


def test_list_solicitudes_filtra_per_estat(db, client):
    admin = _admin_token(client, db)
    release = _seed_release(db)
    solicitud = client.post(
        "/admin/solicitudes-compra",
        json={"lineas": [{"release_id": str(release.id), "cantidad": 1}]},
        headers=_auth(admin),
    ).json()
    client.patch(f"/admin/solicitudes-compra/{solicitud['id']}/cancelar", headers=_auth(admin))

    obertes = client.get("/admin/solicitudes-compra?estado=oberta", headers=_auth(admin)).json()
    assert all(s["estado"] == "oberta" for s in obertes)
    cancelades = client.get("/admin/solicitudes-compra?estado=cancelada", headers=_auth(admin)).json()
    assert any(s["id"] == solicitud["id"] for s in cancelades)


def test_resoldre_estoc_manual_tanca_linia_sense_comanda(db, client):
    admin = _admin_token(client, db)
    release = _seed_release(db)
    solicitud = client.post(
        "/admin/solicitudes-compra",
        json={"lineas": [{"release_id": str(release.id), "cantidad": 1}]},
        headers=_auth(admin),
    ).json()
    linea_id = solicitud["lineas"][0]["id"]

    item = Item(release_id=release.id, precio=20, condicion=CondicionItem.segona_ma, status=ItemStatus.disponible)
    db.add(item)
    db.commit()

    resp = client.post(
        f"/admin/solicitudes-compra/lineas/{linea_id}/resoldre-estoc",
        json={"item_id": str(item.id)},
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["estado"] == "resolta"
    assert body["lineas"][0]["resuelta"] is True
    assert body["lineas"][0]["item_resuelto_id"] == str(item.id)

    db.expire_all()
    item_db = db.get(Item, item.id)
    assert item_db.status.value == "reservado"


def test_resoldre_estoc_linia_ja_resolta_falla(db, client):
    admin = _admin_token(client, db)
    release = _seed_release(db)
    solicitud = client.post(
        "/admin/solicitudes-compra",
        json={"lineas": [{"release_id": str(release.id), "cantidad": 1}]},
        headers=_auth(admin),
    ).json()
    linea_id = solicitud["lineas"][0]["id"]

    item1 = Item(release_id=release.id, precio=20, condicion=CondicionItem.segona_ma, status=ItemStatus.disponible)
    item2 = Item(release_id=release.id, precio=22, condicion=CondicionItem.segona_ma, status=ItemStatus.disponible)
    db.add_all([item1, item2])
    db.commit()

    resp1 = client.post(
        f"/admin/solicitudes-compra/lineas/{linea_id}/resoldre-estoc",
        json={"item_id": str(item1.id)},
        headers=_auth(admin),
    )
    assert resp1.status_code == 200

    resp2 = client.post(
        f"/admin/solicitudes-compra/lineas/{linea_id}/resoldre-estoc",
        json={"item_id": str(item2.id)},
        headers=_auth(admin),
    )
    assert resp2.status_code == 409


def test_eliminar_linia_resolta_desde_estoc_falla(db, client):
    admin = _admin_token(client, db)
    release = _seed_release(db)
    solicitud = client.post(
        "/admin/solicitudes-compra",
        json={"lineas": [{"release_id": str(release.id), "cantidad": 1}]},
        headers=_auth(admin),
    ).json()
    linea_id = solicitud["lineas"][0]["id"]

    item = Item(release_id=release.id, precio=20, condicion=CondicionItem.segona_ma, status=ItemStatus.disponible)
    db.add(item)
    db.commit()
    client.post(
        f"/admin/solicitudes-compra/lineas/{linea_id}/resoldre-estoc",
        json={"item_id": str(item.id)},
        headers=_auth(admin),
    )

    resp = client.delete(f"/admin/solicitudes-compra/{solicitud['id']}/lineas/{linea_id}", headers=_auth(admin))
    assert resp.status_code == 409
