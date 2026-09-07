"""Tests del flux de caixa projectat (docs/PLAN_PARIDAD_HOLDED.md B3):
combina estacionalitat de vendes (mitjana del mateix mes en anys anteriors)
amb despeses ja facturades pendents de pagar."""

import contextlib
import io
import re
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from app.models import CanalVenta, MetodoPago, User, VentaExterna


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


def _mes_dins_n(avui: date, n: int) -> tuple[int, int]:
    """Mateix càlcul que fa l'endpoint per al mes i-èssim a partir d'avui."""
    total_mesos = avui.month - 1 + n
    any_ = avui.year + total_mesos // 12
    mes = total_mesos % 12 + 1
    return any_, mes


def test_flux_caixa_projectat_estructura_basica_sense_dades(client, db):
    token = _admin_token(client, db)
    resp = client.get("/admin/flux-caixa-projectat?mesos=3", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["saldo_actual"] == "0.00"
    assert len(body["linies"]) == 3
    for linia in body["linies"]:
        assert linia["ingressos_estimats"] == "0.00"
        assert linia["despeses_pendents"] == "0.00"
        assert linia["saldo_projectat"] == "0.00"


def test_flux_caixa_projectat_valida_rang_mesos(client, db):
    token = _admin_token(client, db)
    assert client.get("/admin/flux-caixa-projectat?mesos=0", headers=_auth(token)).status_code == 422
    assert client.get("/admin/flux-caixa-projectat?mesos=25", headers=_auth(token)).status_code == 422


def test_flux_caixa_projectat_estima_ingressos_per_estacionalitat(client, db):
    token = _admin_token(client, db)
    avui = date.today()
    any_projeccio, mes_projeccio = _mes_dins_n(avui, 1)

    # Única venda històrica ara fa un any, el mateix mes que es projecta.
    db.add(VentaExterna(
        description="Vinil test", channel=CanalVenta.mostrador, payment_method=MetodoPago.efectivo,
        sale_price=Decimal("100.00"), vat_pct=Decimal("21.00"),
        date=datetime(any_projeccio - 1, mes_projeccio, 15, 12, 0, tzinfo=timezone.utc),
    ))
    db.commit()

    resp = client.get("/admin/flux-caixa-projectat?mesos=1&anys_historic=1", headers=_auth(token))
    assert resp.status_code == 200
    linia = resp.json()["linies"][0]
    assert linia["year"] == any_projeccio and linia["mes"] == mes_projeccio
    assert linia["ingressos_estimats"] == "100.00"
    assert linia["saldo_projectat"] == "100.00"


def test_flux_caixa_projectat_inclou_despeses_pendents_del_mes(client, db):
    token = _admin_token(client, db)
    avui = date.today()
    any_projeccio, mes_projeccio = _mes_dins_n(avui, 1)
    due_date = date(any_projeccio, mes_projeccio, 20)

    resp = client.post(
        "/admin/despeses",
        json={
            "invoice_date": avui.isoformat(), "due_date": due_date.isoformat(),
            "supplier_name": "Lloguer local", "category": "lloguer", "concept": "Lloguer mensual",
            "taxable_base": "50.00", "vat_pct": "0.00", "payment_status": "pendent",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201

    resp = client.get("/admin/flux-caixa-projectat?mesos=1", headers=_auth(token))
    linia = resp.json()["linies"][0]
    assert linia["despeses_pendents"] == "50.00"
    assert linia["saldo_projectat"] == "-50.00"


def test_flux_caixa_projectat_no_compta_despesa_ja_pagada(client, db):
    token = _admin_token(client, db)
    avui = date.today()
    any_projeccio, mes_projeccio = _mes_dins_n(avui, 1)
    due_date = date(any_projeccio, mes_projeccio, 20)

    resp = client.post(
        "/admin/despeses",
        json={
            "invoice_date": avui.isoformat(), "due_date": due_date.isoformat(),
            "supplier_name": "Proveïdor pagat", "category": "altres", "concept": "Ja pagada",
            "taxable_base": "30.00", "vat_pct": "0.00", "payment_status": "pagat",
            "payment_date": avui.isoformat(), "payment_method": "transferencia",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201

    resp = client.get("/admin/flux-caixa-projectat?mesos=1", headers=_auth(token))
    linia = resp.json()["linies"][0]
    assert linia["despeses_pendents"] == "0.00"
