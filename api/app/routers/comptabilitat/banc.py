import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ...database import get_db
from ...models import (
    CompteBancari, Despesa, EstatConciliacio, EstatPagamentDespesa, MovimentBancari, Order,
    VentaExterna,
)
from ...schemas import CompteBancariIn, CompteBancariOut, ConciliarMovimentIn, MovimentBancariOut
from ...services.n43 import parse_csv_generic, parse_n43
from ...services.security import require_admin

router = APIRouter(prefix="/admin", tags=["comptabilitat"], dependencies=[Depends(require_admin)])


@router.post("/comptes", status_code=201, response_model=CompteBancariOut)
def create_compte(payload: CompteBancariIn, db: Session = Depends(get_db)):
    compte = CompteBancari(**payload.model_dump())
    db.add(compte)
    db.commit()
    db.refresh(compte)
    return compte


@router.get("/comptes", response_model=list[CompteBancariOut])
def list_comptes(db: Session = Depends(get_db)):
    return db.scalars(select(CompteBancari).where(CompteBancari.active == True).order_by(CompteBancari.id)).all()


@router.patch("/comptes/{compte_id}", response_model=CompteBancariOut)
def update_compte(compte_id: int, payload: CompteBancariIn, db: Session = Depends(get_db)):
    compte = db.get(CompteBancari, compte_id)
    if compte is None:
        raise HTTPException(404, "Compte no trobat")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(compte, k, v)
    db.commit()
    db.refresh(compte)
    return compte


@router.post("/banc/{compte_id}/import", status_code=201)
async def import_extracte(
    compte_id: int,
    fitxer: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    compte = db.get(CompteBancari, compte_id)
    if compte is None:
        raise HTTPException(404, "Compte no trobat")

    content = (await fitxer.read()).decode("latin-1", errors="replace")
    filename = (fitxer.filename or "").lower()

    if filename.endswith(".n43") or filename.endswith(".txt"):
        moviments = parse_n43(content)
    else:
        moviments = parse_csv_generic(content)

    if not moviments:
        raise HTTPException(422, "No s'han trobat moviments al fitxer")

    # Evita duplicats per data+concepte+import (heurística simple)
    existents = db.scalars(
        select(MovimentBancari)
        .where(MovimentBancari.compte_id == compte_id)
        .where(MovimentBancari.operation_date >= moviments[0].data_operacio)
    ).all()
    existents_key = {(m.operation_date, m.concept[:30], m.movement_amount) for m in existents}

    nous = 0
    for m in moviments:
        key = (m.data_operacio, m.concepte[:30], m.import_moviment)
        if key in existents_key:
            continue
        db.add(MovimentBancari(
            compte_id=compte_id,
            operation_date=m.data_operacio,
            value_date=m.data_valor,
            concept=m.concepte,
            movement_amount=m.import_moviment,
            balance=m.saldo,
        ))
        nous += 1

    db.commit()
    return {"importats": nous, "total_fitxer": len(moviments), "duplicats_ignorats": len(moviments) - nous}


@router.get("/banc/{compte_id}/moviments", response_model=list[MovimentBancariOut])
def list_moviments(
    compte_id: int,
    estat: str | None = None,
    des_de: date | None = None,
    fins_a: date | None = None,
    db: Session = Depends(get_db),
):
    stmt = (
        select(MovimentBancari)
        .where(MovimentBancari.compte_id == compte_id)
        .options(selectinload(MovimentBancari.despesa))
        .order_by(MovimentBancari.operation_date.desc())
    )
    if estat:
        stmt = stmt.where(MovimentBancari.status == estat)
    if des_de:
        stmt = stmt.where(MovimentBancari.operation_date >= des_de)
    if fins_a:
        stmt = stmt.where(MovimentBancari.operation_date <= fins_a)

    movs = db.scalars(stmt).all()
    return [
        MovimentBancariOut(
            **{c: getattr(m, c) for c in MovimentBancariOut.model_fields if hasattr(m, c)},
            despesa_concepte=m.despesa.concept if m.despesa else None,
            despesa_proveidor=m.despesa.supplier_name if m.despesa else None,
        )
        for m in movs
    ]


@router.patch("/banc/moviments/{moviment_id}/conciliar", response_model=MovimentBancariOut)
def conciliar_moviment(
    moviment_id: uuid.UUID,
    payload: ConciliarMovimentIn,
    db: Session = Depends(get_db),
):
    mov = db.get(MovimentBancari, moviment_id)
    if mov is None:
        raise HTTPException(404, "Moviment no trobat")
    if mov.status == EstatConciliacio.conciliat:
        raise HTTPException(409, "El moviment ja està conciliat")

    mov.status = EstatConciliacio(payload.status)
    mov.despesa_id = payload.despesa_id
    mov.order_id = payload.order_id
    mov.venta_externa_id = payload.venta_externa_id
    mov.reconciliation_notes = payload.reconciliation_notes

    # Si conciliem amb una despesa, la marquem com a pagada
    if payload.status == "conciliat" and payload.despesa_id:
        despesa = db.get(Despesa, payload.despesa_id)
        if despesa and despesa.payment_status != EstatPagamentDespesa.pagat:
            despesa.payment_status = EstatPagamentDespesa.pagat
            despesa.payment_date = mov.operation_date

    # Si conciliem amb una venda externa, la marquem com a cobrada
    if payload.status == "conciliat" and payload.venta_externa_id:
        venta = db.get(VentaExterna, payload.venta_externa_id)
        if venta and venta.paid_at is None:
            venta.paid_at = datetime.combine(mov.operation_date, datetime.min.time()).replace(tzinfo=timezone.utc)

    # Si conciliem amb un order, el marquem com a cobrat
    if payload.status == "conciliat" and payload.order_id:
        order = db.get(Order, payload.order_id)
        if order and order.paid_at is None:
            order.paid_at = datetime.combine(mov.operation_date, datetime.min.time()).replace(tzinfo=timezone.utc)

    db.commit()
    db.refresh(mov)
    return MovimentBancariOut(
        **{c: getattr(mov, c) for c in MovimentBancariOut.model_fields if hasattr(mov, c)},
        despesa_concepte=mov.despesa.concept if mov.despesa else None,
        despesa_proveidor=mov.despesa.supplier_name if mov.despesa else None,
    )
