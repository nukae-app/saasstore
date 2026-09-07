"""Tests del tancament d'exercici formal (docs/PLAN_PARIDAD_HOLDED.md B5):
assentament de regularització (ingrés/despesa contra el 129) + tancament
dels 12 períodes de l'any, i el seu revers (reobrir_exercici)."""

import contextlib
import io
import re
from decimal import Decimal

from sqlalchemy import select

from app.models import User


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


def _crear_ingres_manual(client, token, *, data="2026-03-01", import_="1000.00"):
    resp = client.post(
        "/admin/assentaments/manual",
        json={
            "date": data, "description": "Venda de prova",
            "apunts": [
                {"compte_code": "430", "debit": import_, "credit": "0"},
                {"compte_code": "700", "debit": "0", "credit": import_},
            ],
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    return resp.json()


def _crear_despesa(client, token, *, base="200.00", pct="21.00", categoria="subministraments"):
    resp = client.post(
        "/admin/despeses",
        json={
            "invoice_date": "2026-06-05", "supplier_name": "Proveïdor test", "category": categoria,
            "concept": "Test", "taxable_base": base, "vat_pct": pct,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    return resp.json()


def test_tancar_exercici_regularitza_ingressos_i_despeses_contra_129(client, db):
    token = _admin_token(client, db)
    _crear_ingres_manual(client, token, import_="1000.00")
    _crear_despesa(client, token, base="200.00")

    resp = client.post("/admin/periodes/2026/tancar-exercici", headers=_auth(token))
    assert resp.status_code == 201
    body = resp.json()
    assert body["source_type"] == "tancament_exercici"

    per_compte = {a["compte_code"]: a for a in body["apunts"]}
    assert per_compte["700"]["debit"] == "1000.00"
    assert per_compte["628"]["credit"] == "200.00"
    assert per_compte["129"]["credit"] == "800.00"

    balanc = client.get("/admin/balanc-situacio/2026/12", headers=_auth(token)).json()
    assert balanc["exercici_tancat"] is True
    codis_pn = {l["compte_code"]: l["saldo"] for l in balanc["patrimoni_net"]}
    assert codis_pn["129"] == "800.00"
    assert "129*" not in codis_pn

    periodes = {p["month"]: p["closed"] for p in client.get("/admin/periodes", headers=_auth(token)).json()
                if p["year"] == 2026}
    assert all(periodes.get(m) for m in range(1, 13))


def test_tancar_exercici_amb_perdua_carrega_129(client, db):
    token = _admin_token(client, db)
    _crear_ingres_manual(client, token, import_="100.00")
    _crear_despesa(client, token, base="300.00")

    resp = client.post("/admin/periodes/2026/tancar-exercici", headers=_auth(token))
    assert resp.status_code == 201
    per_compte = {a["compte_code"]: a for a in resp.json()["apunts"]}
    assert per_compte["129"]["debit"] == "200.00"


def test_tancar_exercici_ja_tancat_dona_409(client, db):
    token = _admin_token(client, db)
    _crear_ingres_manual(client, token)
    assert client.post("/admin/periodes/2026/tancar-exercici", headers=_auth(token)).status_code == 201
    resp = client.post("/admin/periodes/2026/tancar-exercici", headers=_auth(token))
    assert resp.status_code == 409


def test_tancar_exercici_sense_moviments_dona_422(client, db):
    token = _admin_token(client, db)
    resp = client.post("/admin/periodes/2026/tancar-exercici", headers=_auth(token))
    assert resp.status_code == 422


def test_reobrir_exercici_esborra_assentament_i_reobre_periodes(client, db):
    token = _admin_token(client, db)
    _crear_ingres_manual(client, token)
    assert client.post("/admin/periodes/2026/tancar-exercici", headers=_auth(token)).status_code == 201

    resp = client.post("/admin/periodes/2026/reobrir-exercici", headers=_auth(token))
    assert resp.status_code == 204

    balanc = client.get("/admin/balanc-situacio/2026/12", headers=_auth(token)).json()
    assert balanc["exercici_tancat"] is False
    periodes = {p["month"]: p["closed"] for p in client.get("/admin/periodes", headers=_auth(token)).json()
                if p["year"] == 2026}
    assert not any(periodes.get(m) for m in range(1, 13))

    # Es pot tornar a tancar sense el 409 de "ja tancat"
    resp2 = client.post("/admin/periodes/2026/tancar-exercici", headers=_auth(token))
    assert resp2.status_code == 201


def test_reobrir_exercici_no_tancat_dona_404(client, db):
    token = _admin_token(client, db)
    resp = client.post("/admin/periodes/2026/reobrir-exercici", headers=_auth(token))
    assert resp.status_code == 404
