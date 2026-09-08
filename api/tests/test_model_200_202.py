"""Tests del Model 200 (Impost de Societats, estimació de suport — NO un
càlcul fiscal complet, ver docstring d'aeat.py) i del Model 202 (pagament
fraccionat, modalitat estàndard art. 40.2 LIS)."""

import contextlib
import io
import re
from decimal import Decimal

from sqlalchemy import select

from app.models import CondicionItem, ConfiguracioBotiga, Item, Release, User


def _admin_token(client, db) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert client.post("/auth/magic-link", json={"email": "admin@example.com"}).status_code == 202
    token = re.search(r"token=([\w\-]+)", buf.getvalue()).group(1)
    resp = client.post(f"/auth/magic-link/verify?token={token}")
    user = db.scalar(select(User).where(User.email == "admin@example.com"))
    user.role = "admin"
    db.commit()
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _seed_venda(client, token, db, *, preu="100.00", data="2026-03-10T10:00:00"):
    release = Release(artista="A", title="T", formato="LP")
    db.add(release)
    db.commit()
    item = Item(release_id=release.id, price=Decimal(preu), acquisition_cost=Decimal("0.00"), condition=CondicionItem.nou, quantity=1)
    db.add(item)
    db.commit()
    resp = client.post(
        "/admin/ventas-externas",
        json={
            "item_id": str(item.id), "channel": "mostrador", "payment_method": "efectivo",
            "sale_price": preu, "quantity": 1, "date": data,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    return resp.json()


def _seed_despesa(client, token, *, base, data="2026-03-15"):
    resp = client.post(
        "/admin/despeses",
        json={
            "invoice_date": data, "supplier_name": "Proveïdor test", "category": "subministraments",
            "concept": "Test", "taxable_base": base, "vat_pct": "0.00",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Model 200
# ---------------------------------------------------------------------------

def test_model_200_requereix_tipus_pct(client, db):
    token = _admin_token(client, db)
    resp = client.get("/admin/aeat/200/2026", headers=_auth(token))
    assert resp.status_code == 422


def test_model_200_calcula_quota_sobre_resultat_comptable(client, db):
    token = _admin_token(client, db)
    _seed_venda(client, token, db, preu="1000.00")
    _seed_despesa(client, token, base="400.00")

    resp = client.get("/admin/aeat/200/2026?tipus_pct=25.00", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["resultat_comptable"] == "600.00"
    assert body["ajustos_extracomptables"] == "0.00"
    assert body["base_imposable"] == "600.00"
    assert body["quota_integra"] == "150.00"  # 600 * 25%
    assert body["pagaments_fraccionats_satisfets"] == "0.00"
    assert body["resultat"] == "150.00"


def test_model_200_tipus_reduit_i_pagaments_fraccionats_resten(client, db):
    token = _admin_token(client, db)
    _seed_venda(client, token, db, preu="1000.00")
    _seed_despesa(client, token, base="400.00")

    resp = client.get(
        "/admin/aeat/200/2026?tipus_pct=15.00&pagaments_fraccionats_satisfets=50.00", headers=_auth(token),
    )
    body = resp.json()
    assert body["quota_integra"] == "90.00"  # 600 * 15%
    assert body["resultat"] == "40.00"       # 90 - 50


def test_model_200_resultat_negatiu_es_a_retornar(client, db):
    token = _admin_token(client, db)
    _seed_venda(client, token, db, preu="1000.00")
    _seed_despesa(client, token, base="400.00")

    resp = client.get(
        "/admin/aeat/200/2026?tipus_pct=25.00&pagaments_fraccionats_satisfets=200.00", headers=_auth(token),
    )
    body = resp.json()
    assert body["quota_integra"] == "150.00"
    assert body["resultat"] == "-50.00"  # a retornar, no es topa a 0


def test_model_200_base_negativa_dona_quota_zero(client, db):
    token = _admin_token(client, db)
    _seed_despesa(client, token, base="500.00")  # sense cap ingrés

    resp = client.get("/admin/aeat/200/2026?tipus_pct=25.00", headers=_auth(token))
    body = resp.json()
    assert body["base_imposable"] == "-500.00"
    assert body["quota_integra"] == "0.00"
    assert body["resultat"] == "0.00"


def test_model_200_avisa_si_tenant_es_autonom(client, db):
    token = _admin_token(client, db)
    config = db.scalar(select(ConfiguracioBotiga))
    config.legal_form = "autonom"
    db.commit()

    resp = client.get("/admin/aeat/200/2026?tipus_pct=25.00", headers=_auth(token))
    body = resp.json()
    assert body["forma_juridica_nota"] is not None
    assert "Autònom" in body["forma_juridica_nota"]


# ---------------------------------------------------------------------------
# Model 202
# ---------------------------------------------------------------------------

def test_model_202_calcula_18pct_de_la_cuota_anterior(client, db):
    token = _admin_token(client, db)
    resp = client.get(
        "/admin/aeat/202/2026/1?cuota_integra_exercici_anterior=1000.00", headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["periode"] == 1
    assert body["periode_nom"] == "Abril"
    assert body["import_pagament"] == "180.00"  # 1000 * 18%


def test_model_202_els_3_periodes_donen_el_mateix_import(client, db):
    token = _admin_token(client, db)
    imports = [
        client.get(
            f"/admin/aeat/202/2026/{p}?cuota_integra_exercici_anterior=2000.00", headers=_auth(token),
        ).json()["import_pagament"]
        for p in (1, 2, 3)
    ]
    assert imports == ["360.00", "360.00", "360.00"]


def test_model_202_cuota_anterior_zero_o_negativa_dona_zero(client, db):
    token = _admin_token(client, db)
    resp = client.get(
        "/admin/aeat/202/2026/2?cuota_integra_exercici_anterior=-100.00", headers=_auth(token),
    )
    assert resp.json()["import_pagament"] == "0.00"


def test_model_202_periode_invalid_dona_422(client, db):
    token = _admin_token(client, db)
    resp = client.get(
        "/admin/aeat/202/2026/4?cuota_integra_exercici_anterior=1000.00", headers=_auth(token),
    )
    assert resp.status_code == 422


def test_model_202_requereix_cuota_anterior(client, db):
    token = _admin_token(client, db)
    resp = client.get("/admin/aeat/202/2026/1", headers=_auth(token))
    assert resp.status_code == 422
