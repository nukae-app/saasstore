"""Tests dels llibres comptables (Fase 3): Diari, Major, Balanç de Situació
i Compte de Resultats, derivats de JournalEntry/JournalLine."""

import uuid
from decimal import Decimal

from sqlalchemy import select

from app.models import User


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


def _crear_despesa(client, token, *, base="100.00", pct="21.00", categoria="subministraments"):
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


def test_llibre_diari_llista_assentaments_del_mes_ordenats(client, db):
    token = _admin_token(client, db)
    _crear_despesa(client, token, base="100.00")
    _crear_despesa(client, token, base="50.00")

    resp = client.get("/admin/llibre-diari/2026/6", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["year"] == 2026 and body["mes"] == 6
    assert len(body["assentaments"]) == 2
    assert [a["entry_number"] for a in body["assentaments"]] == [1, 2]
    for assentament in body["assentaments"]:
        total_debit = sum(Decimal(l["debit"]) for l in assentament["apunts"])
        total_credit = sum(Decimal(l["credit"]) for l in assentament["apunts"])
        assert total_debit == total_credit


def test_list_comptes_comptables(client, db):
    token = _admin_token(client, db)
    resp = client.get("/admin/comptes-comptables", headers=_auth(token))
    assert resp.status_code == 200
    codis = {a["code"] for a in resp.json()}
    assert "570" in codis and "700" in codis


def test_llibre_diari_export_csv(client, db):
    token = _admin_token(client, db)
    _crear_despesa(client, token, base="100.00")

    resp = client.get("/admin/llibre-diari/2026/export", params={"mes_desde": 6, "mes_fins": 6}, headers=_auth(token))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    text = resp.content.decode("utf-8-sig")
    rows = text.strip().splitlines()
    assert rows[0] == "Data;Assentament;Compte;Nom del compte;Concepte;Debe;Haver"
    assert len(rows) == 4  # capçalera + 3 apunts (628, 472, 400)
    assert any(";628;" in r for r in rows)
    assert any("121,00" in r for r in rows)  # decimal amb coma


def test_llibre_major_calcula_saldo_acumulat(client, db):
    token = _admin_token(client, db)
    _crear_despesa(client, token, base="100.00")  # Debe 628 100 + 472 21 / Haber 400 121

    resp = client.get("/admin/llibre-major/2026", params={"compte": "400"}, headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["compte_code"] == "400"
    assert len(body["linies"]) == 1
    # 400 és passiu: normal és haver, saldo positiu quan creix el deute.
    assert body["linies"][0]["credit"] == "121.00"
    assert body["saldo_final"] == "121.00"


def test_llibre_major_compte_inexistent_404(client, db):
    token = _admin_token(client, db)
    resp = client.get("/admin/llibre-major/2026", params={"compte": "999999"}, headers=_auth(token))
    assert resp.status_code == 404


def test_balanc_situacio_quadra(client, db):
    token = _admin_token(client, db)
    _crear_despesa(client, token, base="100.00")

    resp = client.get("/admin/balanc-situacio/2026/6", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["quadrat"] is True
    assert body["total_actiu"] == body["total_passiu_patrimoni_net"]
    codis_actiu = {l["compte_code"] for l in body["actiu"]}
    assert "472" in codis_actiu  # IVA suportat, actiu
    codis_passiu = {l["compte_code"] for l in body["passiu"]}
    assert "400" in codis_passiu


def test_balanc_situacio_es_acumulat_no_nomes_del_mes(client, db):
    """Un compte patrimonial (banc, proveïdors...) no es reinicia cada mes
    — el saldo de maig ha de seguir comptant al balanç de juny."""
    token = _admin_token(client, db)
    resp_maig = client.post(
        "/admin/despeses",
        json={
            "invoice_date": "2026-05-05", "supplier_name": "Maig SL", "category": "lloguer",
            "concept": "Lloguer maig", "taxable_base": "200.00", "vat_pct": "21.00",
        },
        headers=_auth(token),
    )
    assert resp_maig.status_code == 201

    balanc_maig = client.get("/admin/balanc-situacio/2026/5", headers=_auth(token)).json()
    balanc_juny = client.get("/admin/balanc-situacio/2026/6", headers=_auth(token)).json()
    saldo_400_maig = next(l["saldo"] for l in balanc_maig["passiu"] if l["compte_code"] == "400")
    saldo_400_juny = next(l["saldo"] for l in balanc_juny["passiu"] if l["compte_code"] == "400")
    assert saldo_400_maig == saldo_400_juny == "242.00"


def test_compte_resultats_net_iva_i_nomes_del_periode(client, db):
    """A diferència del balanç, el compte de resultats és NOMÉS del mes
    (un ingrés/despesa de maig no compta al de juny) i net d'IVA."""
    token = _admin_token(client, db)
    client.post(
        "/admin/despeses",
        json={
            "invoice_date": "2026-05-05", "supplier_name": "Maig SL", "category": "lloguer",
            "concept": "Lloguer maig", "taxable_base": "200.00", "vat_pct": "21.00",
        },
        headers=_auth(token),
    )
    _crear_despesa(client, token, base="100.00", categoria="subministraments")

    pyg_juny = client.get("/admin/compte-resultats/2026/6", headers=_auth(token)).json()
    assert pyg_juny["total_despeses"] == "100.00"  # NO els 200 de maig
    assert pyg_juny["resultat"] == "-100.00"
    codis = {l["compte_code"] for l in pyg_juny["despeses"]}
    assert codis == {"628"}


def test_resultat_legacy_inclou_iva_pyg_nou_no(client, db):
    """Documenta la diferència coneguda: `/admin/resultat` suma preus AMB
    IVA (útil per quadrar caixa); `/admin/compte-resultats` és net d'IVA
    (el que esperaria una gestoria). No s'han de reconciliar a un mateix
    número — són preguntes diferents."""
    from app.models import Release, Item, CondicionItem, TipusIva

    token = _admin_token(client, db)
    db.add(TipusIva(name="General", percentage=Decimal("21.00"), default_new=True, active=True))
    db.commit()
    release = Release(artista="A", title="T", formato="LP")
    db.add(release)
    db.commit()
    item = Item(release_id=release.id, price=Decimal("20.00"), acquisition_cost=Decimal("8.00"), condition=CondicionItem.nou, quantity=5)
    db.add(item)
    db.commit()

    resp = client.post(
        "/admin/ventas-externas",
        json={
            "item_id": str(item.id), "channel": "mostrador", "payment_method": "efectivo",
            "sale_price": "20.00", "quantity": 1, "date": "2026-06-15T10:00:00",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    vat_amount = Decimal(str(resp.json()["vat_amount"]))

    legacy = client.get("/admin/resultat/2026/6", headers=_auth(token)).json()
    nou = client.get("/admin/compte-resultats/2026/6", headers=_auth(token)).json()
    # El legacy compta els 20.00 sencers com a "vendes_mostrador" (preu amb IVA).
    assert Decimal(legacy["vendes_mostrador"]) == Decimal("20.00")
    # El nou compte 700 és net dels 477 (IVA repercutit) que hi va lligat.
    total_ingressos_nou = Decimal(nou["total_ingressos"])
    assert total_ingressos_nou == Decimal("20.00") - vat_amount
    assert total_ingressos_nou < Decimal("20.00")

