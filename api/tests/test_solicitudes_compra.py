"""Tests del flux de sol·licituds de compra: pool (línies soltes, sense
sol·licitud) -> generar sol·licitud (consolida línies seleccionades, les
numera) -> resoldre cap a una comanda real d'un proveïdor concret."""

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


def _add_pool(client, admin, lineas, origen="manual") -> list[dict]:
    resp = client.post(
        "/admin/solicitudes-compra/pool",
        json={"origen": origen, "lineas": lineas},
        headers=_auth(admin),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _crear_solicitud(client, admin, lineas, origen="manual", notes=None) -> dict:
    """Flux complet: afegeix línies al pool i les consolida en una nova
    sol·licitud numerada, tal com faria l'admin des de la pantalla."""
    pool_lineas = _add_pool(client, admin, lineas, origen=origen)
    resp = client.post(
        "/admin/solicitudes-compra/generar",
        json={"linea_ids": [l["id"] for l in pool_lineas], "notes": notes},
        headers=_auth(admin),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_pool_afegeix_linia_con_release_existente(db, client):
    admin = _admin_token(client, db)
    release = _seed_release(db)

    lineas = _add_pool(client, admin, [{"release_id": str(release.id), "quantity": 2, "notes": "reposició"}])
    assert len(lineas) == 1
    assert lineas[0]["artist"] == "Artista"
    assert lineas[0]["quantity"] == 2
    assert lineas[0]["resuelta"] is False
    assert lineas[0]["origen"] == "manual"


def test_pool_afegeix_linia_con_disco_no_catalogado(db, client):
    admin = _admin_token(client, db)
    lineas = _add_pool(client, admin, [{"artist": "Nou Grup", "title": "Nou Disc", "label": "Segell X", "quantity": 1}])
    assert lineas[0]["release_id"] is None
    assert lineas[0]["artist"] == "Nou Grup"


def test_pool_afegeix_linia_con_solo_title_sin_artista(db, client):
    """§17.1: `artist` es detalle opcional (solo tiene sentido para discos);
    el mínimo para describir una línea sin catálogo es `title`, genérico a
    cualquier vertical (p. ej. una vertical de café sin campo 'artista')."""
    admin = _admin_token(client, db)
    lineas = _add_pool(client, admin, [{"title": "Cafè de Kenya", "quantity": 1}])
    assert lineas[0]["release_id"] is None
    assert lineas[0]["title"] == "Cafè de Kenya"
    assert lineas[0]["artist"] is None


def test_pool_afegeix_linia_sin_release_ni_artista_falla(db, client):
    admin = _admin_token(client, db)
    resp = client.post(
        "/admin/solicitudes-compra/pool", json={"lineas": [{"quantity": 1}]}, headers=_auth(admin),
    )
    assert resp.status_code == 422


def test_generar_solicitud_consolida_linies_de_diversos_origens(db, client):
    """Una sol·licitud consolidada pot barrejar línies de diversos orígens
    (per això `origen` viu a la línia, no a la sol·licitud)."""
    admin = _admin_token(client, db)
    release = _seed_release(db)

    manuals = _add_pool(client, admin, [{"title": "Manual A", "quantity": 1}], origen="manual")
    refills = _add_pool(client, admin, [{"release_id": str(release.id), "quantity": 1}], origen="refill_stock")

    resp = client.post(
        "/admin/solicitudes-compra/generar",
        json={"linea_ids": [manuals[0]["id"], refills[0]["id"]], "notes": "lot mixt"},
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    solicitud = resp.json()
    assert solicitud["estado"] == "oberta"
    assert sorted(solicitud["origenes"]) == ["manual", "refill_stock"]
    assert len(solicitud["lineas"]) == 2
    assert solicitud["notes"] == "lot mixt"


def test_generar_solicitud_amb_linia_ja_consolidada_falla(db, client):
    admin = _admin_token(client, db)
    lineas = _add_pool(client, admin, [{"title": "X", "quantity": 1}])
    linea_id = lineas[0]["id"]
    client.post("/admin/solicitudes-compra/generar", json={"linea_ids": [linea_id]}, headers=_auth(admin))

    resp = client.post("/admin/solicitudes-compra/generar", json={"linea_ids": [linea_id]}, headers=_auth(admin))
    assert resp.status_code == 409


def test_eliminar_linia_pool(db, client):
    admin = _admin_token(client, db)
    lineas = _add_pool(client, admin, [{"title": "Es treu", "quantity": 1}])
    linea_id = lineas[0]["id"]

    resp = client.delete(f"/admin/solicitudes-compra/pool/lineas/{linea_id}", headers=_auth(admin))
    assert resp.status_code == 204
    assert db.get(SolicitudCompraLinea, uuid.UUID(linea_id)) is None


def test_eliminar_linia_pool_ja_consolidada_falla(db, client):
    admin = _admin_token(client, db)
    lineas = _add_pool(client, admin, [{"title": "X", "quantity": 1}])
    linea_id = lineas[0]["id"]
    client.post("/admin/solicitudes-compra/generar", json={"linea_ids": [linea_id]}, headers=_auth(admin))

    resp = client.delete(f"/admin/solicitudes-compra/pool/lineas/{linea_id}", headers=_auth(admin))
    assert resp.status_code == 404


def test_resolver_solicitud_crea_comanda(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = _seed_release(db)

    solicitud = _crear_solicitud(client, admin, [{"release_id": str(release.id), "quantity": 3}])
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


def test_resolver_linia_de_pool_sense_consolidar_falla(db, client):
    """No es pot saltar el pas "Crear sol·licitud": cal consolidar la
    línia abans de poder-la resoldre cap a una comanda."""
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = _seed_release(db)
    lineas = _add_pool(client, admin, [{"release_id": str(release.id), "quantity": 1}])

    resp = client.post(
        "/admin/solicitudes-compra/resolver",
        json={
            "proveedor_id": str(prov.id),
            "date": "2026-06-01T10:00:00",
            "lineas": [{"solicitud_linea_id": lineas[0]["id"]}],
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 422


def test_resolver_solicitud_sense_release_falla(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)

    solicitud = _crear_solicitud(client, admin, [{"artist": "X", "title": "Y", "quantity": 1}])
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

    solicitud = _crear_solicitud(
        client, admin, [{"artist": "Artista Nou", "title": "Disc acabat de catalogar", "quantity": 2}],
    )
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

    solicitud = _crear_solicitud(client, admin, [{"artist": "X", "title": "Y", "quantity": 1}])
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

    solicitud = _crear_solicitud(client, admin, [{"release_id": str(release.id), "quantity": 1}])
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

    solicitud = _crear_solicitud(client, admin, [
        {"release_id": str(r1.id), "quantity": 1},
        {"release_id": str(r2.id), "quantity": 1},
    ])
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

    solicitud = _crear_solicitud(client, admin, [{"release_id": str(release.id), "quantity": 1}])
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
    solicitud = _crear_solicitud(client, admin, [{"release_id": str(release.id), "quantity": 1}])

    resp = client.patch(f"/admin/solicitudes-compra/{solicitud['id']}/cancelar", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json()["estado"] == "cancelada"

    resp2 = client.patch(f"/admin/solicitudes-compra/{solicitud['id']}/cancelar", headers=_auth(admin))
    assert resp2.status_code == 409


def test_eliminar_solicitud_sense_resoldre(db, client):
    admin = _admin_token(client, db)
    release = _seed_release(db)
    solicitud = _crear_solicitud(client, admin, [{"release_id": str(release.id), "quantity": 1}])

    resp = client.delete(f"/admin/solicitudes-compra/{solicitud['id']}", headers=_auth(admin))
    assert resp.status_code == 204
    assert db.get(SolicitudCompra, uuid.UUID(solicitud["id"])) is None


def test_list_solicitudes_filtra_per_estat(db, client):
    admin = _admin_token(client, db)
    release = _seed_release(db)
    solicitud = _crear_solicitud(client, admin, [{"release_id": str(release.id), "quantity": 1}])
    client.patch(f"/admin/solicitudes-compra/{solicitud['id']}/cancelar", headers=_auth(admin))

    obertes = client.get("/admin/solicitudes-compra?estado=oberta", headers=_auth(admin)).json()["results"]
    assert all(s["estado"] == "oberta" for s in obertes)
    cancelades = client.get("/admin/solicitudes-compra?estado=cancelada", headers=_auth(admin)).json()["results"]
    assert any(s["id"] == solicitud["id"] for s in cancelades)


def test_resoldre_estoc_manual_tanca_linia_sense_comanda(db, client):
    admin = _admin_token(client, db)
    release = _seed_release(db)
    solicitud = _crear_solicitud(client, admin, [{"release_id": str(release.id), "quantity": 1}])
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
    assert body["resuelta"] is True
    assert body["item_resuelto_id"] == str(item.id)

    solicitud_actualitzada = client.get(
        f"/admin/solicitudes-compra/{solicitud['id']}", headers=_auth(admin)
    ).json()
    assert solicitud_actualitzada["estado"] == "resolta"

    db.expire_all()
    item_db = db.get(Item, item.id)
    assert item_db.status.value == "reservado"


def test_resoldre_estoc_directament_des_del_pool_sense_consolidar(db, client):
    """Resoldre des d'estoc no requereix haver creat la sol·licitud primer:
    si ja hi ha exemplar, no cal formalitzar-ne la compra."""
    admin = _admin_token(client, db)
    release = _seed_release(db)
    lineas = _add_pool(client, admin, [{"release_id": str(release.id), "quantity": 1}])
    linea_id = lineas[0]["id"]

    item = Item(release_id=release.id, price=20, condition=CondicionItem.segona_ma, status=ItemStatus.disponible)
    db.add(item)
    db.commit()

    resp = client.post(
        f"/admin/solicitudes-compra/lineas/{linea_id}/resoldre-estoc",
        json={"item_id": str(item.id)},
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    assert resp.json()["resuelta"] is True

    db.expire_all()
    linea_db = db.get(SolicitudCompraLinea, uuid.UUID(linea_id))
    assert linea_db.solicitud_id is None


def test_resoldre_estoc_linia_ja_resolta_falla(db, client):
    admin = _admin_token(client, db)
    release = _seed_release(db)
    solicitud = _crear_solicitud(client, admin, [{"release_id": str(release.id), "quantity": 1}])
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
    solicitud = _crear_solicitud(client, admin, [{"release_id": str(release.id), "quantity": 1}])
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
    """El pool ha de mostrar totes les línies soltes (sense sol·licitud)
    com una sola llista, amb l'artista/títol resolt des del catàleg quan la
    línia té release_id (veure comentari a Release.artista sobre per què
    cal el join a RecordProduct, no Release.artista)."""
    admin = _admin_token(client, db)
    release = _seed_release(db, "Artista Catalogat", "Disc del catàleg")

    _add_pool(client, admin, [{"release_id": str(release.id), "quantity": 2}])
    _add_pool(client, admin, [{"title": "Disc sense catalogar", "quantity": 1}])

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
    release = _seed_release(db, "Reposició Band", "Reposar-me")

    # Pendent: queda solta al pool.
    _add_pool(client, admin, [{"title": "Pendent Manual", "quantity": 1}])

    # Resolta directament des del pool, sense consolidar-se mai en cap
    # sol·licitud.
    refill_lineas = _add_pool(client, admin, [{"release_id": str(release.id), "quantity": 1}], origen="refill_stock")
    item = Item(release_id=release.id, price=20, condition=CondicionItem.segona_ma, status=ItemStatus.disponible)
    db.add(item)
    db.commit()
    resp = client.post(
        f"/admin/solicitudes-compra/lineas/{refill_lineas[0]['id']}/resoldre-estoc",
        json={"item_id": str(item.id)},
        headers=_auth(admin),
    )
    assert resp.status_code == 200

    # Consolidada en una sol·licitud (encara que després es cancel·li): ja
    # no és del pool.
    consolidable = _add_pool(client, admin, [{"title": "Es consolida", "quantity": 1}])
    gen = client.post(
        "/admin/solicitudes-compra/generar",
        json={"linea_ids": [consolidable[0]["id"]]},
        headers=_auth(admin),
    ).json()
    client.patch(f"/admin/solicitudes-compra/{gen['id']}/cancelar", headers=_auth(admin))

    pendents = client.get("/admin/solicitudes-compra/pool", headers=_auth(admin)).json()
    assert [l["title"] for l in pendents["results"]] == ["Pendent Manual"]

    resoltes = client.get("/admin/solicitudes-compra/pool?estado=resolta", headers=_auth(admin)).json()
    assert [l["title"] for l in resoltes["results"]] == ["Reposar-me"]

    totes = client.get("/admin/solicitudes-compra/pool?estado=totes", headers=_auth(admin)).json()
    # Només 2: la consolidada ha sortit del pool en generar-se la sol·licitud.
    assert totes["total"] == 2

    per_origen = client.get("/admin/solicitudes-compra/pool?estado=totes&origen=refill_stock", headers=_auth(admin)).json()
    assert [l["title"] for l in per_origen["results"]] == ["Reposar-me"]

    per_cerca = client.get("/admin/solicitudes-compra/pool?estado=totes&q=Pendent", headers=_auth(admin)).json()
    assert [l["title"] for l in per_cerca["results"]] == ["Pendent Manual"]


def test_solicituds_tenen_numero_correlatiu_per_any(db, client):
    """Cada sol·licitud rep un número humà ("SOL-{any}-{seq}"), correlatiu
    per tenant+any, assignat en consolidar-se — mateix patró que
    Comanda/Pressupost/Albara, veure DocumentCounter."""
    from datetime import datetime, timezone

    admin = _admin_token(client, db)
    any_actual = datetime.now(timezone.utc).year

    s1 = _crear_solicitud(client, admin, [{"title": "U", "quantity": 1}])
    s2 = _crear_solicitud(client, admin, [{"title": "Dos", "quantity": 1}])

    assert s1["numero"] == f"SOL-{any_actual}-000001"
    assert s2["numero"] == f"SOL-{any_actual}-000002"
