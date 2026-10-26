"""Filtros, orden y paginación de GET /admin/releases (catálogo del admin)."""

import contextlib
import io
import re
from decimal import Decimal

from sqlalchemy import select

from app.models import CondicionItem, Item, ItemStatus, Release, User


def _admin(client, db) -> dict:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert client.post("/auth/magic-link", json={"email": "admin@example.com"}).status_code == 202
    token = re.search(r"token=([\w\-]+)", buf.getvalue()).group(1)
    access = client.post(f"/auth/magic-link/verify?token={token}").json()["access_token"]
    db.scalar(select(User).where(User.email == "admin@example.com")).role = "admin"
    db.commit()
    return {"Authorization": f"Bearer {access}"}


def _release(db, artista, titulo, **kw) -> Release:
    r = Release(artista=artista, title=titulo, formato=kw.pop("formato", "LP"), **kw)
    db.add(r)
    db.commit()
    return r


def _item(db, release, precio="10.00", **kw) -> Item:
    estado = kw.pop("estado_disco", None)
    i = Item(release_id=release.id, price=Decimal(precio), **kw)
    if estado:
        i.estado_disco = estado
    db.add(i)
    db.commit()
    return i


def _ids(resp) -> list[str]:
    assert resp.status_code == 200, resp.text
    return [r["titulo"] for r in resp.json()["releases"]]


def _seed(db):
    a = _release(db, "Alpha", "A1", sello="Blue Note", genero="Jazz, Funk / Soul", estilos="Hard Bop, Soul-Jazz",
                 pais="US", anio=1965, discogs_release_id=11, image_url="http://x/a.jpg")
    b = _release(db, "Beta", "B1", sello="Sub Pop", genero="Rock", estilos="Grunge", pais="UK", anio=1992,
                 formato="CD")
    c = _release(db, "Gamma", "C1", sello="Blue Note Europe", genero="Jazz", pais="US", anio=1978,
                 discogs_release_id=33)
    _item(db, a, "30.00", estado_disco="Near Mint (NM or M-)")
    _item(db, a, "12.00", estado_disco="Very Good Plus (VG+)")
    _item(db, b, "8.00", condition=CondicionItem.nou, quantity=3, min_stock_alert=3)
    _item(db, c, "50.00", status=ItemStatus.vendido)
    return a, b, c


def test_filtros_multivalor_y_tokens(db, client):
    h = _admin(client, db)
    _seed(db)
    # OR dentro del filtro
    assert sorted(_ids(client.get("/admin/releases?sello=Sub Pop&sello=Blue Note", headers=h))) == ["A1", "B1", "C1"]
    # genero: token exacto, "Jazz" no casa con "Funk / Soul" ni con Rock
    assert sorted(_ids(client.get("/admin/releases?genero=Jazz", headers=h))) == ["A1", "C1"]
    assert _ids(client.get("/admin/releases?genero=Jazz&genero=Rock", headers=h)).__len__() == 3
    assert _ids(client.get("/admin/releases?estilo=Grunge", headers=h)) == ["B1"]
    assert _ids(client.get("/admin/releases?estilo=Bop", headers=h)) == []  # token, no substring
    assert sorted(_ids(client.get("/admin/releases?pais=us", headers=h))) == ["A1", "C1"]
    assert _ids(client.get("/admin/releases?formato=cd", headers=h)) == ["B1"]


def test_filtro_anio(db, client):
    h = _admin(client, db)
    _seed(db)
    assert sorted(_ids(client.get("/admin/releases?anio_min=1970&anio_max=1999", headers=h))) == ["B1", "C1"]
    assert _ids(client.get("/admin/releases?anio_max=1970", headers=h)) == ["A1"]


def test_filtros_de_copia_sobre_la_misma_fila(db, client):
    h = _admin(client, db)
    _seed(db)
    assert _ids(client.get("/admin/releases?status=vendido", headers=h)) == ["C1"]
    assert _ids(client.get("/admin/releases?condicion=nou", headers=h)) == ["B1"]
    assert _ids(client.get("/admin/releases?estado_disco=Near Mint", headers=h)) == ["A1"]
    # NM a 30€: precio_max=20 no debe casar con la copia VG+ de 12€ + NM de otra fila
    assert _ids(client.get("/admin/releases?estado_disco=Near Mint&precio_max=20", headers=h)) == []
    assert _ids(client.get("/admin/releases?estado_disco=Very Good&precio_max=20", headers=h)) == ["A1"]
    assert sorted(_ids(client.get("/admin/releases?precio_min=25", headers=h))) == ["A1", "C1"]


def test_con_stock_stock_bajo_y_limpieza(db, client):
    h = _admin(client, db)
    _seed(db)
    assert sorted(_ids(client.get("/admin/releases?con_stock=true", headers=h))) == ["A1", "B1"]
    assert _ids(client.get("/admin/releases?con_stock=false", headers=h)) == ["C1"]
    assert _ids(client.get("/admin/releases?stock_bajo=true", headers=h)) == ["B1"]
    assert _ids(client.get("/admin/releases?sin_discogs=true", headers=h)) == ["B1"]
    assert sorted(_ids(client.get("/admin/releases?sin_discogs=false", headers=h))) == ["A1", "C1"]
    assert sorted(_ids(client.get("/admin/releases?sin_imagen=true", headers=h))) == ["B1", "C1"]
    assert _ids(client.get("/admin/releases?sin_imagen=false", headers=h)) == ["A1"]
    assert sorted(_ids(client.get("/admin/releases?sin_seccio=true", headers=h))) == ["A1", "B1", "C1"]


