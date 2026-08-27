import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import CajaMovimiento, CajaSession, MetodoPago, TipoMovimiento, VentaExterna
from ...schemas import (
    CajaCierreIn, CajaMovimientoIn, CajaMovimientoOut, CajaSessionIn, CajaSessionOut,
)
from ...services.security import require_admin

router = APIRouter(prefix="/admin", tags=["erp"], dependencies=[Depends(require_admin)])


def _mov_totals(session_id: uuid.UUID, db: Session) -> tuple:
    """Returns (total_entrades, total_sortides) from caja_movimientos for a session."""
    movs = db.scalars(
        select(CajaMovimiento).where(CajaMovimiento.session_id == session_id)
    ).all()
    entrades = sum((m.amount for m in movs if m.type == TipoMovimiento.entrada), Decimal("0"))
    sortides = sum((m.amount for m in movs if m.type == TipoMovimiento.salida), Decimal("0"))
    return entrades, sortides


def _caja_out(s: CajaSession, total_entrades=None, total_sortides=None) -> CajaSessionOut:
    te = total_entrades if total_entrades is not None else (s.total_cash_in or Decimal("0"))
    ts = total_sortides if total_sortides is not None else (s.total_cash_out or Decimal("0"))
    diferencia = None
    if s.actual_count is not None and s.total_cash_sales is not None:
        diferencia = s.actual_count - s.opening_float - s.total_cash_sales - te + ts
    return CajaSessionOut(
        id=s.id,
        opened_at=s.opened_at,
        opening_float=s.opening_float,
        closed_at=s.closed_at,
        total_cash_sales=s.total_cash_sales,
        total_cash_in=te,
        total_cash_out=ts,
        actual_count=s.actual_count,
        diferencia=diferencia,
        notes=s.notes,
        created_at=s.created_at,
    )


@router.post("/caja/apertura", status_code=201, response_model=CajaSessionOut)
def abrir_caja(payload: CajaSessionIn, db: Session = Depends(get_db)):
    sesion_activa = db.scalar(
        select(CajaSession).where(CajaSession.closed_at.is_(None))
        .order_by(CajaSession.opened_at.desc())
    )
    if sesion_activa:
        raise HTTPException(409, "Ya hay una sesión de caja abierta")
    s = CajaSession(
        opened_at=payload.opened_at,
        opening_float=payload.opening_float,
        notes=payload.notes,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _caja_out(s, Decimal("0"), Decimal("0"))


@router.post("/caja/cierre/{session_id}", response_model=CajaSessionOut)
def cerrar_caja(session_id: uuid.UUID, payload: CajaCierreIn, db: Session = Depends(get_db)):
    s = db.get(CajaSession, session_id)
    if s is None:
        raise HTTPException(404, "Sesión de caja no encontrada")
    if s.closed_at is not None:
        raise HTTPException(409, "La sesión ya está cerrada")

    ventas_efectivo = db.scalars(
        select(VentaExterna).where(
            VentaExterna.payment_method == MetodoPago.efectivo,
            VentaExterna.date >= s.opened_at,
        )
    ).all()
    total = sum(v.sale_price for v in ventas_efectivo)

    te, ts = _mov_totals(session_id, db)

    s.closed_at = datetime.now(timezone.utc)
    s.total_cash_sales = total
    s.total_cash_in = te
    s.total_cash_out = ts
    s.actual_count = payload.actual_count
    if payload.notes:
        s.notes = payload.notes
    db.commit()
    db.refresh(s)
    return _caja_out(s, te, ts)


@router.get("/caja/activa", response_model=CajaSessionOut | None)
def get_caja_activa(db: Session = Depends(get_db)):
    s = db.scalar(
        select(CajaSession).where(CajaSession.closed_at.is_(None))
        .order_by(CajaSession.opened_at.desc())
    )
    if s is None:
        return None
    te, ts = _mov_totals(s.id, db)
    return _caja_out(s, te, ts)


@router.get("/caja/sessions", response_model=list[CajaSessionOut])
def list_caja_sessions(db: Session = Depends(get_db)):
    sessions = db.scalars(
        select(CajaSession).order_by(CajaSession.opened_at.desc())
    ).all()
    return [_caja_out(s) for s in sessions]


# ---------------------------------------------------------------------------
# Moviments de caixa (entrades i sortides manuals)
# ---------------------------------------------------------------------------

@router.post("/caja/movimientos", status_code=201, response_model=CajaMovimientoOut)
def create_movimiento(payload: CajaMovimientoIn, db: Session = Depends(get_db)):
    sesion = db.scalar(
        select(CajaSession).where(CajaSession.closed_at.is_(None))
        .order_by(CajaSession.opened_at.desc())
    )
    if sesion is None:
        raise HTTPException(409, "No hay ninguna sesión de caja abierta")
    mov = CajaMovimiento(
        session_id=sesion.id,
        type=TipoMovimiento(payload.type),
        concept=payload.concept,
        amount=payload.amount,
        date=payload.date,
    )
    db.add(mov)
    db.commit()
    db.refresh(mov)
    return mov


@router.get("/caja/movimientos", response_model=list[CajaMovimientoOut])
def list_movimientos_activa(db: Session = Depends(get_db)):
    sesion = db.scalar(
        select(CajaSession).where(CajaSession.closed_at.is_(None))
        .order_by(CajaSession.opened_at.desc())
    )
    if sesion is None:
        return []
    return db.scalars(
        select(CajaMovimiento)
        .where(CajaMovimiento.session_id == sesion.id)
        .order_by(CajaMovimiento.date)
    ).all()


@router.get("/caja/sessions/{session_id}/movimientos", response_model=list[CajaMovimientoOut])
def list_movimientos_session(session_id: uuid.UUID, db: Session = Depends(get_db)):
    if db.get(CajaSession, session_id) is None:
        raise HTTPException(404, "Sesión no encontrada")
    return db.scalars(
        select(CajaMovimiento)
        .where(CajaMovimiento.session_id == session_id)
        .order_by(CajaMovimiento.date)
    ).all()
