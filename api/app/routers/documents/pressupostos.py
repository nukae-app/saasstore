import io
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ...database import get_db
from ...models import Pressupost, PressupostLinia, PressupostStatus
from ...schemas import PressupostIn, PressupostOut
from ...services.documents_numbering import next_document_number
from ...services.documents_pdf import generate_pressupost_pdf
from ...services.emailer import send_email
from ...services.security import require_admin

router = APIRouter(prefix="/admin", tags=["documents"], dependencies=[Depends(require_admin)])


def _pressupost_out(pressupost: Pressupost) -> dict:
    return {
        "id": pressupost.id,
        "fiscal_year": pressupost.fiscal_year,
        "number": pressupost.number,
        "status": pressupost.status,
        "client_name": pressupost.client_name,
        "client_email": pressupost.client_email,
        "user_id": pressupost.user_id,
        "issue_date": pressupost.issue_date,
        "valid_until": pressupost.valid_until,
        "notes": pressupost.notes,
        "converted_order_id": pressupost.converted_order_id,
        "created_at": pressupost.created_at,
        "lines": [
            {
                "id": linia.id,
                "description": linia.description,
                "quantity": linia.quantity,
                "unit_price": linia.unit_price,
                "vat_pct": linia.vat_pct,
            }
            for linia in pressupost.lines
        ],
    }


def _get_pressupost_or_404(db: Session, pressupost_id: uuid.UUID) -> Pressupost:
    pressupost = db.scalar(
        select(Pressupost)
        .options(selectinload(Pressupost.lines))
        .where(Pressupost.id == pressupost_id)
    )
    if pressupost is None:
        raise HTTPException(404, "Pressupost no trobat")
    return pressupost


@router.post("/pressupostos", status_code=201, response_model=PressupostOut)
def crear_pressupost(payload: PressupostIn, db: Session = Depends(get_db)):
    fiscal_year = date.today().year
    number = next_document_number(db, "pressupost", fiscal_year)
    pressupost = Pressupost(
        fiscal_year=fiscal_year, number=number,
        client_name=payload.client_name, client_email=payload.client_email, user_id=payload.user_id,
        valid_until=payload.valid_until, notes=payload.notes,
        lines=[
            PressupostLinia(
                position=i, description=linia.description,
                quantity=linia.quantity, unit_price=linia.unit_price, vat_pct=linia.vat_pct,
            )
            for i, linia in enumerate(payload.lines)
        ],
    )
    db.add(pressupost)
    db.commit()
    return _pressupost_out(_get_pressupost_or_404(db, pressupost.id))


@router.get("/pressupostos", response_model=list[PressupostOut])
def llistar_pressupostos(status: str | None = None, db: Session = Depends(get_db)):
    query = select(Pressupost).options(selectinload(Pressupost.lines)).order_by(Pressupost.created_at.desc())
    if status:
        query = query.where(Pressupost.status == status)
    return [_pressupost_out(p) for p in db.scalars(query)]


@router.get("/pressupostos/{pressupost_id}", response_model=PressupostOut)
def obtenir_pressupost(pressupost_id: uuid.UUID, db: Session = Depends(get_db)):
    return _pressupost_out(_get_pressupost_or_404(db, pressupost_id))


@router.patch("/pressupostos/{pressupost_id}", response_model=PressupostOut)
def editar_pressupost(pressupost_id: uuid.UUID, payload: PressupostIn, db: Session = Depends(get_db)):
    pressupost = _get_pressupost_or_404(db, pressupost_id)
    if pressupost.status != PressupostStatus.esborrany:
        raise HTTPException(409, "Només es pot editar un pressupost en esborrany")
    pressupost.client_name = payload.client_name
    pressupost.client_email = payload.client_email
    pressupost.user_id = payload.user_id
    pressupost.valid_until = payload.valid_until
    pressupost.notes = payload.notes
    pressupost.lines = [
        PressupostLinia(
            position=i, description=linia.description,
            quantity=linia.quantity, unit_price=linia.unit_price, vat_pct=linia.vat_pct,
        )
        for i, linia in enumerate(payload.lines)
    ]
    db.commit()
    return _pressupost_out(_get_pressupost_or_404(db, pressupost.id))


@router.delete("/pressupostos/{pressupost_id}", status_code=204)
def eliminar_pressupost(pressupost_id: uuid.UUID, db: Session = Depends(get_db)):
    pressupost = _get_pressupost_or_404(db, pressupost_id)
    if pressupost.status != PressupostStatus.esborrany:
        raise HTTPException(409, "Només es pot eliminar un pressupost en esborrany")
    db.delete(pressupost)
    db.commit()


@router.get("/pressupostos/{pressupost_id}/pdf")
def pressupost_pdf(pressupost_id: uuid.UUID, db: Session = Depends(get_db)):
    pressupost = _get_pressupost_or_404(db, pressupost_id)
    pdf_bytes = generate_pressupost_pdf(pressupost, db)
    filename = f"pressupost_{pressupost.fiscal_year}_{pressupost.number:04d}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/pressupostos/{pressupost_id}/enviar", response_model=PressupostOut)
def enviar_pressupost(pressupost_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    pressupost = _get_pressupost_or_404(db, pressupost_id)
    if pressupost.status not in (PressupostStatus.esborrany, PressupostStatus.enviat):
        raise HTTPException(409, "Aquest pressupost no es pot enviar en el seu estat actual")
    if not pressupost.client_email:
        raise HTTPException(422, "El client no té email")

    pdf_bytes = generate_pressupost_pdf(pressupost, db)
    filename = f"pressupost_{pressupost.fiscal_year}_{pressupost.number:04d}.pdf"
    send_email(
        to=pressupost.client_email,
        subject=f"Pressupost {pressupost.fiscal_year}/{pressupost.number:04d}",
        body="Adjuntem el pressupost sol·licitat. Gràcies!",
        tenant=request.state.tenant,
        db=db,
        attachment=(filename, pdf_bytes, "application/pdf"),
    )
    pressupost.status = PressupostStatus.enviat
    db.commit()
    return _pressupost_out(_get_pressupost_or_404(db, pressupost.id))


@router.post("/pressupostos/{pressupost_id}/acceptar", response_model=PressupostOut)
def acceptar_pressupost(pressupost_id: uuid.UUID, db: Session = Depends(get_db)):
    pressupost = _get_pressupost_or_404(db, pressupost_id)
    if pressupost.status not in (PressupostStatus.esborrany, PressupostStatus.enviat):
        raise HTTPException(409, "Aquest pressupost no es pot acceptar en el seu estat actual")
    pressupost.status = PressupostStatus.acceptat
    db.commit()
    return _pressupost_out(_get_pressupost_or_404(db, pressupost.id))


@router.post("/pressupostos/{pressupost_id}/rebutjar", response_model=PressupostOut)
def rebutjar_pressupost(pressupost_id: uuid.UUID, db: Session = Depends(get_db)):
    pressupost = _get_pressupost_or_404(db, pressupost_id)
    if pressupost.status not in (PressupostStatus.esborrany, PressupostStatus.enviat):
        raise HTTPException(409, "Aquest pressupost no es pot rebutjar en el seu estat actual")
    pressupost.status = PressupostStatus.rebutjat
    db.commit()
    return _pressupost_out(_get_pressupost_or_404(db, pressupost.id))