def test_orden_y_paginacion(db, client):
    h = _admin(client, db)
    _seed(db)
    assert _ids(client.get("/admin/releases?sort=anio&dir=desc", headers=h)) == ["B1", "C1", "A1"]
    assert _ids(client.get("/admin/releases?sort=anio", headers=h)) == ["A1", "C1", "B1"]
    # precio = copia disponible más barata (C1 solo tiene una vendida -> nulo, al final)
    assert _ids(client.get("/admin/releases?sort=precio", headers=h)) == ["B1", "A1", "C1"]
    assert _ids(client.get("/admin/releases?sort=artista&dir=desc", headers=h)) == ["C1", "B1", "A1"]
    resp = client.get("/admin/releases?limit=2&offset=2", headers=h)
    assert resp.json()["total"] == 3 and _ids(resp) == ["C1"]
    assert _ids(client.get("/admin/releases?sort=formato&dir=desc", headers=h))[:2] == ["A1", "C1"]  # LP antes que CD
    assert client.get("/admin/releases?sort=ean", headers=h).status_code == 200
    assert client.get("/admin/releases?sort=nope", headers=h).status_code == 422


def test_respuesta_incluye_pais_estilos_y_creado(db, client):
    h = _admin(client, db)
    _seed(db)
    r = client.get("/admin/releases?genero=Rock", headers=h).json()["releases"][0]
    assert r["pais"] == "UK" and r["estilos"] == "Grunge" and r["creado"]


def test_facets_valores_distintos_y_filtro_anio_exacto(db, client):
    h = _admin(client, db)
    _seed(db)
    _release(db, "Delta", "D1", sello="Verve – V-8000, Blue Note – BLP 1")  # catno fuera, un valor por sello
    _release(db, "Eps", "E1")  # sin sello ni año: no aporta valores
    f = client.get("/admin/releases/facets", headers=h).json()
    assert f["sello"] == ["Blue Note", "Blue Note Europe", "Sub Pop", "Verve"]
    assert f["formato"] == ["CD", "LP"]
    assert f["anio"] == [1965, 1978, 1992]
    assert f["genero"] == ["Funk / Soul", "Jazz", "Rock"]      # partidos por coma y sin duplicados
    assert f["estilo"] == ["Grunge", "Hard Bop", "Soul-Jazz"]
    assert f["pais"] == ["UK", "US"]
    assert f["etiqueta"] == [] and f["seccio"] == []
    assert sorted(_ids(client.get("/admin/releases?anio=1965&anio=1992", headers=h))) == ["A1", "B1"]


def test_q_busca_por_palabras_sueltas_entre_campos(db, client):
    h = _admin(client, db)
    _seed(db)
    assert _ids(client.get("/admin/releases?q=Alpha A1", headers=h)) == ["A1"]      # artista + título
    assert _ids(client.get("/admin/releases?q=alpha  blue", headers=h)) == ["A1"]    # artista + sello, espacios dobles
    assert _ids(client.get("/admin/releases?q=Alpha B1", headers=h)) == []           # todas las palabras deben casar
    assert sorted(_ids(client.get("/admin/releases?q=blue note", headers=h))) == ["A1", "C1"]
    assert len(_ids(client.get("/admin/releases?q=%20", headers=h))) == 3            # solo espacios = sin filtro


def test_orden_y_campo_ultima_recepcion(db, client):
    from datetime import datetime, timezone
    h = _admin(client, db)
    a, b, c = _seed(db)
    # A: dos copias (la última entró el 2024-03-10); B: nou, última recepción 2025-06-01; C: sin entry_date
    for item, fecha in zip(db.scalars(select(Item).where(Item.release_id == a.id)).all(), ("2023-01-05", "2024-03-10")):
        item.entry_date = datetime.fromisoformat(fecha).replace(tzinfo=timezone.utc)
    db.scalar(select(Item).where(Item.release_id == b.id)).entry_date = datetime(2025, 6, 1, tzinfo=timezone.utc)
    db.commit()
    # C cae en created_at (= ahora) y es la más reciente
    assert _ids(client.get("/admin/releases?sort=recepcion&dir=desc", headers=h)) == ["C1", "B1", "A1"]
    assert _ids(client.get("/admin/releases?sort=recepcion", headers=h)) == ["A1", "B1", "C1"]
    rows = {r["titulo"]: r for r in client.get("/admin/releases", headers=h).json()["releases"]}
    assert rows["A1"]["ultima_recepcion"].startswith("2024-03-10")
    assert rows["B1"]["ultima_recepcion"].startswith("2025-06-01")
    assert rows["C1"]["ultima_recepcion"]  # created_at como respaldo
