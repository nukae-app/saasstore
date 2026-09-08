"""Tests de retenció d'IRPF a proveïdors (Model 111 professionals, Model 115
lloguer) i del Model 390 (resum anual d'IVA). Cobreix: la partida doble es
manté quadrada quan hi ha retenció (400 net + 4751 retingut), el pagament a
l'alta usa el net, la conciliació bancària hi encaixa pel net, i els
informes de caselles agreguen correctament."""

import contextlib
import io
import re
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models import (
    CategoriaDespesa, CompteBancari, Despesa, EstatPagamentDespesa, JournalEntry, JournalLine, JournalSourceType,
    MovimentBancari, Proveedor, RetencioTipus, User,
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


def _seed_proveedor(db, name="Gestoria Poblenou SLP", nif="B12345678") -> Proveedor:
    p = Proveedor(name=name, nif=nif, type="professional")
    db.add(p)
    db.commit()
    return p


# ---------------------------------------------------------------------------
# Partida doble amb retenció
# ---------------------------------------------------------------------------

def test_despesa_amb_retencio_reparteix_400_i_4751(client, db):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)

    resp = client.post(
        "/admin/despeses",
        json={
            "invoice_date": "2026-05-10", "proveidor_id": str(prov.id), "supplier_name": prov.name,
            "category": "serveis_professionals", "concept": "Gestoria maig",
            "taxable_base": "200.00", "vat_pct": "21.00",
            "retencio_tipus": "professional", "retencio_pct": "15.00",
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["retencio_import"] == "30.00"          # 200 * 15%
    assert data["total"] == "242.00"                    # 200 + 21% IVA, la retenció NO es descompta del total
    assert data["net_a_pagar"] == "212.00"               # 242 - 30

    entry = db.scalar(
        select(JournalEntry).where(
            JournalEntry.source_type == JournalSourceType.despesa_alta,
            JournalEntry.source_id == uuid.UUID(data["id"]),
        )
    )
    lines = db.scalars(select(JournalLine).where(JournalLine.entry_id == entry.id)).all()
    assert sum(l.debit for l in lines) == sum(l.credit for l in lines) == Decimal("242.00")
    codis = {l.account.code: (l.debit, l.credit) for l in lines}
    assert codis["623"] == (Decimal("200.00"), Decimal("0.00"))   # serveis professionals independents
    assert codis["472"] == (Decimal("42.00"), Decimal("0.00"))
    assert codis["400"] == (Decimal("0.00"), Decimal("212.00"))   # net, no el total
    assert codis["4751"] == (Decimal("0.00"), Decimal("30.00"))


def test_despesa_sense_retencio_no_toca_4751(client, db):
    admin = _admin_token(client, db)
    resp = client.post(
        "/admin/despeses",
        json={
            "invoice_date": "2026-05-10", "supplier_name": "Endesa", "category": "subministraments",
            "concept": "Llum", "taxable_base": "100.00", "vat_pct": "21.00",
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["retencio_import"] is None
    assert data["net_a_pagar"] == data["total"]
    entry = db.scalar(
        select(JournalEntry).where(
            JournalEntry.source_type == JournalSourceType.despesa_alta,
            JournalEntry.source_id == uuid.UUID(data["id"]),
        )
    )
    codis = {l.account.code for l in db.scalars(select(JournalLine).where(JournalLine.entry_id == entry.id))}
    assert "4751" not in codis


def test_despesa_amb_retencio_pagada_a_l_alta_paga_el_net(client, db):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    resp = client.post(
        "/admin/despeses",
        json={
            "invoice_date": "2026-05-10", "proveidor_id": str(prov.id), "supplier_name": prov.name,
            "category": "serveis_professionals", "concept": "Gestoria maig",
            "taxable_base": "200.00", "vat_pct": "21.00",
            "retencio_tipus": "professional", "retencio_pct": "15.00",
            "payment_status": "pagat", "payment_method": "transferencia", "payment_date": "2026-05-10",
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 201
    despesa_id = uuid.UUID(resp.json()["id"])

    pagament = db.scalar(
        select(JournalEntry).where(
            JournalEntry.source_type == JournalSourceType.despesa_pagament, JournalEntry.source_id == despesa_id,
        )
    )
    assert pagament is not None
    lines = {l.account.code: (l.debit, l.credit) for l in db.scalars(select(JournalLine).where(JournalLine.entry_id == pagament.id))}
    assert lines["400"] == (Decimal("212.00"), Decimal("0.00"))
    assert lines["572"] == (Decimal("0.00"), Decimal("212.00"))


def test_actualitzar_despesa_recalcula_retencio(client, db):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    resp = client.post(
        "/admin/despeses",
        json={
            "invoice_date": "2026-05-10", "proveidor_id": str(prov.id), "supplier_name": prov.name,
            "category": "serveis_professionals", "concept": "Gestoria",
            "taxable_base": "100.00", "vat_pct": "21.00",
            "retencio_tipus": "professional", "retencio_pct": "15.00",
        },
        headers=_auth(admin),
    )
    despesa_id = resp.json()["id"]

    resp = client.patch(f"/admin/despeses/{despesa_id}", json={"taxable_base": "300.00"}, headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json()["retencio_import"] == "45.00"

    resp = client.patch(f"/admin/despeses/{despesa_id}", json={"retencio_tipus": None}, headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json()["retencio_import"] is None
    assert resp.json()["retencio_pct"] is None


# ---------------------------------------------------------------------------
# Conciliació bancària pel net
# ---------------------------------------------------------------------------

def test_suggeriments_bancaris_encaixen_pel_net_amb_retencio(client, db):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    compte = CompteBancari(name="Compte principal")
    db.add(compte)
    db.commit()

    resp = client.post(
        "/admin/despeses",
        json={
            "invoice_date": "2026-05-10", "proveidor_id": str(prov.id), "supplier_name": prov.name,
            "category": "serveis_professionals", "concept": "Gestoria",
            "taxable_base": "200.00", "vat_pct": "21.00",
            "retencio_tipus": "professional", "retencio_pct": "15.00",
        },
        headers=_auth(admin),
    )
    despesa_id = resp.json()["id"]
    assert resp.json()["net_a_pagar"] == "212.00"

    mov = MovimentBancari(compte_id=compte.id, operation_date=date(2026, 5, 15), concept="Transferència gestoria", movement_amount=Decimal("-212.00"))
    db.add(mov)
    db.commit()

    resp = client.get(f"/admin/banc/moviments/{mov.id}/suggeriments", headers=_auth(admin))
    assert resp.status_code == 200
    assert [s["despesa_id"] for s in resp.json()] == [despesa_id]


# ---------------------------------------------------------------------------
# Models 111 / 115
# ---------------------------------------------------------------------------

def test_model_111_agrega_retencions_de_professionals(client, db):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db, name="Gestoria X", nif="B11111111")
    client.post(
        "/admin/despeses",
        json={
            "invoice_date": "2026-05-10", "proveidor_id": str(prov.id), "supplier_name": prov.name,
            "category": "serveis_professionals", "concept": "Gestoria maig",
            "taxable_base": "200.00", "vat_pct": "21.00",
            "retencio_tipus": "professional", "retencio_pct": "15.00",
        },
        headers=_auth(admin),
    )
    client.post(
        "/admin/despeses",
        json={
            "invoice_date": "2026-06-05", "proveidor_id": str(prov.id), "supplier_name": prov.name,
            "category": "serveis_professionals", "concept": "Gestoria juny",
            "taxable_base": "100.00", "vat_pct": "21.00",
            "retencio_tipus": "professional", "retencio_pct": "15.00",
        },
        headers=_auth(admin),
    )
    # Despesa sense retenció, no ha de comptar.
    client.post(
        "/admin/despeses",
        json={
            "invoice_date": "2026-05-12", "supplier_name": "Endesa", "category": "subministraments",
            "concept": "Llum", "taxable_base": "50.00", "vat_pct": "21.00",
        },
        headers=_auth(admin),
    )

    resp = client.get("/admin/aeat/111/2026/2", headers=_auth(admin))  # T2 = abr-may-jun
    assert resp.status_code == 200
    body = resp.json()
    assert body["num_perceptors"] == 1
    assert body["base_total"] == "300.00"
    assert body["retencio_total"] == "45.00"
    assert body["desglossat"][0]["nif"] == "B11111111"


def test_model_115_agrega_retencions_de_lloguer(client, db):
    admin = _admin_token(client, db)
    arrendador = Proveedor(name="Propietari Local SL", nif="B22222222", type="altres")
    db.add(arrendador)
    db.commit()

    client.post(
        "/admin/despeses",
        json={
            "invoice_date": "2026-05-01", "proveidor_id": str(arrendador.id), "supplier_name": arrendador.name,
            "category": "lloguer", "concept": "Lloguer maig",
            "taxable_base": "500.00", "vat_pct": "21.00",
            "retencio_tipus": "lloguer", "retencio_pct": "19.00",
        },
        headers=_auth(admin),
    )

    resp = client.get("/admin/aeat/115/2026/2", headers=_auth(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert body["num_perceptors"] == 1
    assert body["base_total"] == "500.00"
    assert body["retencio_total"] == "95.00"

    # No ha d'aparèixer al 111 (tipus diferent).
    resp111 = client.get("/admin/aeat/111/2026/2", headers=_auth(admin))
    assert resp111.json()["num_perceptors"] == 0


def test_model_trimestre_invalid_dona_422(client, db):
    admin = _admin_token(client, db)
    assert client.get("/admin/aeat/111/2026/0", headers=_auth(admin)).status_code == 422
    assert client.get("/admin/aeat/115/2026/5", headers=_auth(admin)).status_code == 422


# ---------------------------------------------------------------------------
# Model 390 (resum anual d'IVA)
# ---------------------------------------------------------------------------

def test_model_390_agrega_els_4_trimestres_del_303(client, db):
    admin = _admin_token(client, db)
    for mes, base in [(2, "10.00"), (5, "20.00"), (8, "30.00"), (11, "40.00")]:
        client.post(
            "/admin/despeses",
            json={
                "invoice_date": f"2026-{mes:02d}-10", "supplier_name": "Proveïdor", "category": "subministraments",
                "concept": "Despesa", "taxable_base": base, "vat_pct": "21.00",
            },
            headers=_auth(admin),
        )

    resp = client.get("/admin/aeat/390/2026", headers=_auth(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["trimestres"]) == 4

    resp_t1 = client.get("/admin/aeat/303/2026/1", headers=_auth(admin)).json()  # gen-feb-mar
    resp_t4 = client.get("/admin/aeat/303/2026/4", headers=_auth(admin)).json()  # oct-nov-des
    assert Decimal(body["trimestres"][0]["resultat"]) == Decimal(resp_t1["casella_64_resultat_liquidacio"])
    assert Decimal(body["trimestres"][3]["resultat"]) == Decimal(resp_t4["casella_64_resultat_liquidacio"])

    total_esperat = sum(
        Decimal(client.get(f"/admin/aeat/303/2026/{t}", headers=_auth(admin)).json()["casella_64_resultat_liquidacio"])
        for t in range(1, 5)
    )
    assert Decimal(body["resultat_anual"]) == total_esperat
