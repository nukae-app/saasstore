"""Tests de remeses de pagament a proveïdors (SEPA pain.001) i la seva
conciliació — ver docs/PLAN_COBRAMENTS_PAGAMENTS.md."""

import contextlib
import io
import re
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models import (
    CategoriaDespesa, CompteBancari, Despesa, EstatPagamentDespesa, JournalEntry, JournalLine, MovimentBancari,
    Proveedor, RemesaPagamentStatus, User,
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


def _seed_proveedor(db, name="DistroX", iban="ES7620770024003102575766") -> Proveedor:
    p = Proveedor(name=name, supplier_iban=iban, payment_method="transferencia")
    db.add(p)
    db.commit()
    return p


def _seed_compte(db, iban="ES9121000418450200051332") -> CompteBancari:
    c = CompteBancari(name="Compte principal", iban=iban)
    db.add(c)
    db.commit()
    return c


def _seed_despesa(db, proveidor, total: str, due_date: date | None = None, retencio: str | None = None) -> Despesa:
    d = Despesa(
        invoice_date=date(2026, 9, 1), due_date=due_date, proveidor_id=proveidor.id, supplier_name=proveidor.name,
        category=CategoriaDespesa.subministraments, concept="Factura", taxable_base=Decimal(total),
        vat_pct=Decimal("0.00"), vat_amount=Decimal("0.00"), total=Decimal(total),
        payment_status=EstatPagamentDespesa.pendent, payment_method="transferencia",
        retencio_import=Decimal(retencio) if retencio else None,
    )
    db.add(d)
    db.commit()
    return d


def test_despeses_elegibles_nomes_transferencia_amb_iban(client, db):
    token = _admin_token(client, db)
    prov_ok = _seed_proveedor(db, "Amb IBAN")
    prov_sense_iban = _seed_proveedor(db, "Sense IBAN", iban=None)
    _seed_despesa(db, prov_ok, "100.00")
    d2 = _seed_despesa(db, prov_sense_iban, "50.00")

    resp = client.get("/admin/remeses-pagament/despeses-elegibles", headers=_auth(token))
    assert resp.status_code == 200
    ids = {row["despesa_id"] for row in resp.json()}
    assert str(d2.id) not in ids
    assert len(resp.json()) == 1


def test_generar_remesa_ok_marca_despeses_en_remesa_i_numera(client, db):
    token = _admin_token(client, db)
    compte = _seed_compte(db)
    prov = _seed_proveedor(db)
    d1 = _seed_despesa(db, prov, "100.00")
    d2 = _seed_despesa(db, prov, "50.00", retencio="5.00")

    resp = client.post(
        "/admin/remeses-pagament",
        json={
            "compte_bancari_id": compte.id, "execution_date": "2026-09-20",
            "despesa_ids": [str(d1.id), str(d2.id)],
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["number"] == 1
    assert body["status"] == "generada"
    # 100.00 + (50.00 - 5.00 retencio) = 145.00 net
    assert Decimal(body["total"]) == Decimal("145.00")
    imports = {l["despesa_id"]: Decimal(l["import"]) for l in body["lines"]}
    assert imports[str(d1.id)] == Decimal("100.00")
    assert imports[str(d2.id)] == Decimal("45.00")

    db.refresh(d1)
    db.refresh(d2)
    assert d1.payment_status == EstatPagamentDespesa.en_remesa
    assert d2.payment_status == EstatPagamentDespesa.en_remesa

    xml_resp = client.get(f"/admin/remeses-pagament/{body['id']}/xml", headers=_auth(token))
    assert xml_resp.status_code == 200
    assert b"pain.001.001.03" in xml_resp.content
    assert b"<NbOfTxs>2</NbOfTxs>" in xml_resp.content


def test_generar_remesa_rebutja_proveidor_sense_iban(client, db):
    token = _admin_token(client, db)
    compte = _seed_compte(db)
    prov = _seed_proveedor(db, iban=None)
    d = _seed_despesa(db, prov, "20.00")

    resp = client.post(
        "/admin/remeses-pagament",
        json={"compte_bancari_id": compte.id, "execution_date": "2026-09-20", "despesa_ids": [str(d.id)]},
        headers=_auth(token),
    )
    assert resp.status_code == 422
    db.refresh(d)
    assert d.payment_status == EstatPagamentDespesa.pendent  # no s'ha tocat res


def test_generar_remesa_rebutja_despesa_ja_pagada(client, db):
    token = _admin_token(client, db)
    compte = _seed_compte(db)
    prov = _seed_proveedor(db)
    d = _seed_despesa(db, prov, "20.00")
    d.payment_status = EstatPagamentDespesa.pagat
    db.commit()

    resp = client.post(
        "/admin/remeses-pagament",
        json={"compte_bancari_id": compte.id, "execution_date": "2026-09-20", "despesa_ids": [str(d.id)]},
        headers=_auth(token),
    )
    assert resp.status_code == 422


def test_generar_remesa_sense_iban_al_compte_emissor_falla(client, db):
    token = _admin_token(client, db)
    compte = _seed_compte(db, iban=None)
    prov = _seed_proveedor(db)
    d = _seed_despesa(db, prov, "20.00")

    resp = client.post(
        "/admin/remeses-pagament",
        json={"compte_bancari_id": compte.id, "execution_date": "2026-09-20", "despesa_ids": [str(d.id)]},
        headers=_auth(token),
    )
    assert resp.status_code == 422


def test_anullar_remesa_allibera_despeses_en_remesa(client, db):
    token = _admin_token(client, db)
    compte = _seed_compte(db)
    prov = _seed_proveedor(db)
    d = _seed_despesa(db, prov, "20.00")

    remesa_id = client.post(
        "/admin/remeses-pagament",
        json={"compte_bancari_id": compte.id, "execution_date": "2026-09-20", "despesa_ids": [str(d.id)]},
        headers=_auth(token),
    ).json()["id"]

    resp = client.post(f"/admin/remeses-pagament/{remesa_id}/anullar", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "anullada"
    db.refresh(d)
    assert d.payment_status == EstatPagamentDespesa.pendent

    # no es pot anul·lar dues vegades
    assert client.post(f"/admin/remeses-pagament/{remesa_id}/anullar", headers=_auth(token)).status_code == 409


def test_conciliar_moviment_contra_remesa_sencera_tanca_totes_les_despeses(client, db):
    token = _admin_token(client, db)
    compte = _seed_compte(db)
    prov1 = _seed_proveedor(db, "Prov1")
    prov2 = _seed_proveedor(db, "Prov2", iban="ES1000492352082414205416")
    d1 = _seed_despesa(db, prov1, "100.00")
    d2 = _seed_despesa(db, prov2, "50.00")

    remesa_id = client.post(
        "/admin/remeses-pagament",
        json={
            "compte_bancari_id": compte.id, "execution_date": "2026-09-20",
            "despesa_ids": [str(d1.id), str(d2.id)],
        },
        headers=_auth(token),
    ).json()["id"]

    mov = MovimentBancari(
        compte_id=compte.id, operation_date=date(2026, 9, 20), concept="REMESA PROVEIDORS",
        movement_amount=Decimal("-150.00"),
    )
    db.add(mov)
    db.commit()

    resp = client.patch(
        f"/admin/banc/moviments/{mov.id}/conciliar",
        json={"status": "conciliat", "remesa_pagament_id": remesa_id},
        headers=_auth(token),
    )
    assert resp.status_code == 200

    db.refresh(d1)
    db.refresh(d2)
    assert d1.payment_status == EstatPagamentDespesa.pagat
    assert d2.payment_status == EstatPagamentDespesa.pagat
    assert d1.payment_date == date(2026, 9, 20)

    # cada despesa ha generat el seu propi assentament de pagament (400/572)
    for d in (d1, d2):
        entry = db.scalar(select(JournalEntry).where(JournalEntry.source_id == d.id))
        assert entry is not None
        lines = {l.account.code: (l.debit, l.credit) for l in db.scalars(select(JournalLine).where(JournalLine.entry_id == entry.id))}
        assert lines["400"] == (d.total, Decimal("0.00"))
        assert lines["572"] == (Decimal("0.00"), d.total)


def test_conciliar_moviment_import_no_coincident_amb_remesa_falla(client, db):
    token = _admin_token(client, db)
    compte = _seed_compte(db)
    prov = _seed_proveedor(db)
    d = _seed_despesa(db, prov, "100.00")

    remesa_id = client.post(
        "/admin/remeses-pagament",
        json={"compte_bancari_id": compte.id, "execution_date": "2026-09-20", "despesa_ids": [str(d.id)]},
        headers=_auth(token),
    ).json()["id"]

    mov = MovimentBancari(
        compte_id=compte.id, operation_date=date(2026, 9, 20), concept="REMESA",
        movement_amount=Decimal("-99.00"),
    )
    db.add(mov)
    db.commit()

    resp = client.patch(
        f"/admin/banc/moviments/{mov.id}/conciliar",
        json={"status": "conciliat", "remesa_pagament_id": remesa_id},
        headers=_auth(token),
    )
    assert resp.status_code == 422
    db.refresh(d)
    assert d.payment_status == EstatPagamentDespesa.en_remesa  # no s'ha tocat
