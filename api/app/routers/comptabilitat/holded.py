"""Exportació experimental a Holded — ver services/holded_export.py per
l'avís sobre l'esquema NO verificat del payload. No forma part de cap flux
automàtic: només es crida quan l'admin prem "Exportar a Holded" a mà."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ...database import get_db
from ...models import JournalEntry, JournalLine
from ...schemas import HoldedExportIn, HoldedExportLiniaOut, HoldedExportOut
from ...services.holded_export import HoldedExportError, push_ledger_entry
from ...services.security import require_admin
from ...tenant_secrets import get_tenant_secrets
from .llibres import _fi_de_mes, _validar_mes

router = APIRouter(prefix="/admin", tags=["comptabilitat"], dependencies=[Depends(require_admin)])


@router.post("/holded/export", response_model=HoldedExportOut)
def export_holded(payload: HoldedExportIn, request: Request, db: Session = Depends(get_db)):
    _validar_mes(payload.mes_desde)
    _validar_mes(payload.mes_fins)
    if payload.mes_desde > payload.mes_fins:
        raise HTTPException(422, "mes_desde no pot ser posterior a mes_fins")

    secrets = get_tenant_secrets(request.state.tenant.id)
    if not secrets.holded_api_key:
        raise HTTPException(
            422, "Cal desar la clau d'API de Holded (POST /admin/secrets, camp holded_api_key) abans d'exportar"
        )

    entries = db.scalars(
        select(JournalEntry)
        .where(JournalEntry.fiscal_year == payload.year)
        .where(
            JournalEntry.date >= date(payload.year, payload.mes_desde, 1),
            JournalEntry.date <= _fi_de_mes(payload.year, payload.mes_fins),
        )
        .options(selectinload(JournalEntry.lines).selectinload(JournalLine.account))
        .order_by(JournalEntry.entry_number)
    ).all()

    resultats: list[HoldedExportLiniaOut] = []
    for entry in entries:
        codis_sense_mapeig = {l.account.code for l in entry.lines} - payload.account_mapping.keys()
        if codis_sense_mapeig:
            resultats.append(HoldedExportLiniaOut(
                entry_number=entry.entry_number, status="error",
                detail=f"Sense mapeig a Holded: {', '.join(sorted(codis_sense_mapeig))}",
            ))
            continue
        lines = [
            {
                "holded_account_id": payload.account_mapping[l.account.code],
                "debit": l.debit, "credit": l.credit, "description": l.description,
            }
            for l in entry.lines
        ]
        try:
            push_ledger_entry(
                secrets.holded_api_key, date_iso=entry.date.isoformat(),
                description=f"[{entry.entry_number}] {entry.description}", lines=lines,
            )
            resultats.append(HoldedExportLiniaOut(entry_number=entry.entry_number, status="ok"))
        except HoldedExportError as exc:
            resultats.append(HoldedExportLiniaOut(entry_number=entry.entry_number, status="error", detail=str(exc)))

    return HoldedExportOut(
        year=payload.year, mes_desde=payload.mes_desde, mes_fins=payload.mes_fins, resultats=resultats,
    )
