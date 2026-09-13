"""Remeses de pagament a proveïdors (SEPA pain.001.001.03, transferència —
NO domiciliació) — ver docs/PLAN_COBRAMENTS_PAGAMENTS.md.

NOMÉS genera el fitxer; mai l'envia al banc. L'admin sempre el descarrega i
el puja a mà al portal del seu banc."""

import io
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ...database import get_db
from ...models import (
    CompteBancari, ConfiguracioBotiga, Despesa, EstatPagamentDespesa, RemesaPagament,
    RemesaPagamentLinia, RemesaPagamentStatus,
)
from ...schemas import (
    DespesaElegibleRemesaOut, RemesaPagamentGenerarIn, RemesaPagamentLiniaOut, RemesaPagamentOut,
)
from ...services.documents_numbering import next_document_number
from ...services.security import require_admin
from ...services.sepa_pain001 import Pain001Linia, build_pain001_xml, generate_end_to_end_id

router = APIRouter(prefix="/admin", tags=["comptabilitat"], dependencies=[Depends(require_admin)])


def _remesa_out(remesa: RemesaPagament) -> RemesaPagamentOut:
    return RemesaPagamentOut(
        id=remesa.id, fiscal_year=remesa.fiscal_year, number=remesa.number, status=remesa.status.value,
        compte_bancari_id=remesa.compte_bancari_id, execution_date=remesa.execution_date, total=remesa.total,
        created_at=remesa.created_at,
        lines=[
            RemesaPagamentLiniaOut(
                despesa_id=l.despesa_id, supplier_name=l.despesa.supplier_name, import_=l.import_,
                end_to_end_id=l.end_to_end_id,
            )
            for l in remesa.lines
        ],
    )


def _get_remesa_or_404(db: Session, remesa_id: uuid.UUID) -> RemesaPagament:
    remesa = db.scalar(
        select(RemesaPagament)
        .options(selectinload(RemesaPagament.lines).selectinload(RemesaPagamentLinia.despesa))
        .where(RemesaPagament.id == remesa_id)
    )
    if remesa is None:
        raise HTTPException(404, "Remesa no trobada")
    return remesa


@router.get("/remeses-pagament/despeses-elegibles", response_model=list[DespesaElegibleRemesaOut])
def despeses_elegibles_remesa(db: Session = Depends(get_db)):
    """Despeses pendents/vençudes que es poden incloure en una remesa: cal
    que es paguin per transferència i que el proveïdor tingui IBAN informat
    — sense IBAN no es pot generar cap línia SEPA."""
    despeses = db.scalars(
        select(Despesa)
        .options(selectinload(Despesa.proveidor))
        .where(Despesa.payment_status.in_([EstatPagamentDespesa.pendent, EstatPagamentDespesa.vencut]))
        .where(Despesa.payment_method == "transferencia")
        .order_by(Despesa.due_date.asc().nullslast())
    ).all()
    return [
        DespesaElegibleRemesaOut(
            despesa_id=d.id, supplier_name=d.supplier_name, due_date=d.due_date,
            net_a_pagar=d.total - (d.retencio_import or Decimal("0")),
        )
        for d in despeses if d.proveidor is not None and d.proveidor.supplier_iban
    ]


