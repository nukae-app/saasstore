"""Tests d'actius fixos i amortitzacions (Fase 4): alta amb assentament,
generació d'amortitzacions idempotent i topada al cost pendent al darrer mes."""

from decimal import Decimal

from sqlalchemy import select

from app.models import JournalEntry, JournalLine, JournalSourceType, User


def _admin_token(client, db) -> str:
    import contextlib
    import io
    import re

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


def _crear_actiu(client, token, **overrides):
    payload = {
        "name": "Ordinador TPV", "category": "equips_informatics", "acquisition_date": "2026-01-10",
        "acquisition_cost": "1200.00", "vat_amount": "252.00", "annual_depreciation_pct": "25.00",
    }
    payload.update(overrides)
    resp = client.post("/admin/actius", json=payload, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_alta_actiu_genera_assentament_balancejat(client, db):
    token = _admin_token(client, db)
    actiu = _crear_actiu(client, token)

    entry = db.scalar(
        select(JournalEntry).where(
            JournalEntry.source_type == JournalSourceType.actiu_alta,
            JournalEntry.source_id == __import__("uuid").UUID(actiu["id"]),
        )
    )
    assert entry is not None
    lines = {l.account.code: (l.debit, l.credit) for l in db.scalars(select(JournalLine).where(JournalLine.entry_id == entry.id))}
    assert lines["217"] == (Decimal("1200.00"), Decimal("0.00"))
    assert lines["472"] == (Decimal("252.00"), Decimal("0.00"))
    assert lines["400"] == (Decimal("0.00"), Decimal("1452.00"))
    assert actiu["book_value"] == "1200.00"
    assert actiu["accumulated_depreciation"] == "0.00"


def test_generar_amortitzacions_quota_mensual_correcta(client, db):
    token = _admin_token(client, db)
    _crear_actiu(client, token, acquisition_cost="1200.00", annual_depreciation_pct="24.00")  # 24 = 2%/mes = 24.00/mes

    resp = client.post("/admin/amortitzacions/2026/2/generar", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["entrades_generades"]) == 1
    assert body["entrades_generades"][0]["amount"] == "24.00"

    actiu = client.get("/admin/actius", headers=_auth(token)).json()[0]
    assert actiu["accumulated_depreciation"] == "24.00"
    assert actiu["book_value"] == "1176.00"


def test_generar_amortitzacions_es_idempotent(client, db):
    token = _admin_token(client, db)
    _crear_actiu(client, token, acquisition_cost="1200.00", annual_depreciation_pct="24.00")

    r1 = client.post("/admin/amortitzacions/2026/3/generar", headers=_auth(token)).json()
    r2 = client.post("/admin/amortitzacions/2026/3/generar", headers=_auth(token)).json()
    assert len(r1["entrades_generades"]) == 1
    assert len(r2["entrades_generades"]) == 0
    assert len(r2["actius_saltats"]) == 1

    actiu = client.get("/admin/actius", headers=_auth(token)).json()[0]
    assert actiu["accumulated_depreciation"] == "24.00"  # no s'ha duplicat


def test_generar_amortitzacions_topa_al_cost_pendent_al_darrer_mes(client, db):
    token = _admin_token(client, db)
    # Cost 100.00, quota mensual teòrica de 30.00 (360%/12) — el 4t mes només
    # pot amortitzar els 10.00 que queden, no els 30.00 sencers.
    _crear_actiu(client, token, acquisition_cost="100.00", annual_depreciation_pct="360.00")

    for mes in (1, 2, 3, 4):
        client.post(f"/admin/amortitzacions/2026/{mes}/generar", headers=_auth(token))

    actiu = client.get("/admin/actius", headers=_auth(token)).json()[0]
    assert actiu["accumulated_depreciation"] == "100.00"
    assert actiu["book_value"] == "0.00"

    # Un 5è mes ja no genera res: totalment amortitzat.
    r5 = client.post("/admin/amortitzacions/2026/5/generar", headers=_auth(token)).json()
    assert len(r5["entrades_generades"]) == 0
