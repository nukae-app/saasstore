"""Tests del CRUD complet de catàleg a l'admin: editar, eliminar, detecció de duplicats."""

import contextlib
import io
import re
import uuid
from decimal import Decimal

from sqlalchemy import select

from app.models import CondicionItem, Item, ItemStatus, Order, OrderItem, OrderStatus, Release, User
from app.services.reservations import reserve_items


# ---------------------------------------------------------------------------
# Helpers (mismo patrón que test_erp.py)
# ---------------------------------------------------------------------------

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


def _seed_release(db, artista="Artista", titulo="Àlbum", discogs_release_id=None) -> Release:
    r = Release(artista=artista, title=titulo, formato="LP", discogs_release_id=discogs_release_id)
    db.add(r)
    db.commit()
    return r


def _seed_item(db, release, precio="20.00") -> Item:
    item = Item(release_id=release.id, price=Decimal(precio))
    db.add(item)
    db.commit()
    return item


# ---------------------------------------------------------------------------
# Editar release
# ---------------------------------------------------------------------------

def test_update_release(db, client):
    admin = _admin_token(client, db)
    release = _seed_release(db)

    resp = client.put(
        f"/admin/releases/{release.id}",
        json={"artista": "Artista Nou", "title": "Àlbum Nou", "anio": 1999},
        headers=_auth(admin),
    )
    assert resp.status_code == 200

    db.refresh(release)
    assert release.artista == "Artista Nou"
    assert release.title == "Àlbum Nou"
    assert release.anio == 1999


