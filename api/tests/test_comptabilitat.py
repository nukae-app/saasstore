"""Tests del flux de facturació de proveïdor: recepcions (albarà) -> factura (Despesa)."""

import contextlib
import io
import re
import uuid
from decimal import Decimal

from sqlalchemy import select

from app.models import Compra, Proveedor, Release, User


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


def _seed_release(db) -> Release:
    r = Release(artista="Artista", titulo="Àlbum", formato="LP")
    db.add(r)
    db.commit()
    return r


def _seed_proveedor(db, dies_pagament=30) -> Proveedor:
    p = Proveedor(nombre="DistroX", email="prov@example.com", dies_pagament=dies_pagament)
    db.add(p)
    db.commit()
    return p


def _crear_i_rebre_comanda(client, admin, db, prov, release, num_albaran):
    payload = {
        "proveedor_id": str(prov.id), "fecha": "2026-06-01T10:00:00",
        "lineas": [{"release_id": str(release.id), "cantidad": 1, "precio_unitario_estimado": "10.00"}],
    }
    comanda = client.post("/admin/comandas", json=payload, headers=_auth(admin)).json()
    client.patch(f"/admin/comandas/{comanda['id']}/marcar-enviada", headers=_auth(admin))
    recepcio = {
        "fecha": "2026-06-05T10:00:00",
        "num_albaran": num_albaran,
        "items": [{"comanda_linea_id": comanda["lineas"][0]["id"], "precio": "20.00", "coste_adquisicion": "10.00"}],
    }
    resp = client.post(f"/admin/comandas/{comanda['id']}/recepcio", json=recepcio, headers=_auth(admin))
    assert resp.status_code == 201
    return resp.json()["compra_id"]


def test_recepcio_sense_facturar_apareix_a_llista(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = _seed_release(db)
    compra_id = _crear_i_rebre_comanda(client, admin, db, prov, release, "ALB-1")

    resp = client.get("/admin/compras?tipo=proveedor&sense_facturar=true", headers=_auth(admin))
    assert resp.status_code == 200
    assert compra_id in [c["id"] for c in resp.json()]


def test_facturar_una_recepcio_crea_despesa_pendent(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = _seed_release(db)
    compra_id = _crear_i_rebre_comanda(client, admin, db, prov, release, "ALB-1")

    resp = client.post(
        "/admin/despeses/des-de-compres",
        json={"compra_ids": [compra_id], "num_factura": "FAC-1", "data_factura": "2026-06-10"},
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    despesa = resp.json()
    assert despesa["estat_pagament"] == "pendent"
    assert despesa["compra_ids"] == [compra_id]
    assert Decimal(despesa["total"]) == Decimal("10.00")
    assert despesa["data_venciment"] == "2026-07-10"  # dies_pagament=30

    pendents = client.get("/admin/despeses/pendents", headers=_auth(admin)).json()
    assert any(d["id"] == despesa["id"] for d in pendents)

    db.expire_all()
    compra = db.get(Compra, uuid.UUID(compra_id))
    assert str(compra.despesa_id) == despesa["id"]


def test_facturar_diverses_recepcions_junta(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = _seed_release(db)
    compra_1 = _crear_i_rebre_comanda(client, admin, db, prov, release, "ALB-1")
    compra_2 = _crear_i_rebre_comanda(client, admin, db, prov, release, "ALB-2")

    resp = client.post(
        "/admin/despeses/des-de-compres",
        json={"compra_ids": [compra_1, compra_2], "num_factura": "FAC-2"},
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    despesa = resp.json()
    assert set(despesa["compra_ids"]) == {compra_1, compra_2}
    assert Decimal(despesa["total"]) == Decimal("20.00")


def test_no_es_pot_facturar_dos_cops_la_mateixa_recepcio(db, client):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    release = _seed_release(db)
    compra_id = _crear_i_rebre_comanda(client, admin, db, prov, release, "ALB-1")

    client.post(
        "/admin/despeses/des-de-compres",
        json={"compra_ids": [compra_id], "num_factura": "FAC-1"},
        headers=_auth(admin),
    )
    resp = client.post(
        "/admin/despeses/des-de-compres",
        json={"compra_ids": [compra_id], "num_factura": "FAC-1-bis"},
        headers=_auth(admin),
    )
    assert resp.status_code == 409


def test_no_es_poden_barrejar_proveidors_diferents(db, client):
    admin = _admin_token(client, db)
    prov1 = _seed_proveedor(db)
    prov1.nombre = "Prov 1"
    db.add(Proveedor(nombre="Prov 2", email="p2@example.com"))
    db.commit()
    prov2 = db.scalar(select(Proveedor).where(Proveedor.nombre == "Prov 2"))
    release = _seed_release(db)
    compra_1 = _crear_i_rebre_comanda(client, admin, db, prov1, release, "ALB-1")
    compra_2 = _crear_i_rebre_comanda(client, admin, db, prov2, release, "ALB-2")

    resp = client.post(
        "/admin/despeses/des-de-compres",
        json={"compra_ids": [compra_1, compra_2], "num_factura": "FAC-X"},
        headers=_auth(admin),
    )
    assert resp.status_code == 422
