"""Tests de regles de conciliació i suggeriments automàtics (Bloc B3, veure
docs/PLAN_PARIDAD_HOLDED.md)."""

import contextlib
import io
import re
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models import (
    CategoriaDespesa, CompteBancari, Despesa, EstatConciliacio, EstatPagamentDespesa, MovimentBancari, Proveedor,
    User,
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


def _seed_proveedor(db, name="DistroX") -> Proveedor:
    p = Proveedor(name=name)
    db.add(p)
    db.commit()
    return p


def _seed_compte(db) -> CompteBancari:
    c = CompteBancari(name="Compte principal")
    db.add(c)
    db.commit()
    return c


def _seed_despesa(db, proveidor, total: str, invoice_date: date, due_date: date | None = None) -> Despesa:
    d = Despesa(
        invoice_date=invoice_date, due_date=due_date, proveidor_id=proveidor.id, supplier_name=proveidor.name,
        category=CategoriaDespesa.subministraments, concept="Factura", taxable_base=Decimal(total),
        vat_pct=Decimal("0.00"), vat_amount=Decimal("0.00"), total=Decimal(total),
        payment_status=EstatPagamentDespesa.pendent,
    )
    db.add(d)
    db.commit()
    return d


def _seed_moviment(db, compte, import_: str, concept: str, operation_date: date) -> MovimentBancari:
    m = MovimentBancari(compte_id=compte.id, operation_date=operation_date, concept=concept, movement_amount=Decimal(import_))
    db.add(m)
    db.commit()
    return m


def test_crear_llistar_editar_eliminar_regla(client, db):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)

    resp = client.post("/admin/banc/regles", json={"pattern": "ENDESA", "proveidor_id": str(prov.id)}, headers=_auth(admin))
    assert resp.status_code == 201
    regla = resp.json()
    assert regla["pattern"] == "ENDESA"
    assert regla["proveidor_nom"] == "DistroX"
    assert regla["active"] is True

    resp = client.get("/admin/banc/regles", headers=_auth(admin))
    assert len(resp.json()) == 1

    resp = client.patch(f"/admin/banc/regles/{regla['id']}", json={"pattern": "ENDESA", "proveidor_id": str(prov.id), "active": False}, headers=_auth(admin))
    assert resp.json()["active"] is False

    resp = client.delete(f"/admin/banc/regles/{regla['id']}", headers=_auth(admin))
    assert resp.status_code == 204
    assert client.get("/admin/banc/regles", headers=_auth(admin)).json() == []


def test_suggeriments_ordena_per_import_exacte_i_proximitat_de_data(client, db):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    compte = _seed_compte(db)

    # Import exacte, lluny en data.
    d_lluny = _seed_despesa(db, prov, "100.00", date(2026, 1, 1))
    # Import exacte, a prop en data -> ha de sortir primer.
    d_prop = _seed_despesa(db, prov, "100.00", date(2026, 6, 8))
    # Import diferent -> mai ha de sortir.
    _seed_despesa(db, prov, "50.00", date(2026, 6, 10))

    mov = _seed_moviment(db, compte, "-100.00", "Transferència", date(2026, 6, 10))

    resp = client.get(f"/admin/banc/moviments/{mov.id}/suggeriments", headers=_auth(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert [s["despesa_id"] for s in body] == [str(d_prop.id), str(d_lluny.id)]


def test_suggeriments_buit_per_a_ingressos(client, db):
    admin = _admin_token(client, db)
    compte = _seed_compte(db)
    mov = _seed_moviment(db, compte, "100.00", "Ingrés", date.today())

    resp = client.get(f"/admin/banc/moviments/{mov.id}/suggeriments", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json() == []


def test_aplicar_regles_concilia_automaticament_amb_candidat_unic(client, db):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    compte = _seed_compte(db)
    despesa = _seed_despesa(db, prov, "60.50", date(2026, 6, 1))
    mov = _seed_moviment(db, compte, "-60.50", "REBUT ENDESA JUNY", date(2026, 6, 15))

    client.post("/admin/banc/regles", json={"pattern": "ENDESA", "proveidor_id": str(prov.id)}, headers=_auth(admin))

    resp = client.post(f"/admin/banc/{compte.id}/aplicar-regles", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json()["conciliats"] == 1

    db.refresh(mov)
    db.refresh(despesa)
    assert mov.status == EstatConciliacio.conciliat
    assert mov.despesa_id == despesa.id
    assert despesa.payment_status == EstatPagamentDespesa.pagat


def test_aplicar_regles_no_fa_res_amb_ambiguitat(client, db):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    compte = _seed_compte(db)
    # Dues despeses pendents amb el mateix import i proveïdor: ambigu, no s'ha de triar cap.
    _seed_despesa(db, prov, "30.00", date(2026, 6, 1))
    _seed_despesa(db, prov, "30.00", date(2026, 6, 2))
    mov = _seed_moviment(db, compte, "-30.00", "REBUT ENDESA", date(2026, 6, 15))

    client.post("/admin/banc/regles", json={"pattern": "ENDESA", "proveidor_id": str(prov.id)}, headers=_auth(admin))

    resp = client.post(f"/admin/banc/{compte.id}/aplicar-regles", headers=_auth(admin))
    assert resp.json()["conciliats"] == 0

    db.refresh(mov)
    assert mov.status == EstatConciliacio.pendent


def test_aplicar_regles_ignora_moviments_sense_match(client, db):
    admin = _admin_token(client, db)
    prov = _seed_proveedor(db)
    compte = _seed_compte(db)
    _seed_despesa(db, prov, "20.00", date(2026, 6, 1))
    mov = _seed_moviment(db, compte, "-20.00", "Concepte qualsevol", date(2026, 6, 15))

    client.post("/admin/banc/regles", json={"pattern": "ENDESA", "proveidor_id": str(prov.id)}, headers=_auth(admin))

    resp = client.post(f"/admin/banc/{compte.id}/aplicar-regles", headers=_auth(admin))
    assert resp.json()["conciliats"] == 0
    db.refresh(mov)
    assert mov.status == EstatConciliacio.pendent
