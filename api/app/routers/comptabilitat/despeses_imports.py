"""Cua de revisió per donar d'alta Despeses a partir d'un PDF de factura de
proveïdor (extracció amb Claude, veure services/despesa_extraction.py).
L'extracció mai es contabilitza sola: `confirmar` sempre passa pel mateix
`DespesaIn` que l'alta manual, amb revisió humana pel mig."""

import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...config import Settings, get_settings
from ...database import get_db
from ...models import DespesaImport, DespesaImportStatus
from ...schemas import DespesaImportOut, DespesaIn, DespesaOut
from ...services.despesa_extraction import extract_despesa_data
from ...services.security import require_admin
from .despeses import _build_despesa, _despesa_out

router = APIRouter(prefix="/admin", tags=["comptabilitat"], dependencies=[Depends(require_admin)])

UPLOADS_ROOT = "/app/uploads"
UPLOADS_DIR = os.path.join(UPLOADS_ROOT, "despeses")


@router.post("/despeses/imports", status_code=201, response_model=DespesaImportOut)
async def crear_despesa_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if (file.content_type or "") != "application/pdf" and not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(422, "Només s'accepten fitxers PDF")

    content = await file.read()

    os.makedirs(UPLOADS_DIR, exist_ok=True)
    filename = f"{uuid.uuid4()}.pdf"
    with open(os.path.join(UPLOADS_DIR, filename), "wb") as f:
        f.write(content)
    file_url = f"/uploads/despeses/{filename}"

    imp = DespesaImport(
        file_url=file_url,
        original_filename=file.filename or filename,
        status=DespesaImportStatus.pendent,
    )
    db.add(imp)
    db.flush()

    extracted_data, error_message = await extract_despesa_data(content, db, settings)
    if error_message:
        imp.status = DespesaImportStatus.error
        imp.error_message = error_message
    else:
        imp.status = DespesaImportStatus.processat
        imp.extracted_data = extracted_data

    db.commit()
    db.refresh(imp)
    return imp


@router.get("/despeses/imports", response_model=list[DespesaImportOut])
def list_despeses_imports(status: str | None = None, db: Session = Depends(get_db)):
    stmt = select(DespesaImport).order_by(DespesaImport.created_at.desc())
    if status:
        stmt = stmt.where(DespesaImport.status == DespesaImportStatus(status))
    return db.scalars(stmt).all()


@router.get("/despeses/imports/{import_id}", response_model=DespesaImportOut)
def get_despesa_import(import_id: uuid.UUID, db: Session = Depends(get_db)):
    imp = db.get(DespesaImport, import_id)
    if imp is None:
        raise HTTPException(404, "Importació no trobada")
    return imp


@router.post("/despeses/imports/{import_id}/confirmar", status_code=201, response_model=DespesaOut)
def confirmar_despesa_import(import_id: uuid.UUID, payload: DespesaIn, db: Session = Depends(get_db)):
    imp = db.get(DespesaImport, import_id)
    if imp is None:
        raise HTTPException(404, "Importació no trobada")
    if imp.status == DespesaImportStatus.confirmat:
        raise HTTPException(409, "Aquesta importació ja s'ha confirmat")

    despesa = _build_despesa(payload, db)
    despesa.source_document_url = imp.file_url
    db.flush()

    imp.status = DespesaImportStatus.confirmat
    imp.despesa_id = despesa.id

    db.commit()
    db.refresh(despesa)
    return _despesa_out(despesa)


@router.delete("/despeses/imports/{import_id}", status_code=204)
def descartar_despesa_import(import_id: uuid.UUID, db: Session = Depends(get_db)):
    imp = db.get(DespesaImport, import_id)
    if imp is None:
        raise HTTPException(404, "Importació no trobada")
    if imp.status == DespesaImportStatus.confirmat:
        raise HTTPException(409, "No es pot descartar una importació ja confirmada")

    if imp.file_url.startswith("/uploads/"):
        filepath = os.path.join(UPLOADS_ROOT, imp.file_url.removeprefix("/uploads/"))
        if os.path.exists(filepath):
            os.remove(filepath)

    imp.status = DespesaImportStatus.descartat
    db.commit()
