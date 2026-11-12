"""Cua de revisió per donar d'alta Despeses a partir d'un PDF de factura de
proveïdor (extracció amb Claude, veure services/despesa_extraction.py).
L'extracció mai es contabilitza sola: `confirmar` sempre passa pel mateix
`DespesaIn` que l'alta manual, amb revisió humana pel mig."""

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
from ...services.storage import get_storage
from .despeses import _build_despesa, _despesa_out

router = APIRouter(prefix="/admin", tags=["comptabilitat"], dependencies=[Depends(require_admin)])

# Las facturas son privadas: se guardan bajo `despeses/` (prefijo `private/` en S3, sin
# lectura pública) y el admin las abre con una URL firmada de corta duración
# (GET /despeses/imports/{id}/file-url). Ver services/storage.py.
FILE_URL_TTL_SECONDS = 300

# Factura en PDF o foto (mòbil, capture de càmera) — Claude llegeix totes dues
# nativament, veure services/despesa_extraction.py. Sense HEIC: l'API de
# Claude no l'accepta i els navegadors mòbils ja converteixen a JPEG en pujar.
ALLOWED_CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


@router.post("/despeses/imports", status_code=201, response_model=DespesaImportOut)
async def crear_despesa_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    content_type = (file.content_type or "").lower()
    ext = ALLOWED_CONTENT_TYPES.get(content_type)
    if ext is None:
        raise HTTPException(422, "Només s'accepten PDF o fotos (JPEG, PNG, WebP, HEIC)")

    content = await file.read()

    filename = f"{uuid.uuid4()}{ext}"
    get_storage().save(f"despeses/{filename}", content, content_type=content_type)
    file_url = f"/uploads/despeses/{filename}"

    imp = DespesaImport(
        file_url=file_url,
        original_filename=file.filename or filename,
        status=DespesaImportStatus.pendent,
    )
    db.add(imp)
    db.flush()

    extracted_data, error_message = await extract_despesa_data(content, content_type, db, settings)
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

    if imp.file_url.startswith("/uploads/despeses/"):
        get_storage().delete(imp.file_url.removeprefix("/uploads/"))

    imp.status = DespesaImportStatus.descartat
    db.commit()


@router.get("/despeses/imports/{import_id}/file-url")
def url_fitxer_despesa_import(import_id: uuid.UUID, db: Session = Depends(get_db)):
    """URL temporal (5 min) per obrir la factura original. El fitxer és privat:
    ja no es serveix públicament a /uploads/despeses/."""
    imp = db.get(DespesaImport, import_id)
    if imp is None or not imp.file_url.startswith("/uploads/despeses/"):
        raise HTTPException(404, "Importació no trobada")
    url = get_storage().private_url(
        imp.file_url.removeprefix("/uploads/"), expires=FILE_URL_TTL_SECONDS, filename=imp.original_filename,
    )
    return {"url": url, "expires_in": FILE_URL_TTL_SECONDS}