@router.post("/remeses-pagament", status_code=201, response_model=RemesaPagamentOut)
def generar_remesa(payload: RemesaPagamentGenerarIn, db: Session = Depends(get_db)):
    if not payload.despesa_ids:
        raise HTTPException(422, "Cal seleccionar com a mínim una despesa")

    compte = db.get(CompteBancari, payload.compte_bancari_id)
    if compte is None:
        raise HTTPException(404, "Compte bancari no trobat")
    if not compte.iban:
        raise HTTPException(422, "El compte bancari emissor no té IBAN informat")

    despeses = db.scalars(
        select(Despesa).options(selectinload(Despesa.proveidor)).where(Despesa.id.in_(payload.despesa_ids))
    ).all()
    trobades = {d.id for d in despeses}
    faltants = set(payload.despesa_ids) - trobades
    if faltants:
        raise HTTPException(404, f"Despeses no trobades: {', '.join(str(f) for f in faltants)}")

    errors = []
    for d in despeses:
        if d.payment_status not in (EstatPagamentDespesa.pendent, EstatPagamentDespesa.vencut):
            errors.append(f"{d.supplier_name}: no està pendent de pagament")
        elif d.proveidor is None or not d.proveidor.supplier_iban:
            errors.append(f"{d.supplier_name}: el proveïdor no té IBAN informat")
    if errors:
        raise HTTPException(422, "; ".join(errors))

    fiscal_year = date.today().year
    number = next_document_number(db, "remesa_pagament", fiscal_year)
    remesa_number_str = f"{fiscal_year}-{number:04d}"

    config = db.scalar(select(ConfiguracioBotiga))
    debtor_name = config.fiscal_name if config else compte.name

    pain_lines: list[Pain001Linia] = []
    remesa_lines: list[RemesaPagamentLinia] = []
    total = Decimal("0.00")
    for i, d in enumerate(despeses, start=1):
        net = d.total - (d.retencio_import or Decimal("0"))
        e2e = generate_end_to_end_id(remesa_number_str, i)
        pain_lines.append(Pain001Linia(
            end_to_end_id=e2e, amount=net, creditor_name=d.proveidor.name,
            creditor_iban=d.proveidor.supplier_iban, remittance_info=d.invoice_number or d.concept,
        ))
        remesa_lines.append(RemesaPagamentLinia(despesa_id=d.id, position=i, import_=net, end_to_end_id=e2e))
        total += net

    xml_content = build_pain001_xml(
        remesa_number=remesa_number_str, execution_date=payload.execution_date,
        created_at=datetime.now(timezone.utc), debtor_name=debtor_name, debtor_iban=compte.iban,
        debtor_bic=compte.bic, lines=pain_lines,
    )

    remesa = RemesaPagament(
        fiscal_year=fiscal_year, number=number, compte_bancari_id=compte.id,
        execution_date=payload.execution_date, total=total, xml_content=xml_content, lines=remesa_lines,
    )
    db.add(remesa)
    db.flush()

    for d in despeses:
        d.payment_status = EstatPagamentDespesa.en_remesa

    db.commit()
    return _remesa_out(_get_remesa_or_404(db, remesa.id))


@router.get("/remeses-pagament", response_model=list[RemesaPagamentOut])
def list_remeses(db: Session = Depends(get_db)):
    remeses = db.scalars(
        select(RemesaPagament)
        .options(selectinload(RemesaPagament.lines).selectinload(RemesaPagamentLinia.despesa))
        .order_by(RemesaPagament.created_at.desc())
    ).all()
    return [_remesa_out(r) for r in remeses]


@router.get("/remeses-pagament/{remesa_id}", response_model=RemesaPagamentOut)
def get_remesa(remesa_id: uuid.UUID, db: Session = Depends(get_db)):
    return _remesa_out(_get_remesa_or_404(db, remesa_id))


@router.get("/remeses-pagament/{remesa_id}/xml")
def download_remesa_xml(remesa_id: uuid.UUID, db: Session = Depends(get_db)):
    remesa = _get_remesa_or_404(db, remesa_id)
    filename = f"remesa_{remesa.fiscal_year}_{remesa.number:04d}.xml"
    return StreamingResponse(
        io.BytesIO(remesa.xml_content.encode("utf-8")), media_type="application/xml",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/remeses-pagament/{remesa_id}/anullar", response_model=RemesaPagamentOut)
def anullar_remesa(remesa_id: uuid.UUID, db: Session = Depends(get_db)):
    """Anul·la la remesa (mai es reutilitza el número) i allibera les
    despeses que encara estiguin `en_remesa` tornant-les a `pendent` — les
    que ja s'haguessin conciliat per una altra via es deixen tal qual."""
    remesa = _get_remesa_or_404(db, remesa_id)
    if remesa.status == RemesaPagamentStatus.anullada:
        raise HTTPException(409, "Aquesta remesa ja està anul·lada")

    for linia in remesa.lines:
        if linia.despesa.payment_status == EstatPagamentDespesa.en_remesa:
            linia.despesa.payment_status = EstatPagamentDespesa.pendent

    remesa.status = RemesaPagamentStatus.anullada
    db.commit()
    return _remesa_out(_get_remesa_or_404(db, remesa.id))
