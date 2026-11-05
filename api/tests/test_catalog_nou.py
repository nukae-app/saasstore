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
    r = Release(artista="Artista", title="Àlbum", formato="LP")
    db.add(r)
    db.flush()
    db.add(Item(
        release_id=r.id, price=Decimal(precio), condition=CondicionItem.nou,
        quantity=cantidad, reserved_quantity=cantidad_reservada,
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
    user.role = "admin"
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


def _seed_sort(db):
    """A: 1 copia a 30 (la más antigua); B: copias a 50 y 10 (mín. 10); C: 20 (la más nueva)."""
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    out = {}
    for name, artista, prices, age in (("A", "Zeta", ["30"], 3), ("B", "Beta", ["50", "10"], 2), ("C", "Alfa", ["20"], 1)):
        r = Release(artista=artista, title=name, formato="LP")
        db.add(r)
        db.flush()
        for pr in prices:
            db.add(Item(release_id=r.id, price=Decimal(pr), condition=CondicionItem.segona_ma,
                        created_at=now - timedelta(days=age)))
        out[name] = r
    db.commit()
    return out


def _titles(client, sort):
    return [r["title"] for r in client.get(f"/catalog?sort={sort}").json()["results"]]


def test_catalog_sort_novetats(db, client):
    _seed_sort(db)
    assert _titles(client, "novetats") == ["C", "B", "A"]


def test_catalog_sort_preu_usa_minimo_disponible(db, client):
    _seed_sort(db)
    assert _titles(client, "preu_asc") == ["B", "C", "A"]
    assert _titles(client, "preu_desc") == ["A", "C", "B"]


def test_catalog_sort_artista_y_titol(db, client):
    _seed_sort(db)
    assert _titles(client, "artista") == ["C", "B", "A"]
    assert _titles(client, "titol") == ["A", "B", "C"]


def test_catalog_sort_invalido_422(db, client):
    assert client.get("/catalog?sort=lo_que_sea").status_code == 422


def test_catalog_sort_any_con_nulos_al_final(db, client):
    from app.models import RecordProduct
    for title, anio in (("X", 1975), ("Y", None), ("Z", 2001)):
        r = Release(artista="Art", title=title, formato="LP")
        db.add(r)
        db.flush()
        db.add(Item(release_id=r.id, price=Decimal("10"), condition=CondicionItem.segona_ma))
        rec = db.get(RecordProduct, r.id)
        if rec is not None:
            rec.anio = anio
    db.commit()
    assert _titles(client, "any_desc") == ["Z", "X", "Y"]
    assert _titles(client, "any_asc") == ["X", "Z", "Y"]
