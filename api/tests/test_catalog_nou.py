"""Regresión: el catálogo público (y la creación de peticiones) no debe
tratar una línea `nou` agotada (cantidad - cantidad_reservada <= 0) como si
tuviera stock, solo porque `status` se queda en 'disponible' para stock
agregado (a diferencia de segona_ma, donde status sí refleja la venta)."""

import contextlib
import io
import re
from decimal import Decimal

from sqlalchemy import select

from app.models import CondicionItem, Item, Release, User


def _login(client, email: str) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert client.post("/auth/magic-link", json={"email": email}).status_code == 202
    token = re.search(r"token=([\w\-]+)", buf.getvalue()).group(1)
    resp = client.post(f"/auth/magic-link/verify?token={token}")
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _seed_release_nou(db, cantidad, cantidad_reservada=0, precio="20.00") -> Release:
    r = Release(artista="Artista", titulo="Àlbum", formato="LP")
    db.add(r)
    db.flush()
    db.add(Item(
        release_id=r.id, precio=Decimal(precio), condicion=CondicionItem.nou,
        cantidad=cantidad, cantidad_reservada=cantidad_reservada,
    ))
    db.commit()
    return r


def test_catalog_no_lista_release_con_nou_agotado(db, client):
    _seed_release_nou(db, cantidad=0)
    resp = client.get("/catalog")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_catalog_no_lista_release_con_nou_completamente_reservado(db, client):
    _seed_release_nou(db, cantidad=3, cantidad_reservada=3)
    resp = client.get("/catalog")
    assert resp.json()["total"] == 0


def test_catalog_lista_release_con_nou_disponible(db, client):
    _seed_release_nou(db, cantidad=3, cantidad_reservada=1)
    resp = client.get("/catalog")
    assert resp.json()["total"] == 1


def test_catalog_precio_filtros_ignoran_nou_agotado(db, client):
    _seed_release_nou(db, cantidad=0, precio="15.00")
    resp = client.get("/catalog?precio_min=10&precio_max=20")
    assert resp.json()["total"] == 0


def test_crear_peticion_release_con_nou_agotado_no_falla(db, client):
    """Antes: un release con la línea nou a 0 (o toda reservada) bloqueaba
    la creación de la petición como si tuviera stock real."""
    token = _login(client, "client@example.com")
    release = _seed_release_nou(db, cantidad=0)

    resp = client.post("/me/peticiones", json={"release_id": str(release.id)}, headers=_auth(token))
    assert resp.status_code == 201


def test_crear_peticion_release_con_nou_reservado_no_falla(db, client):
    token = _login(client, "client@example.com")
    release = _seed_release_nou(db, cantidad=2, cantidad_reservada=2)

    resp = client.post("/me/peticiones", json={"release_id": str(release.id)}, headers=_auth(token))
    assert resp.status_code == 201


def test_crear_peticion_tienda_con_nou_agotado_no_falla(db, client):
    admin_token = _login(client, "admin@example.com")
    user = db.scalar(select(User).where(User.email == "admin@example.com"))
    user.rol = "admin"
    db.commit()

    _login(client, "mostrador@example.com")
    cliente = db.scalar(select(User).where(User.email == "mostrador@example.com"))
    release = _seed_release_nou(db, cantidad=0)

    resp = client.post(
        "/admin/peticiones/tienda",
        json={"user_id": str(cliente.id), "release_id": str(release.id)},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201
