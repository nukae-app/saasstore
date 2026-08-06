"""Tests del sistema de tipus d'IVA: gestió de tipus, càlcul automàtic a vendes
(general sobre preu per discos nous, REBU sobre marge per 2a mà) i informe trimestral."""

import contextlib
import io
import re
from decimal import Decimal

from sqlalchemy import select

from app.models import CondicionItem, Item, Release, TipusIva, User


def _seed_release(db, artista="Artista", titulo="Àlbum", formato="LP") -> Release:
    r = Release(artista=artista, titulo=titulo, formato=formato)
    db.add(r)
    db.commit()
    return r


def _seed_item(db, release, precio="20.00", coste="10.00", condicion=CondicionItem.nou) -> Item:
    item = Item(
        release_id=release.id,
        precio=Decimal(precio),
        coste_adquisicion=Decimal(coste),
        condicion=condicion,
    )
    db.add(item)
    db.commit()
    return item


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


def _seed_tipus_iva(db, *, nou_pct="21.00", rebu_pct="21.00") -> tuple[TipusIva, TipusIva]:
    general = TipusIva(nom="General", percentatge=Decimal(nou_pct), per_defecte_nou=True, actiu=True)
    rebu = TipusIva(nom="REBU", percentatge=Decimal(rebu_pct), es_rebu=True, per_defecte_segona_ma=True, actiu=True)
    db.add_all([general, rebu])
    db.commit()
    return general, rebu


# ---------------------------------------------------------------------------
# CRUD tipus d'IVA
# ---------------------------------------------------------------------------

def test_crud_tipus_iva(db, client):
    admin = _admin_token(client, db)

    resp = client.post(
        "/admin/tipus-iva",
        json={"nom": "General 21%", "percentatge": "21.00", "per_defecte_nou": True},
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    tipus_id = resp.json()["id"]

    resp = client.get("/admin/tipus-iva", headers=_auth(admin))
    assert resp.status_code == 200
    assert any(t["id"] == tipus_id for t in resp.json())

    resp = client.patch(f"/admin/tipus-iva/{tipus_id}", json={"percentatge": "10.00"}, headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json()["percentatge"] == "10.00"


def test_nomes_un_tipus_per_defecte_nou_actiu(db, client):
    """Marcar un segon tipus com a per_defecte_nou desmarca l'anterior."""
    admin = _admin_token(client, db)
    r1 = client.post(
        "/admin/tipus-iva",
        json={"nom": "A", "percentatge": "21.00", "per_defecte_nou": True},
        headers=_auth(admin),
    ).json()
    r2 = client.post(
        "/admin/tipus-iva",
        json={"nom": "B", "percentatge": "10.00", "per_defecte_nou": True},
        headers=_auth(admin),
    ).json()

    db.refresh(db.get(TipusIva, r1["id"]))
    t1 = db.get(TipusIva, r1["id"])
    t2 = db.get(TipusIva, r2["id"])
    assert t1.per_defecte_nou is False
    assert t2.per_defecte_nou is True


# ---------------------------------------------------------------------------
# Càlcul automàtic d'IVA a la venda (TPV mostrador)
# ---------------------------------------------------------------------------

def test_venta_mostrador_disco_nou_aplica_iva_general(db, client):
    admin = _admin_token(client, db)
    _seed_tipus_iva(db)
    release = _seed_release(db)
    item = _seed_item(db, release, precio="25.00", coste="12.00", condicion=CondicionItem.nou)

    resp = client.post(
        "/admin/ventas-externas",
        json={"item_id": str(item.id), "canal": "mostrador", "precio_venta": "25.00", "fecha": "2026-06-11T16:00:00"},
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["iva_pct"] == "21.00"
    # IVA sobre el preu total (25 / 1.21 * 0.21)
    assert data["iva_import"] == "4.34"


def test_venta_mostrador_disco_segona_ma_rebu_aplica_iva_sobre_marge(db, client):
    admin = _admin_token(client, db)
    _seed_tipus_iva(db)
    release = _seed_release(db)
    # Cost 10, venda 25 -> marge 15. IVA del marge: 15 * 21/121
    item = _seed_item(db, release, precio="25.00", coste="10.00", condicion=CondicionItem.segona_ma)

    resp = client.post(
        "/admin/ventas-externas",
        json={"item_id": str(item.id), "canal": "mostrador", "precio_venta": "25.00", "fecha": "2026-06-11T16:00:00"},
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["iva_pct"] == "21.00"
    assert data["iva_import"] == "2.60"  # (25-10) * 21/121 = 2.6033... -> 2.60


def test_venta_sense_tipus_iva_configurat_no_calcula_res(db, client):
    """Sense cap TipusIva actiu configurat, la venda es crea igualment (no bloqueja el TPV)."""
    admin = _admin_token(client, db)
    release = _seed_release(db)
    item = _seed_item(db, release, precio="25.00", coste="12.00", condicion=CondicionItem.nou)

    resp = client.post(
        "/admin/ventas-externas",
        json={"item_id": str(item.id), "canal": "mostrador", "precio_venta": "25.00", "fecha": "2026-06-11T16:00:00"},
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    assert resp.json()["iva_pct"] is None


# ---------------------------------------------------------------------------
# Despeses amb tipus d'IVA
# ---------------------------------------------------------------------------

def test_despesa_amb_tipus_iva_deriva_percentatge(db, client):
    admin = _admin_token(client, db)
    general, _ = _seed_tipus_iva(db, nou_pct="10.00")

    resp = client.post(
        "/admin/despeses",
        json={
            "data_factura": "2026-06-01",
            "proveidor_nom": "Subministrador SL",
            "categoria": "subministraments",
            "concepte": "Llum juny",
            "base_imposable": "100.00",
            "tipus_iva_id": general.id,
            "iva_pct": "21.00",  # s'ignora: mana el tipus seleccionat
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["iva_pct"] == "10.00"
    assert data["iva_import"] == "10.00"
    assert data["total"] == "110.00"


# ---------------------------------------------------------------------------
# Informe trimestral
# ---------------------------------------------------------------------------

def test_informe_iva_trimestral_inclou_vendes_externes(db, client):
    admin = _admin_token(client, db)
    _seed_tipus_iva(db)
    release = _seed_release(db)
    item = _seed_item(db, release, precio="25.00", coste="12.00", condicion=CondicionItem.nou)
    client.post(
        "/admin/ventas-externas",
        json={"item_id": str(item.id), "canal": "mostrador", "precio_venta": "25.00", "fecha": "2026-06-11T16:00:00"},
        headers=_auth(admin),
    )

    resp = client.get("/admin/iva/2026/2", headers=_auth(admin))
    assert resp.status_code == 200
    data = resp.json()
    linies = [l for l in data["iva_repercutit"] if l["categoria"] == "vendes_mostrador"]
    assert len(linies) == 1
    assert linies[0]["iva_import"] == "4.34"
    assert Decimal(data["total_iva_repercutit"]) >= Decimal("4.34")
