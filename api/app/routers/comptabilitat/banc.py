import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ...database import get_db
from ...models import (
    CompteBancari, Despesa, EstatConciliacio, EstatPagamentDespesa, JournalSourceType, MovimentBancari, Order,
    Proveedor, ReglaConciliacio, VentaExterna,
)
from ...schemas import (
    CompteBancariIn, CompteBancariOut, ConciliarMovimentIn, DespesaSuggerimentOut, MovimentBancariOut,
    ReglaConciliacioIn, ReglaConciliacioOut,
)
from ...services.banc_conciliacio import apply_rules_to_pending, find_matching_rule, rank_despesa_candidates
from ...services.comptabilitat_posting import post_cobrament_conciliacio, post_despesa_pagament
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


def _regla_out(regla: ReglaConciliacio) -> dict:
    return {
        "id": regla.id, "pattern": regla.pattern, "proveidor_id": regla.proveidor_id,
        "proveidor_nom": regla.proveidor.name, "active": regla.active, "created_at": regla.created_at,
    }


@router.post("/banc/regles", status_code=201, response_model=ReglaConciliacioOut)
def create_regla(payload: ReglaConciliacioIn, db: Session = Depends(get_db)):
    if db.get(Proveedor, payload.proveidor_id) is None:
        raise HTTPException(404, "Proveïdor no trobat")
    regla = ReglaConciliacio(**payload.model_dump())
    db.add(regla)
    db.commit()
    db.refresh(regla)
    return _regla_out(regla)


@router.get("/banc/regles", response_model=list[ReglaConciliacioOut])
def list_regles(db: Session = Depends(get_db)):
    regles = db.scalars(
        select(ReglaConciliacio).options(selectinload(ReglaConciliacio.proveidor)).order_by(ReglaConciliacio.pattern)
    ).all()
    return [_regla_out(r) for r in regles]


@router.patch("/banc/regles/{regla_id}", response_model=ReglaConciliacioOut)
def update_regla(regla_id: int, payload: ReglaConciliacioIn, db: Session = Depends(get_db)):
    regla = db.get(ReglaConciliacio, regla_id)
    if regla is None:
        raise HTTPException(404, "Regla no trobada")
    if db.get(Proveedor, payload.proveidor_id) is None:
        raise HTTPException(404, "Proveïdor no trobat")
    for k, v in payload.model_dump().items():
        setattr(regla, k, v)
    db.commit()
    db.refresh(regla)
    return _regla_out(regla)


@router.delete("/banc/regles/{regla_id}", status_code=204)
def delete_regla(regla_id: int, db: Session = Depends(get_db)):
    regla = db.get(ReglaConciliacio, regla_id)
    if regla is None:
        raise HTTPException(404, "Regla no trobada")
    db.delete(regla)
    db.commit()


@router.post("/banc/{compte_id}/aplicar-regles")
def aplicar_regles(compte_id: int, db: Session = Depends(get_db)):
    """Reaplica les regles actives als moviments pendents ja importats
    d'aquest compte — útil quan es dona d'alta o s'edita una regla i hi ha
    moviments antics que ara ja hi farien match."""
    if db.get(CompteBancari, compte_id) is None:
        raise HTTPException(404, "Compte no trobat")
    conciliats = apply_rules_to_pending(db, compte_id)
    db.commit()
    return {"conciliats": conciliats}


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

    conciliats_auto = apply_rules_to_pending(db, compte_id)
    db.commit()

    return {
        "importats": nous, "total_fitxer": len(moviments), "duplicats_ignorats": len(moviments) - nous,
        "conciliats_auto": conciliats_auto,
    }


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


@router.get("/banc/moviments/{moviment_id}/suggeriments", response_model=list[DespesaSuggerimentOut])
def suggeriments_moviment(moviment_id: uuid.UUID, db: Session = Depends(get_db)):
    """Despeses pendents amb import exacte al moviment, per proximitat de
    data — per pre-omplir el desplegable de conciliació manual sense que
    l'admin hagi de buscar-la a mà (Bloc B3)."""
    mov = db.get(MovimentBancari, moviment_id)
    if mov is None:
        raise HTTPException(404, "Moviment no trobat")
    if mov.movement_amount >= 0:
        return []
    regla = find_matching_rule(db, mov.concept)
    candidats = rank_despesa_candidates(db, mov, proveidor_id=regla.proveidor_id if regla else None)
    return [
        {
            "despesa_id": d.id, "supplier_name": d.supplier_name, "concept": d.concept,
            "total": d.total, "invoice_date": d.invoice_date, "due_date": d.due_date,
        }
        for d in candidats
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
            post_despesa_pagament(
                db, despesa, payment_date=mov.operation_date, amount=abs(mov.movement_amount), cash=False,
            )

    # Si conciliem amb una venda externa, la marquem com a cobrada
    if payload.status == "conciliat" and payload.venta_externa_id:
        venta = db.get(VentaExterna, payload.venta_externa_id)
        if venta and venta.paid_at is None:
            venta.paid_at = datetime.combine(mov.operation_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            post_cobrament_conciliacio(
                db, entry_date=mov.operation_date, source_type=JournalSourceType.venda_externa,
                source_id=venta.id, amount=abs(mov.movement_amount),
                description=f"Cobrament venda {venta.channel.value} #{str(venta.ticket_id)[:8]}",
            )

    # Si conciliem amb un order, el marquem com a cobrat
    if payload.status == "conciliat" and payload.order_id:
        order = db.get(Order, payload.order_id)
        if order and order.paid_at is None:
            order.paid_at = datetime.combine(mov.operation_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            post_cobrament_conciliacio(
                db, entry_date=mov.operation_date, source_type=JournalSourceType.venda_web,
                source_id=order.id, amount=abs(mov.movement_amount),
                description=f"Cobrament venda web #{str(order.id)[:8]}",
            )

    db.commit()
    db.refresh(mov)
    return MovimentBancariOut(
        **{c: getattr(mov, c) for c in MovimentBancariOut.model_fields if hasattr(mov, c)},
        despesa_concepte=mov.despesa.concept if mov.despesa else None,
        despesa_proveidor=mov.despesa.supplier_name if mov.despesa else None,
    )
