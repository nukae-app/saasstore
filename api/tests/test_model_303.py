"""Tests del informe de caselles del Model 303 (Fase 5) — en particular que
el desglossament corrent (28/29) vs béns d'inversió (30/31) surt correcte
gràcies al fet que un FixedAsset mai passa per Despesa."""

from decimal import Decimal

from sqlalchemy import select

from app.models import CondicionItem, Item, Release, TipusIva, User


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


def test_model_303_desglossa_corrent_vs_inversio(client, db):
    token = _admin_token(client, db)
    db.add(TipusIva(name="General", percentage=Decimal("21.00"), default_new=True, active=True))
    db.commit()

    # Venda: 100.00 total, 21% -> base 82.64, cuota 17.36 (repercutit).
    release = Release(artista="A", title="T", formato="LP")
    db.add(release)
    db.commit()
    item = Item(release_id=release.id, price=Decimal("100.00"), acquisition_cost=Decimal("40.00"), condition=CondicionItem.nou, quantity=1)
    db.add(item)
    db.commit()
    resp = client.post(
        "/admin/ventas-externas",
        json={
            "item_id": str(item.id), "channel": "mostrador", "payment_method": "efectivo",
            "sale_price": "100.00", "quantity": 1, "date": "2026-04-15T10:00:00",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    cuota_repercutida = Decimal(str(resp.json()["vat_amount"]))

    # Despesa corrent: base 50.00, cuota 10.50.
    resp_despesa = client.post(
        "/admin/despeses",
        json={
            "invoice_date": "2026-04-20", "supplier_name": "Proveïdor", "category": "subministraments",
            "concept": "Llum", "taxable_base": "50.00", "vat_pct": "21.00",
        },
        headers=_auth(token),
    )
    assert resp_despesa.status_code == 201

    # Actiu (béns d'inversió): cost 1000.00, IVA 210.00.
    resp_actiu = client.post(
        "/admin/actius",
        json={
            "name": "Ordinador", "category": "equips_informatics", "acquisition_date": "2026-04-25",
            "acquisition_cost": "1000.00", "vat_amount": "210.00", "annual_depreciation_pct": "25.00",
        },
        headers=_auth(token),
    )
    assert resp_actiu.status_code == 201

    resp = client.get("/admin/aeat/303/2026/2", headers=_auth(token))  # T2 = abr-may-jun
    assert resp.status_code == 200
    body = resp.json()

    assert Decimal(body["repercutit_general"]["cuota"]) == cuota_repercutida
    assert Decimal(body["casella_27_cuota_meritada"]) == cuota_repercutida

    assert body["casella_28_base_corrent"] == "50.00"
    assert body["casella_29_cuota_corrent"] == "10.50"
    assert body["casella_30_base_inversio"] == "1000.00"
    assert body["casella_31_cuota_inversio"] == "210.00"

    total_a_deduir = Decimal("10.50") + Decimal("210.00")
    assert Decimal(body["casella_45_total_a_deduir"]) == total_a_deduir
    assert Decimal(body["casella_46_resultat_regim_general"]) == cuota_repercutida - total_a_deduir
    assert Decimal(body["casella_64_resultat_liquidacio"]) == cuota_repercutida - total_a_deduir
    assert body["nota_rebu"] is False


def test_model_303_trimestre_invalid_dona_422(client, db):
    token = _admin_token(client, db)
    resp = client.get("/admin/aeat/303/2026/5", headers=_auth(token))
    assert resp.status_code == 422
