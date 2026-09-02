import io
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ...database import get_db
from ...models import Albara, Order, OrderItem
from ...schemas import AlbaraIn, AlbaraOut
from ...services.documents_numbering import next_document_number
from ...services.documents_pdf import generate_albara_pdf
from ...services.security import require_admin

router = APIRouter(prefix="/admin", tags=["documents"], dependencies=[Depends(require_admin)])


def _albara_out(albara: Albara) -> dict:
    return {
        "id": albara.id,
        "fiscal_year": albara.fiscal_year,
        "number": albara.number,
        "order_id": albara.order_id,
        "delivery_date": albara.delivery_date,
        "notes": albara.notes,
        "created_at": albara.created_at,
    }


def _get_albara_or_404(db: Session, albara_id: uuid.UUID) -> Albara:
    albara = db.get(Albara, albara_id)
    if albara is None:
        raise HTTPException(404, "Albarà no trobat")
    return albara


@router.post("/albarans", status_code=201, response_model=AlbaraOut)
def crear_albara(payload: AlbaraIn, db: Session = Depends(get_db)):
    order = db.get(Order, payload.order_id)
    if order is None:
        raise HTTPException(404, "Comanda no trobada")

    delivery_date = payload.delivery_date or date.today()
    fiscal_year = delivery_date.year
    number = next_document_number(db, "albara", fiscal_year)
    albara = Albara(
        fiscal_year=fiscal_year, number=number,
        order_id=payload.order_id, delivery_date=delivery_date, notes=payload.notes,
    )
    db.add(albara)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Aquesta comanda ja té un albarà")
    return _albara_out(albara)


@router.get("/albarans", response_model=list[AlbaraOut])
def llistar_albarans(order_id: uuid.UUID | None = None, db: Session = Depends(get_db)):
    query = select(Albara).order_by(Albara.created_at.desc())
    if order_id:
        query = query.where(Albara.order_id == order_id)
    return [_albara_out(a) for a in db.scalars(query)]


@router.get("/albarans/{albara_id}", response_model=AlbaraOut)
def obtenir_albara(albara_id: uuid.UUID, db: Session = Depends(get_db)):
    return _albara_out(_get_albara_or_404(db, albara_id))


@router.get("/albarans/{albara_id}/pdf")
def albara_pdf(albara_id: uuid.UUID, db: Session = Depends(get_db)):
    albara = db.scalar(
        select(Albara)
        .options(selectinload(Albara.order).selectinload(Order.items).selectinload(OrderItem.release))
        .where(Albara.id == albara_id)
    )
    if albara is None:
        raise HTTPException(404, "Albarà no trobat")
    pdf_bytes = generate_albara_pdf(albara, db)
    filename = f"albara_{albara.fiscal_year}_{albara.number:04d}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
