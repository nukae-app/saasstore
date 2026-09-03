"""Tests del flux de sol·licituds de compra: sol·licitud (sense proveïdor) ->
resoldre cap a una comanda real d'un proveïdor concret."""

import contextlib
import io
import re
import uuid

from sqlalchemy import select

from app.models import (
    CondicionItem, EstadoSolicitud, Item, ItemStatus, OrigenSolicitud, Proveedor, Release, SolicitudCompra,
    SolicitudCompraLinea, User,
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
    user.role = "admin"
    db.commit()
    return access


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _seed_release(db, artista="Artista", titulo="Àlbum") -> Release:
    r = Release(artista=artista, title=titulo, formato="LP")
    db.add(r)
    db.commit()
    return r


def _seed_proveedor(db, nombre="DistroX", email="prov@example.com") -> Proveedor:
    p = Proveedor(name=nombre, email=email)
    db.add(p)
    db.commit()
    return p


def test_crear_solicitud_con_release_existente(db, client):
    admin = _admin_token(client, db)
    release = _seed_release(db)

    payload = {
        "lineas": [{"release_id": str(release.id), "quantity": 2, "notes": "reposició"}],
    }
    resp = client.post("/admin/solicitudes-compra", json=payload, headers=_auth(admin))
    assert resp.status_code == 201
    body = resp.json()
    assert body["estado"] == "oberta"
    assert body["origen"] == "manual"
    assert len(body["lineas"]) == 1
    assert body["lineas"][0]["artist"] == "Artista"
    assert body["lineas"][0]["quantity"] == 2
    assert body["lineas"][0]["resuelta"] is False


def test_crear_solicitud_con_disco_no_catalogado(db, client):
    admin = _admin_token(client, db)

    payload = {
        "lineas": [{"artist": "Nou Grup", "title": "Nou Disc", "label": "Segell X", "quantity": 1}],
    }
    resp = client.post("/admin/solicitudes-compra", json=payload, headers=_auth(admin))
    assert resp.status_code == 201
    body = resp.json()
    assert body["lineas"][0]["release_id"] is None
    assert body["lineas"][0]["artist"] == "Nou Grup"


def test_crear_solicitud_con_solo_title_sin_artista(db, client):
    """§17.1: `artist` es detalle opcional (solo tiene sentido para discos);
    el mínimo para describir una línea sin catálogo es `title`, genérico a
    cualquier vertical (p. ej. una vertical de café sin campo 'artista')."""
    admin = _admin_token(client, db)
    payload = {"lineas": [{"title": "Cafè de Kenya", "quantity": 1}]}
    resp = client.post("/admin/solicitudes-compra", json=payload, headers=_auth(admin))
    assert resp.status_code == 201
    body = resp.json()
    assert body["lineas"][0]["release_id"] is None
    assert body["lineas"][0]["title"] == "Cafè de Kenya"
    assert body["lineas"][0]["artist"] is None


def test_crear_solicitud_sin_release_ni_artista_falla(db, client):
    admin = _admin_token(client, db)
    payload = {"lineas": [{"quantity": 1}]}
    resp = client.post("/admin/solicitudes-compra", json=payload, headers=_auth(admin))
    assert resp.status_code == 422


def test_resolver_solicitud_crea_comanda(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = _seed_release(db)

    solicitud = client.post(
        "/admin/solicitudes-compra",
        json={"lineas": [{"release_id": str(release.id), "quantity": 3}]},
        headers=_auth(admin),
    ).json()
    linea_id = solicitud["lineas"][0]["id"]

    resp = client.post(
        "/admin/solicitudes-compra/resolver",
        json={
            "proveedor_id": str(prov.id),
            "date": "2026-06-01T10:00:00",
            "lineas": [{"solicitud_linea_id": linea_id, "estimated_unit_price": "10.00"}],
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    comanda = resp.json()
    assert comanda["proveedor_id"] == str(prov.id)
    assert comanda["lineas"][0]["quantity"] == 3

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
        json={"lineas": [{"artist": "X", "title": "Y", "quantity": 1}]},
        headers=_auth(admin),
    ).json()
    linea_id = solicitud["lineas"][0]["id"]

    resp = client.post(
        "/admin/solicitudes-compra/resolver",
        json={
            "proveedor_id": str(prov.id),
            "date": "2026-06-01T10:00:00",
            "lineas": [{"solicitud_linea_id": linea_id}],
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 422


def test_resolver_solicitud_amb_release_id_al_payload_resol_linia_sense_catalogar(db, client):
    """Una línia creada a mà (sense release_id, disc encara no al catàleg)
    es pot resoldre aportant el release_id en aquest mateix pas — ja no cal
    sortir a donar d'alta el disc abans."""
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = _seed_release(db, "Artista Nou", "Disc acabat de catalogar")

    solicitud = client.post(
        "/admin/solicitudes-compra",
        json={"lineas": [{"artist": "Artista Nou", "title": "Disc acabat de catalogar", "quantity": 2}]},
        headers=_auth(admin),
    ).json()
    linea_id = solicitud["lineas"][0]["id"]
    assert solicitud["lineas"][0]["release_id"] is None

    resp = client.post(
        "/admin/solicitudes-compra/resolver",
        json={
            "proveedor_id": str(prov.id),
            "date": "2026-06-01T10:00:00",
            "lineas": [{"solicitud_linea_id": linea_id, "release_id": str(release.id)}],
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    comanda = resp.json()
    assert comanda["lineas"][0]["release_id"] == str(release.id)

    solicitud_actualitzada = client.get(
        f"/admin/solicitudes-compra/{solicitud['id']}", headers=_auth(admin)
    ).json()
    assert solicitud_actualitzada["lineas"][0]["release_id"] == str(release.id)
    assert solicitud_actualitzada["lineas"][0]["resuelta"] is True


def test_resolver_solicitud_amb_release_id_inexistent_falla(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)

    solicitud = client.post(
        "/admin/solicitudes-compra",
        json={"lineas": [{"artist": "X", "title": "Y", "quantity": 1}]},
        headers=_auth(admin),
    ).json()
    linea_id = solicitud["lineas"][0]["id"]

    resp = client.post(
        "/admin/solicitudes-compra/resolver",
        json={
            "proveedor_id": str(prov.id),
            "date": "2026-06-01T10:00:00",
            "lineas": [{"solicitud_linea_id": linea_id, "release_id": str(uuid.uuid4())}],
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 404


def test_resolver_linia_ya_resuelta_falla(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = _seed_release(db)

    solicitud = client.post(
        "/admin/solicitudes-compra",
        json={"lineas": [{"release_id": str(release.id), "quantity": 1}]},
        headers=_auth(admin),
    ).json()
    linea_id = solicitud["lineas"][0]["id"]
    resolver_payload = {
        "proveedor_id": str(prov.id), "date": "2026-06-01T10:00:00",
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
            {"release_id": str(r1.id), "quantity": 1},
            {"release_id": str(r2.id), "quantity": 1},
        ]},
        headers=_auth(admin),
    ).json()
    linea1_id = solicitud["lineas"][0]["id"]

    client.post(
        "/admin/solicitudes-compra/resolver",
        json={
            "proveedor_id": str(prov.id), "date": "2026-06-01T10:00:00",
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
        json={"lineas": [{"release_id": str(release.id), "quantity": 1}]},
        headers=_auth(admin),
    ).json()
    linea_id = solicitud["lineas"][0]["id"]
    client.post(
        "/admin/solicitudes-compra/resolver",
        json={
            "proveedor_id": str(prov.id), "date": "2026-06-01T10:00:00",
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
        json={"lineas": [{"release_id": str(release.id), "quantity": 1}]},
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
        json={"lineas": [{"release_id": str(release.id), "quantity": 1}]},
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
        json={"lineas": [{"release_id": str(release.id), "quantity": 1}]},
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
        json={"lineas": [{"release_id": str(release.id), "quantity": 1}]},
        headers=_auth(admin),
    ).json()
    linea_id = solicitud["lineas"][0]["id"]

    item = Item(release_id=release.id, price=20, condition=CondicionItem.segona_ma, status=ItemStatus.disponible)
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
        json={"lineas": [{"release_id": str(release.id), "quantity": 1}]},
        headers=_auth(admin),
    ).json()
    linea_id = solicitud["lineas"][0]["id"]

    item1 = Item(release_id=release.id, price=20, condition=CondicionItem.segona_ma, status=ItemStatus.disponible)
    item2 = Item(release_id=release.id, price=22, condition=CondicionItem.segona_ma, status=ItemStatus.disponible)
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
        json={"lineas": [{"release_id": str(release.id), "quantity": 1}]},
        headers=_auth(admin),
    ).json()
    linea_id = solicitud["lineas"][0]["id"]

    item = Item(release_id=release.id, price=20, condition=CondicionItem.segona_ma, status=ItemStatus.disponible)
    db.add(item)
    db.commit()
    client.post(
        f"/admin/solicitudes-compra/lineas/{linea_id}/resoldre-estoc",
        json={"item_id": str(item.id)},
        headers=_auth(admin),
    )

    resp = client.delete(f"/admin/solicitudes-compra/{solicitud['id']}/lineas/{linea_id}", headers=_auth(admin))
    assert resp.status_code == 409


def test_refill_sugerencias_no_falla_amb_candidats_reals(db, client):
    """Regressió: _suggest_proveedor_para_release feia servir HistorialCompra
    sense importar-la — l'endpoint només "funcionava" quan no hi havia cap
    candidat (el bucle mai s'executava). Amb estoc baix + vendes recents,
    abans d'aquest fix petava amb NameError."""
    from datetime import datetime, timezone
    from decimal import Decimal

    from app.models import HistorialCompra, Order, OrderItem, OrderStatus

    admin = _admin_token(client, db)
    release = _seed_release(db, "Artista Refill", "Poc estoc")
    proveedor = _seed_proveedor(db, "Distro Refill")

    # 1 unitat disponible, s'ha venut 10 cops en els últims 60 dies -> estoc
    # urgent (dies_estoc molt per sota del llindar de 21).
    item = Item(
        release_id=release.id, price=Decimal("20.00"), acquisition_cost=Decimal("10.00"),
        condition=CondicionItem.nou, quantity=1, status=ItemStatus.disponible,
    )
    db.add(item)
    db.flush()

    for _ in range(10):
        order = Order(
            contact_email="client@example.com", status=OrderStatus.pagado,
            total=Decimal("20.00"), shipping_method="recogida_tienda",
        )
        db.add(order)
        db.flush()
        db.add(OrderItem(
            order_id=order.id, item_id=item.id, release_id=release.id,
            price=Decimal("20.00"), condition=CondicionItem.nou, quantity=1,
        ))

    # Historial de compra a aquest proveïdor per aquest mateix release —
    # exerceix exactament la línia que fallava per la importació que faltava.
    db.add(HistorialCompra(
        proveedor_id=proveedor.id, date=datetime.now(timezone.utc).date(),
        artist=release.artista, title=release.title, release_id=release.id,
        quantity=5, cost_price=Decimal("10.00"),
    ))
    db.commit()

    resp = client.get("/admin/solicitudes-compra/refill-sugerencias", headers=_auth(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["release_id"] == str(release.id)
    assert body[0]["proveedor_sugerido_id"] == str(proveedor.id)
    assert body[0]["proveedor_sugerido_nombre"] == "Distro Refill"


def test_pool_lineas_aplana_i_pagina(db, client):
    """El pool ha de mostrar línies de sol·licituds diferents (i orígens
    diferents) com una sola llista, amb l'artista/títol resolt des del
    catàleg quan la línia té release_id (veure comentari a Release.artista
    sobre per què cal el join a RecordProduct, no Release.artista)."""
    admin = _admin_token(client, db)
    release = _seed_release(db, "Artista Catalogat", "Disc del catàleg")

    client.post(
        "/admin/solicitudes-compra",
        json={"lineas": [{"release_id": str(release.id), "quantity": 2}]},
        headers=_auth(admin),
    )
    client.post(
        "/admin/solicitudes-compra",
        json={"lineas": [{"title": "Disc sense catalogar", "quantity": 1}]},
        headers=_auth(admin),
    )

    resp = client.get("/admin/solicitudes-compra/pool", headers=_auth(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert body["page"] == 1
    titles = {l["title"] for l in body["results"]}
    assert titles == {"Disc del catàleg", "Disc sense catalogar"}
    catalogada = next(l for l in body["results"] if l["title"] == "Disc del catàleg")
    assert catalogada["artist"] == "Artista Catalogat"
    assert catalogada["origen"] == "manual"

    pag1 = client.get("/admin/solicitudes-compra/pool?page_size=1&page=1", headers=_auth(admin)).json()
    pag2 = client.get("/admin/solicitudes-compra/pool?page_size=1&page=2", headers=_auth(admin)).json()
    assert len(pag1["results"]) == 1
    assert len(pag2["results"]) == 1
    assert pag1["results"][0]["id"] != pag2["results"][0]["id"]


def test_pool_lineas_filtra_per_estat_origen_i_cerca(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = _seed_release(db, "Reposició Band", "Reposar-me")

    manual = client.post(
        "/admin/solicitudes-compra",
        json={"lineas": [{"title": "Pendent Manual", "quantity": 1}]},
        headers=_auth(admin),
    ).json()
    refill = client.post(
        "/admin/solicitudes-compra",
        json={"origen": "refill_stock", "lineas": [{"release_id": str(release.id), "quantity": 1}]},
        headers=_auth(admin),
    ).json()
    cancelada = client.post(
        "/admin/solicitudes-compra",
        json={"lineas": [{"title": "Es cancel·la", "quantity": 1}]},
        headers=_auth(admin),
    ).json()
    client.patch(f"/admin/solicitudes-compra/{cancelada['id']}/cancelar", headers=_auth(admin))

    resp = client.post(
        "/admin/solicitudes-compra/resolver",
        json={
            "proveedor_id": str(prov.id),
            "date": "2026-06-01T10:00:00",
            "lineas": [{"solicitud_linea_id": refill["lineas"][0]["id"]}],
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 201

    pendents = client.get("/admin/solicitudes-compra/pool", headers=_auth(admin)).json()
    assert [l["title"] for l in pendents["results"]] == ["Pendent Manual"]

    resoltes = client.get("/admin/solicitudes-compra/pool?estado=resolta", headers=_auth(admin)).json()
    assert [l["title"] for l in resoltes["results"]] == ["Reposar-me"]

    cancelades = client.get("/admin/solicitudes-compra/pool?estado=cancelada", headers=_auth(admin)).json()
    assert [l["title"] for l in cancelades["results"]] == ["Es cancel·la"]

    totes = client.get("/admin/solicitudes-compra/pool?estado=totes", headers=_auth(admin)).json()
    assert totes["total"] == 3

    per_origen = client.get("/admin/solicitudes-compra/pool?estado=totes&origen=refill_stock", headers=_auth(admin)).json()
    assert [l["title"] for l in per_origen["results"]] == ["Reposar-me"]

    per_cerca = client.get("/admin/solicitudes-compra/pool?estado=totes&q=cancel", headers=_auth(admin)).json()
    assert [l["title"] for l in per_cerca["results"]] == ["Es cancel·la"]