def test_update_release_404(db, client):
    admin = _admin_token(client, db)
    import uuid as _uuid
    resp = client.put(
        f"/admin/releases/{_uuid.uuid4()}",
        json={"artista": "X", "title": "Y"},
        headers=_auth(admin),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Eliminar release / item
# ---------------------------------------------------------------------------

def test_create_item_nou_agrega_en_linia_existent(db, client):
    """Alta manual de stock nuevo: si ya hay línea nou para el release, se
    suma en vez de duplicar, con coste medio ponderado (mismo criterio que
    la recepción de comandas)."""
    admin = _admin_token(client, db)
    release = _seed_release(db)

    resp1 = client.post(
        "/admin/items",
        json={"release_id": str(release.id), "price": "20.00", "acquisition_cost": "10.00",
              "condition": "nou", "quantity": 4},
        headers=_auth(admin),
    )
    assert resp1.status_code == 201
    item_id = resp1.json()["id"]

    resp2 = client.post(
        "/admin/items",
        json={"release_id": str(release.id), "price": "22.00", "acquisition_cost": "16.00",
              "condition": "nou", "quantity": 2},
        headers=_auth(admin),
    )
    assert resp2.status_code == 201
    assert resp2.json()["id"] == item_id  # misma línea, no una nueva

    db.expire_all()
    items = db.scalars(select(Item).where(Item.release_id == release.id)).all()
    assert len(items) == 1
    assert items[0].quantity == 6
    assert items[0].acquisition_cost == Decimal("12.00")  # (4*10 + 2*16) / 6
    assert items[0].price == Decimal("22.00")


def test_create_item_segona_ma_no_agrega(db, client):
    """Segunda mano sigue creando una fila por copia, aunque sea el mismo release."""
    admin = _admin_token(client, db)
    release = _seed_release(db)

    for precio in ("20.00", "25.00"):
        resp = client.post(
            "/admin/items",
            json={"release_id": str(release.id), "price": precio, "condition": "segona_ma"},
            headers=_auth(admin),
        )
        assert resp.status_code == 201

    db.expire_all()
    items = db.scalars(select(Item).where(Item.release_id == release.id)).all()
    assert len(items) == 2


def test_list_releases_incluye_cantidad_para_items_nou(db, client):
    """Regresión: /admin/releases (StockBadge del catálogo) necesita
    cantidad/cantidad_reservada por item, si no las líneas nou salen NaN/NaN."""
    admin = _admin_token(client, db)
    release = _seed_release(db)
    db.add(Item(release_id=release.id, price=Decimal("20.00"), condition=CondicionItem.nou, quantity=5))
    db.commit()

    resp = client.get("/admin/releases", headers=_auth(admin))
    assert resp.status_code == 200
    item_out = resp.json()["releases"][0]["items"][0]
    assert item_out["cantidad"] == 5
    assert item_out["cantidad_reservada"] == 0


def test_delete_release_sense_items(db, client):
    admin = _admin_token(client, db)
    release = _seed_release(db)
    release_id = release.id

    resp = client.delete(f"/admin/releases/{release_id}", headers=_auth(admin))
    assert resp.status_code == 204
    db.expire_all()
    assert db.scalar(select(Release).where(Release.id == release_id)) is None


def test_delete_release_amb_items_falla(db, client):
    admin = _admin_token(client, db)
    release = _seed_release(db)
    _seed_item(db, release)

    resp = client.delete(f"/admin/releases/{release.id}", headers=_auth(admin))
    assert resp.status_code == 409
    # el release segueix existint
    assert db.get(Release, release.id) is not None


def test_delete_item_disponible(db, client):
    admin = _admin_token(client, db)
    release = _seed_release(db)
    item = _seed_item(db, release)
    item_id = item.id

    resp = client.delete(f"/admin/items/{item_id}", headers=_auth(admin))
    assert resp.status_code == 204
    db.expire_all()
    assert db.scalar(select(Item).where(Item.id == item_id)) is None


def test_delete_item_amb_pedido_falla(db, client):
    admin = _admin_token(client, db)
    release = _seed_release(db)
    item = _seed_item(db, release)
    reserve_items(db, [item.id], uuid.uuid4())

    order = Order(
        status=OrderStatus.pendiente_pago,
        contact_email="client@example.com",
        total=Decimal("20.00"),
        shipping_method="recogida_tienda",
    )
    db.add(order)
    db.commit()
    db.add(OrderItem(order_id=order.id, item_id=item.id, price=item.price))
    db.commit()

    resp = client.delete(f"/admin/items/{item.id}", headers=_auth(admin))
    assert resp.status_code == 409
    db.expire_all()
    assert db.get(Item, item.id) is not None


# ---------------------------------------------------------------------------
# Editar item
# ---------------------------------------------------------------------------

def test_update_item(db, client):
    admin = _admin_token(client, db)
    release = _seed_release(db)
    item = _seed_item(db, release)

    resp = client.put(
        f"/admin/items/{item.id}",
        json={"price": "25.50", "condition": "nou", "estado_disco": None, "estado_funda": None},
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    db.refresh(item)
    assert item.price == Decimal("25.50")
    assert item.condition.value == "nou"


def test_update_item_venut_falla(db, client):
    admin = _admin_token(client, db)
    release = _seed_release(db)
    item = _seed_item(db, release)
    item.status = ItemStatus.vendido
    db.commit()

    resp = client.put(
        f"/admin/items/{item.id}",
        json={"price": "99.00", "condition": "nou"},
        headers=_auth(admin),
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Detecció de duplicats
# ---------------------------------------------------------------------------

def test_check_duplicate_per_discogs_id(db, client):
    admin = _admin_token(client, db)
    _seed_release(db, artista="The Beatles", titulo="Abbey Road", discogs_release_id=12345)

    resp = client.get(
        "/admin/releases/check-duplicate",
        params={"discogs_release_id": 12345},
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    matches = resp.json()
    assert len(matches) == 1
    assert matches[0]["artista"] == "The Beatles"


def test_check_duplicate_per_artista_titulo(db, client):
    admin = _admin_token(client, db)
    _seed_release(db, artista="Pink Floyd", titulo="The Wall")

    resp = client.get(
        "/admin/releases/check-duplicate",
        params={"artista": "Pink Floyd", "titulo": "The Wall"},
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_check_duplicate_sense_coincidencia(db, client):
    admin = _admin_token(client, db)
    _seed_release(db, artista="Pink Floyd", titulo="The Wall")

    resp = client.get(
        "/admin/releases/check-duplicate",
        params={"artista": "Altre Artista", "titulo": "Altre Disc"},
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_check_duplicate_exclude_id(db, client):
    admin = _admin_token(client, db)
    release = _seed_release(db, artista="Pink Floyd", titulo="The Wall")

    resp = client.get(
        "/admin/releases/check-duplicate",
        params={"artista": "Pink Floyd", "titulo": "The Wall", "exclude_id": str(release.id)},
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Export / import CSV del catàleg
# ---------------------------------------------------------------------------

def _csv_rows(text: str) -> list[dict]:
    import csv as csv_mod
    return list(csv_mod.DictReader(io.StringIO(text)))


def test_export_catalog_csv(db, client):
    admin = _admin_token(client, db)
    release = _seed_release(db, artista="Pink Floyd", titulo="The Wall")
    _seed_item(db, release, precio="25.00")

    resp = client.get("/admin/catalog/export.csv", headers=_auth(admin))
    assert resp.status_code == 200
    rows = _csv_rows(resp.text)
    assert len(rows) == 1
    assert rows[0]["artista"] == "Pink Floyd"
    assert rows[0]["precio"] == "25.00"
    assert rows[0]["eliminar"] == ""


def test_import_catalog_csv_actualitza_preu_i_release(db, client):
    admin = _admin_token(client, db)
    release = _seed_release(db, artista="Pink Floyd", titulo="The Wall")
    item = _seed_item(db, release, precio="25.00")

    csv_text = (
        "item_id,release_id,artista,titulo,discogs_release_id,sello,formato,anio,genero,"
        "precio,condicion,estado_disco,estado_funda,status,codi_discogs,eliminar\n"
        f"{item.id},{release.id},Pink Floyd,The Wall,,Harvest,LP,1979,Rock,"
        "30.00,segona_ma,VG+,VG+,disponible,,\n"
    )
    resp = client.post(
        "/admin/catalog/import",
        files={"file": ("catalog.csv", csv_text, "text/csv")},
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["actualitzats"] == 1
    assert body["errors"] == []

    db.refresh(item)
    db.refresh(release)
    assert str(item.price) == "30.00"
    assert item.estado_disco == "VG+"
    assert release.sello == "Harvest"


def test_import_catalog_csv_elimina_item_marcat(db, client):
    admin = _admin_token(client, db)
    release = _seed_release(db, artista="Pink Floyd", titulo="The Wall")
    item = _seed_item(db, release, precio="25.00")

    csv_text = (
        "item_id,release_id,artista,titulo,discogs_release_id,sello,formato,anio,genero,"
        "precio,condicion,estado_disco,estado_funda,status,codi_discogs,eliminar\n"
        f"{item.id},{release.id},Pink Floyd,The Wall,,,LP,,,"
        "25.00,segona_ma,,,disponible,,X\n"
    )
    resp = client.post(
        "/admin/catalog/import",
        files={"file": ("catalog.csv", csv_text, "text/csv")},
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["eliminats"] == 1
    db.expunge(item)
    assert db.scalar(select(Item).where(Item.id == item.id)) is None


def test_import_catalog_csv_no_elimina_item_venut(db, client):
    admin = _admin_token(client, db)
    release = _seed_release(db, artista="Pink Floyd", titulo="The Wall")
    item = _seed_item(db, release, precio="25.00")
    order = Order(contact_email="x@example.com", total=Decimal("25.00"), status=OrderStatus.pagado, shipping_method="recogida")
    db.add(order)
    db.flush()
    db.add(OrderItem(order_id=order.id, item_id=item.id, price=Decimal("25.00")))
    item.status = ItemStatus.vendido
    db.commit()

    csv_text = (
        "item_id,release_id,artista,titulo,discogs_release_id,sello,formato,anio,genero,"
        "precio,condicion,estado_disco,estado_funda,status,codi_discogs,eliminar\n"
        f"{item.id},{release.id},Pink Floyd,The Wall,,,LP,,,"
        "25.00,segona_ma,,,vendido,,X\n"
    )
    resp = client.post(
        "/admin/catalog/import",
        files={"file": ("catalog.csv", csv_text, "text/csv")},
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["eliminats"] == 0
    assert len(body["errors"]) == 1
    db.expire_all()
    assert db.get(Item, item.id) is not None


def test_import_catalog_csv_item_no_trobat(db, client):
    admin = _admin_token(client, db)
    fake_id = "00000000-0000-0000-0000-000000000000"
    csv_text = (
        "item_id,release_id,artista,titulo,discogs_release_id,sello,formato,anio,genero,"
        "precio,condicion,estado_disco,estado_funda,status,codi_discogs,eliminar\n"
        f"{fake_id},{fake_id},X,Y,,,,,,10.00,segona_ma,,,disponible,,\n"
    )
    resp = client.post(
        "/admin/catalog/import",
        files={"file": ("catalog.csv", csv_text, "text/csv")},
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["errors"]) == 1
    assert "no trobat" in body["errors"][0]["motiu"].lower()


# ---------------------------------------------------------------------------
# Enriquir release des de Discogs (vinculació manual d'un discogs_release_id)
# ---------------------------------------------------------------------------

def test_enrich_release_from_discogs(db, client, monkeypatch):
    import app.routers.admin as admin_module

    admin = _admin_token(client, db)
    release = _seed_release(db, discogs_release_id=999888)

    def _fake_enrich(release_arg, db_arg, token_arg=None):
        release_arg.tracklist = [{"pos": "A1", "title": "Cançó", "duration": "3:00"}]
        release_arg.genero = "Rock"
        release_arg.formato = "LP"
        db_arg.commit()
        return True

    monkeypatch.setattr(admin_module.discogs_sync, "enrich_release_from_discogs", _fake_enrich)

    resp = client.post(f"/admin/discogs/sync/releases/{release.id}/enrich", headers=_auth(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert body["genero"] == "Rock"
    assert body["formato"] == "LP"
    assert body["tracklist"][0]["pos"] == "A1"
    db.expire_all()
    assert db.get(Release, release.id).genero == "Rock"


def test_release_needs_sync_per_format_buit():
    from app.routers.admin.discogs_sync import _release_needs_sync

    complet = Release(
        artista="A", title="Complet", formato="LP",
        image_url="http://x/img.jpg", genero="Rock", ean="123", tracklist=[{"pos": "A1"}],
    )
    assert _release_needs_sync(complet) is False

    complet.formato = None
    assert _release_needs_sync(complet) is True


def test_discogs_sync_stats_compta_sense_format(db, client):
    """El botó 'Sync Discogs' (bulk) es basa en aquestes stats per decidir què
    processar: un release sense format ha de comptar, o mai s'inclouria."""
    admin = _admin_token(client, db)
    complet = Release(
        artista="A", title="Complet", formato="LP",
        image_url="http://x/img.jpg", genero="Rock", ean="123", tracklist=[{"pos": "A1"}],
    )
    sense_format = Release(
        artista="B", title="Sense format", formato=None,
        image_url="http://x/img.jpg", genero="Rock", ean="456", tracklist=[{"pos": "A1"}],
    )
    db.add_all([complet, sense_format])
    db.flush()
    db.add_all([Item(release_id=complet.id, price=Decimal("10.00")),
                Item(release_id=sense_format.id, price=Decimal("10.00"))])
    db.commit()

    resp = client.get("/admin/discogs/sync/stats", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json()["sense_format"] == 1


def test_enrich_release_sense_discogs_id(db, client):
    admin = _admin_token(client, db)
    release = _seed_release(db)

    resp = client.post(f"/admin/discogs/sync/releases/{release.id}/enrich", headers=_auth(admin))
    assert resp.status_code == 422


def test_enrich_release_no_trobat(db, client):
    admin = _admin_token(client, db)
    fake_id = "00000000-0000-0000-0000-000000000000"

    resp = client.post(f"/admin/discogs/sync/releases/{fake_id}/enrich", headers=_auth(admin))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Està sonant (portada) — només un disc actiu alhora
# ---------------------------------------------------------------------------

def test_esta_sonant_es_exclusiu(db, client):
    admin = _admin_token(client, db)
    r1 = _seed_release(db, artista="Artista U")
    r2 = _seed_release(db, artista="Artista Dos")

    resp = client.patch(
        f"/admin/releases/{r1.id}/esta-sonant",
        params={"esta_sonant": True},
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    db.refresh(r1)
    assert r1.esta_sonant is True

    # En marcar el segon, el primer es desmarca automàticament.
    resp = client.patch(
        f"/admin/releases/{r2.id}/esta-sonant",
        params={"esta_sonant": True},
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    db.refresh(r1)
    db.refresh(r2)
    assert r1.esta_sonant is False
    assert r2.esta_sonant is True


def test_catalog_filtra_per_esta_sonant(db, client):
    r1 = _seed_release(db, artista="Artista U")
    _seed_item(db, r1)
    r2 = _seed_release(db, artista="Artista Dos")
    _seed_item(db, r2)
    r2.esta_sonant = True
    db.commit()

    resp = client.get("/catalog", params={"esta_sonant": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["results"][0]["id"] == str(r2.id)
