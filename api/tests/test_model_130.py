"""Tests del Model 130 (pagament fraccionat d'IRPF, Autònoms): acumulat des
de l'1 de gener (no per trimestre com el 303), casella 07 resta el resultat
dels trimestres anteriors, reducció opcional del 5% (topada a 2.000€/any) i
la nota quan el tenant és una SL (a qui aquest model no li aplica)."""

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


def _seed_venda(client, token, db, *, preu="100.00", cost="0.00", data="2026-02-10T10:00:00"):
    release = Release(artista="A", title="T", formato="LP")
    db.add(release)
    db.commit()
    item = Item(release_id=release.id, price=Decimal(preu), acquisition_cost=Decimal(cost), condition=CondicionItem.nou, quantity=1)
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


def _seed_despesa(client, token, *, base, data="2026-02-15"):
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


def test_model_130_primer_trimestre_sense_pagaments_anteriors(client, db):
    token = _admin_token(client, db)
    # Venda sense cost d'adquisició registrat (no genera 610/300) -> ingrés net = base venuda.
    _seed_venda(client, token, db, preu="100.00", cost="0.00", data="2026-02-10T10:00:00")
    _seed_despesa(client, token, base="40.00", data="2026-02-15")

    resp = client.get("/admin/aeat/130/2026/1", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["casella_01_ingressos_acumulats"] == "100.00"
    assert body["casella_02_despeses_acumulades"] == "40.00"
    assert body["casella_03_rendiment_net"] == "60.00"
    assert body["reduccio_5pct_aplicada"] is False
    assert body["casella_05_import"] == "12.00"  # 60 * 20%
    assert body["casella_07_pagaments_anteriors"] == "0.00"
    assert body["resultat"] == "12.00"


def test_model_130_segon_trimestre_acumula_i_resta_pagament_anterior(client, db):
    token = _admin_token(client, db)
    _seed_venda(client, token, db, preu="100.00", data="2026-02-10T10:00:00")   # T1
    _seed_despesa(client, token, base="40.00", data="2026-02-15")               # T1
    _seed_venda(client, token, db, preu="50.00", data="2026-05-10T10:00:00")    # T2
    _seed_despesa(client, token, base="20.00", data="2026-05-15")               # T2

    resp = client.get("/admin/aeat/130/2026/2", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    # Acumulat gen-jun: ingressos 150, despeses 60, rendiment 90.
    assert body["casella_01_ingressos_acumulats"] == "150.00"
    assert body["casella_02_despeses_acumulades"] == "60.00"
    assert body["casella_03_rendiment_net"] == "90.00"
    assert body["casella_05_import"] == "18.00"      # 90 * 20%
    assert body["casella_07_pagaments_anteriors"] == "12.00"  # resultat del T1
    assert body["resultat"] == "6.00"                 # 18 - 12


def test_model_130_reduccio_5pct_opcional(client, db):
    token = _admin_token(client, db)
    _seed_venda(client, token, db, preu="1000.00", data="2026-02-10T10:00:00")

    sense = client.get("/admin/aeat/130/2026/1", headers=_auth(token)).json()
    assert sense["reduccio_5pct_aplicada"] is False
    assert sense["reduccio_5pct_import"] == "0.00"
    assert sense["casella_05_import"] == "200.00"  # 1000 * 20%

    amb = client.get("/admin/aeat/130/2026/1?aplicar_reduccio_5pct=true", headers=_auth(token)).json()
    assert amb["reduccio_5pct_aplicada"] is True
    assert amb["reduccio_5pct_import"] == "50.00"  # 5% de 1000
    assert amb["rendiment_net_reduit"] == "950.00"
    assert amb["casella_05_import"] == "190.00"    # 950 * 20%


def test_model_130_reduccio_5pct_topada_a_2000(client, db):
    token = _admin_token(client, db)
    _seed_venda(client, token, db, preu="60000.00", data="2026-02-10T10:00:00")

    resp = client.get("/admin/aeat/130/2026/1?aplicar_reduccio_5pct=true", headers=_auth(token))
    body = resp.json()
    # 5% de 60000 = 3000, però topa a 2000.
    assert body["reduccio_5pct_import"] == "2000.00"


def test_model_130_rendiment_negatiu_dona_resultat_zero(client, db):
    token = _admin_token(client, db)
    _seed_despesa(client, token, base="500.00", data="2026-02-15")  # sense cap ingrés

    resp = client.get("/admin/aeat/130/2026/1", headers=_auth(token))
    body = resp.json()
    assert body["casella_03_rendiment_net"] == "-500.00"
    assert body["casella_05_import"] == "0.00"
    assert body["resultat"] == "0.00"


def test_model_130_trimestre_invalid_dona_422(client, db):
    token = _admin_token(client, db)
    assert client.get("/admin/aeat/130/2026/0", headers=_auth(token)).status_code == 422


def test_model_130_avisa_si_tenant_es_sl(client, db):
    token = _admin_token(client, db)
    # PATCH /admin/configuracio bloqueja canviar legal_form un cop ja hi ha
    # pla de comptes sembrat (el fixture ja el sembra) — es fixa directament
    # a la BD, mateix criteri que altres tests que toquen estat intern (p.
    # ex. user.role = "admin" a _admin_token).
    config = db.scalar(select(ConfiguracioBotiga))
    config.legal_form = "sl"
    db.commit()

    resp = client.get("/admin/aeat/130/2026/1", headers=_auth(token))
    body = resp.json()
    assert body["forma_juridica_nota"] is not None
    assert "SL" in body["forma_juridica_nota"]
