"""Tests de la cua d'importació de Despeses des de PDF (OCR amb Claude).

L'extracció real (`services.despesa_extraction.extract_despesa_data`) es
mockeja sempre — els tests mai criden l'API d'Anthropic de veritat."""

import contextlib
import io
import os
import re
import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.models import Despesa, DespesaImport, DespesaImportStatus, Proveedor, User
from app.routers.comptabilitat import despeses_imports as despeses_imports_router
from app.services.despesa_extraction import _match_proveidor


@pytest.fixture(autouse=True)
def _patch_uploads_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(despeses_imports_router, "UPLOADS_ROOT", str(tmp_path))
    monkeypatch.setattr(despeses_imports_router, "UPLOADS_DIR", os.path.join(str(tmp_path), "despeses"))


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


def _mock_extraction(monkeypatch, data=None, error=None):
    async def fake(pdf_bytes, db, settings):
        return (data, error)
    monkeypatch.setattr(despeses_imports_router, "extract_despesa_data", AsyncMock(side_effect=fake))


def _upload(client, admin, filename="factura.pdf"):
    return client.post(
        "/admin/despeses/imports",
        files={"file": (filename, b"%PDF-1.4 fake content", "application/pdf")},
        headers=_auth(admin),
    )


def test_upload_pdf_ok_queda_processat(client, db, monkeypatch):
    admin = _admin_token(client, db)
    extracted = {
        "supplier_name": "DistroX", "supplier_nif": None, "invoice_number": "F-1", "invoice_date": "2026-06-01",
        "taxable_base": 100.0, "vat_pct": 21.0, "total": 121.0, "category": "compres_material",
        "concept": "Discos", "confidence": "alta", "proveidor_id": None,
    }
    _mock_extraction(monkeypatch, data=extracted)

    resp = _upload(client, admin)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "processat"
    assert body["extracted_data"]["supplier_name"] == "DistroX"
    assert body["file_url"].startswith("/uploads/despeses/")

    imp = db.get(DespesaImport, uuid.UUID(body["id"]))
    assert imp.status == DespesaImportStatus.processat


def test_upload_pdf_error_queda_error(client, db, monkeypatch):
    admin = _admin_token(client, db)
    _mock_extraction(monkeypatch, error="La resposta de Claude no és un JSON vàlid")

    resp = _upload(client, admin)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "error"
    assert body["error_message"]
    assert body["extracted_data"] is None


def test_upload_rebutja_no_pdf(client, db, monkeypatch):
    admin = _admin_token(client, db)
    resp = client.post(
        "/admin/despeses/imports",
        files={"file": ("ticket.txt", b"hola", "text/plain")},
        headers=_auth(admin),
    )
    assert resp.status_code == 422


def test_confirmar_crea_despesa_i_enllaça_pdf(client, db, monkeypatch):
    admin = _admin_token(client, db)
    _mock_extraction(monkeypatch, data={
        "supplier_name": "DistroX", "supplier_nif": None, "invoice_number": "F-1", "invoice_date": "2026-06-01",
        "taxable_base": 100.0, "vat_pct": 21.0, "total": 121.0, "category": "compres_material",
        "concept": "Discos", "confidence": "alta", "proveidor_id": None,
    })
    imp_id = _upload(client, admin).json()["id"]

    payload = {
        "invoice_date": "2026-06-01", "supplier_name": "DistroX", "category": "compres_material",
        "concept": "Discos", "taxable_base": "100.00", "vat_pct": "21.00",
    }
    resp = client.post(f"/admin/despeses/imports/{imp_id}/confirmar", json=payload, headers=_auth(admin))
    assert resp.status_code == 201
    despesa = resp.json()
    assert despesa["source_document_url"].startswith("/uploads/despeses/")

    imp = db.get(DespesaImport, uuid.UUID(imp_id))
    assert imp.status == DespesaImportStatus.confirmat
    assert str(imp.despesa_id) == despesa["id"]
    d = db.get(Despesa, uuid.UUID(despesa["id"]))
    assert d.source_document_url == imp.file_url


def test_no_es_pot_confirmar_dos_cops(client, db, monkeypatch):
    admin = _admin_token(client, db)
    _mock_extraction(monkeypatch, data={
        "supplier_name": "DistroX", "supplier_nif": None, "invoice_number": None, "invoice_date": "2026-06-01",
        "taxable_base": 50.0, "vat_pct": 21.0, "total": 60.5, "category": "altres",
        "concept": "X", "confidence": "alta", "proveidor_id": None,
    })
    imp_id = _upload(client, admin).json()["id"]
    payload = {
        "invoice_date": "2026-06-01", "supplier_name": "DistroX", "category": "altres",
        "concept": "X", "taxable_base": "50.00", "vat_pct": "21.00",
    }
    assert client.post(f"/admin/despeses/imports/{imp_id}/confirmar", json=payload, headers=_auth(admin)).status_code == 201
    resp = client.post(f"/admin/despeses/imports/{imp_id}/confirmar", json=payload, headers=_auth(admin))
    assert resp.status_code == 409


def test_descartar_no_crea_despesa(client, db, monkeypatch):
    admin = _admin_token(client, db)
    _mock_extraction(monkeypatch, error="il·legible")
    imp_id = _upload(client, admin).json()["id"]

    resp = client.delete(f"/admin/despeses/imports/{imp_id}", headers=_auth(admin))
    assert resp.status_code == 204
    imp = db.get(DespesaImport, uuid.UUID(imp_id))
    assert imp.status == DespesaImportStatus.descartat
    assert imp.despesa_id is None


def test_match_proveidor_per_nif(db):
    prov = Proveedor(name="DistroX SL", nif="B12345678")
    db.add(prov)
    db.commit()

    assert _match_proveidor(db, "B12345678", "Nom Diferent") == str(prov.id)


def test_match_proveidor_per_nom_ambigu_no_fa_match(db):
    db.add_all([Proveedor(name="Distro"), Proveedor(name="Distro Barcelona")])
    db.commit()

    assert _match_proveidor(db, None, "Distro") is None


def test_list_filtra_per_status(client, db, monkeypatch):
    admin = _admin_token(client, db)
    _mock_extraction(monkeypatch, error="il·legible")
    _upload(client, admin)

    resp = client.get("/admin/despeses/imports?status=error", headers=_auth(admin))
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["status"] == "error"

    resp = client.get("/admin/despeses/imports?status=processat", headers=_auth(admin))
    assert resp.json() == []
