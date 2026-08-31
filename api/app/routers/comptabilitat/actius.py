"""Actius fixos (immobilitzat material) i la seva amortització — ver
models/actius.py per què la baixa (venda/desballestament) no està
implementada encara."""

import calendar
import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import AssetCategory, AssetDepreciationEntry, FixedAsset
from ...schemas import (
    AssetDepreciationEntryOut, FixedAssetIn, FixedAssetOut, GenerarAmortitzacionsOut,
)
from ...services.comptabilitat_posting import post_actiu_alta, post_amortitzacio
from ...services.security import require_admin

router = APIRouter(prefix="/admin", tags=["comptabilitat"], dependencies=[Depends(require_admin)])


def _accumulated(db: Session, actiu_id: uuid.UUID) -> Decimal:
    total = db.execute(
        select(AssetDepreciationEntry.amount).where(AssetDepreciationEntry.actiu_id == actiu_id)
    ).scalars().all()
    return sum(total, Decimal("0.00"))


def _actiu_out(db: Session, actiu: FixedAsset) -> FixedAssetOut:
    acumulat = _accumulated(db, actiu.id)
    return FixedAssetOut(
        id=actiu.id, name=actiu.name, category=actiu.category.value, acquisition_date=actiu.acquisition_date,
        acquisition_cost=actiu.acquisition_cost, vat_amount=actiu.vat_amount, supplier_name=actiu.supplier_name,
        depreciation_method=actiu.depreciation_method.value, annual_depreciation_pct=actiu.annual_depreciation_pct,
        disposal_date=actiu.disposal_date, disposal_amount=actiu.disposal_amount, notes=actiu.notes,
        created_at=actiu.created_at, accumulated_depreciation=acumulat, book_value=actiu.acquisition_cost - acumulat,
    )


@router.post("/actius", status_code=201, response_model=FixedAssetOut)
def create_actiu(payload: FixedAssetIn, db: Session = Depends(get_db)):
    actiu = FixedAsset(
        name=payload.name, category=AssetCategory(payload.category), acquisition_date=payload.acquisition_date,
        acquisition_cost=payload.acquisition_cost, vat_amount=payload.vat_amount,
        supplier_name=payload.supplier_name, annual_depreciation_pct=payload.annual_depreciation_pct,
        notes=payload.notes,
    )
    db.add(actiu)
    db.flush()
    post_actiu_alta(db, actiu)
    db.commit()
    db.refresh(actiu)
    return _actiu_out(db, actiu)


@router.get("/actius", response_model=list[FixedAssetOut])
def list_actius(db: Session = Depends(get_db)):
    actius = db.scalars(select(FixedAsset).order_by(FixedAsset.acquisition_date.desc())).all()
    return [_actiu_out(db, a) for a in actius]


@router.get("/actius/{actiu_id}", response_model=FixedAssetOut)
def get_actiu(actiu_id: uuid.UUID, db: Session = Depends(get_db)):
    actiu = db.get(FixedAsset, actiu_id)
    if actiu is None:
        raise HTTPException(404, "Actiu no trobat")
    return _actiu_out(db, actiu)


@router.post("/amortitzacions/{year}/{mes}/generar", response_model=GenerarAmortitzacionsOut)
def generar_amortitzacions(year: int, mes: int, db: Session = Depends(get_db)):
    if not (1 <= mes <= 12):
        raise HTTPException(422, "Mes ha de ser entre 1 i 12")
    fi_de_mes = date(year, mes, calendar.monthrange(year, mes)[1])

    actius = db.scalars(
        select(FixedAsset).where(FixedAsset.acquisition_date <= fi_de_mes)
    ).all()

    generades: list[AssetDepreciationEntryOut] = []
    saltats: list[str] = []
    for actiu in actius:
        if actiu.disposal_date is not None and actiu.disposal_date <= fi_de_mes:
            saltats.append(actiu.name)
            continue
        ja_existeix = db.scalar(
            select(AssetDepreciationEntry).where(
                AssetDepreciationEntry.actiu_id == actiu.id, AssetDepreciationEntry.year == year,
                AssetDepreciationEntry.month == mes,
            )
        )
        if ja_existeix is not None:
            saltats.append(actiu.name)
            continue

        acumulat = _accumulated(db, actiu.id)
        pendent = actiu.acquisition_cost - acumulat
        if pendent <= 0:
            saltats.append(actiu.name)
            continue

        quota_mensual = (actiu.acquisition_cost * actiu.annual_depreciation_pct / 100 / 12).quantize(Decimal("0.01"))
        import_final = min(quota_mensual, pendent)

        dep = AssetDepreciationEntry(actiu_id=actiu.id, year=year, month=mes, amount=import_final)
        db.add(dep)
        db.flush()
        post_amortitzacio(db, dep, actiu)
        generades.append(AssetDepreciationEntryOut(id=dep.id, actiu_id=actiu.id, year=year, month=mes, amount=import_final))

    db.commit()
    return GenerarAmortitzacionsOut(year=year, mes=mes, entrades_generades=generades, actius_saltats=saltats)
