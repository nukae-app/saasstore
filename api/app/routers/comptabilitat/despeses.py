import io
import uuid
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from ...database import get_db
from ...models import CategoriaDespesa, Compra, Despesa, EstatPagamentDespesa, Proveedor, TipusIva
from ...schemas import DespesaDesDeComprasIn, DespesaIn, DespesaOut, DespesaUpdate
from ...services.comptabilitat_posting import post_despesa_alta, post_despesa_pagament
from ...services.documents_pdf import generate_despesa_pdf
from ...services.security import require_admin

router = APIRouter(prefix="/admin", tags=["comptabilitat"], dependencies=[Depends(require_admin)])


def _calc_venciment(data_factura: date, prov: Proveedor | None) -> date | None:
    if prov is None or prov.payment_days is None:
        return None
    due = data_factura + timedelta(days=prov.payment_days)
    if prov.payment_day_of_month:
        # Avança al dia fix del mes: si el dia ja ha passat, va al mes següent
        d = prov.payment_day_of_month
        if due.day <= d:
            try:
                due = due.replace(day=d)
            except ValueError:
                pass  # dia invàlid per a aquell mes → deixem la data calculada
        else:
            # Primer dia del mes següent, ajustat
            if due.month == 12:
                due = date(due.year + 1, 1, d)
            else:
                try:
                    due = date(due.year, due.month + 1, d)
                except ValueError:
                    pass
    return due


def _despesa_out(d: Despesa) -> dict:
    return {
        "id": d.id, "invoice_number": d.invoice_number, "invoice_date": d.invoice_date,
        "due_date": d.due_date, "proveidor_id": d.proveidor_id,
        "supplier_name": d.supplier_name, "category": d.category, "concept": d.concept,
        "taxable_base": d.taxable_base, "tipus_iva_id": d.tipus_iva_id, "vat_pct": d.vat_pct,
        "vat_amount": d.vat_amount, "total": d.total, "payment_status": d.payment_status,
        "payment_date": d.payment_date, "payment_method": d.payment_method,
        "compra_ids": [c.id for c in d.compras], "notes": d.notes, "created_at": d.created_at,
    }


@router.post("/despeses", status_code=201, response_model=DespesaOut)
def create_despesa(payload: DespesaIn, db: Session = Depends(get_db)):
    prov = db.get(Proveedor, payload.proveidor_id) if payload.proveidor_id else None

    # Si es tria un tipus d'IVA del catàleg, el seu percentatge mana sobre el vat_pct enviat.
    vat_pct = payload.vat_pct
    if payload.tipus_iva_id is not None:
        tipus = db.get(TipusIva, payload.tipus_iva_id)
        if tipus is None:
            raise HTTPException(404, "Tipus d'IVA no trobat")
        vat_pct = tipus.percentage

    vat_amount = (payload.taxable_base * vat_pct / 100).quantize(Decimal("0.01"))
    total = payload.total if payload.total is not None else payload.taxable_base + vat_amount

    due_date = payload.due_date or _calc_venciment(payload.invoice_date, prov)

    despesa = Despesa(
        invoice_number=payload.invoice_number,
        invoice_date=payload.invoice_date,
        due_date=due_date,
        proveidor_id=payload.proveidor_id,
        supplier_name=payload.supplier_name,
        category=CategoriaDespesa(payload.category),
        concept=payload.concept,
        taxable_base=payload.taxable_base,
        tipus_iva_id=payload.tipus_iva_id,
        vat_pct=vat_pct,
        vat_amount=vat_amount,
        total=total,
        payment_status=EstatPagamentDespesa(payload.payment_status),
        payment_date=payload.payment_date,
        payment_method=payload.payment_method,
        notes=payload.notes,
    )
    db.add(despesa)
    db.flush()
    post_despesa_alta(db, despesa)
    # L'admin pot marcar la despesa com a pagada ja en l'alta (p.ex. una
    # compra en efectiu pagada al moment) — sense passar per la conciliació
    # bancària de banc.py, que és l'altre camí cap a `pagat`.
    if despesa.payment_status == EstatPagamentDespesa.pagat:
        post_despesa_pagament(
            db, despesa, payment_date=despesa.payment_date or despesa.invoice_date,
            amount=despesa.total, cash=(despesa.payment_method == "efectiu"),
        )
    db.commit()
    db.refresh(despesa)
    return _despesa_out(despesa)


@router.get("/despeses", response_model=list[DespesaOut])
def list_despeses(
    categoria: str | None = None,
    estat: str | None = None,
    proveidor_id: uuid.UUID | None = None,
    des_de: date | None = None,
    fins_a: date | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(Despesa).options(selectinload(Despesa.compras)).order_by(Despesa.invoice_date.desc())
    if categoria:
        stmt = stmt.where(Despesa.category == categoria)
    if estat:
        stmt = stmt.where(Despesa.payment_status == estat)
    if proveidor_id:
        stmt = stmt.where(Despesa.proveidor_id == proveidor_id)
    if des_de:
        stmt = stmt.where(Despesa.invoice_date >= des_de)
    if fins_a:
        stmt = stmt.where(Despesa.invoice_date <= fins_a)
    return [_despesa_out(d) for d in db.scalars(stmt).all()]


@router.get("/despeses/pendents", response_model=list[DespesaOut])
def list_despeses_pendents(db: Session = Depends(get_db)):
    """Factures pendents de pagament ordenades per data de venciment (vençudes primer)."""
    today = date.today()
    # Actualitza vençudes automàticament
    db.execute(
        update(Despesa)
        .where(Despesa.payment_status == EstatPagamentDespesa.pendent)
        .where(Despesa.due_date < today)
        .values(payment_status=EstatPagamentDespesa.vencut)
        .execution_options(synchronize_session=False)
    )
    db.commit()
    despeses = db.scalars(
        select(Despesa)
        .options(selectinload(Despesa.compras))
        .where(Despesa.payment_status.in_([EstatPagamentDespesa.pendent, EstatPagamentDespesa.vencut]))
        .order_by(Despesa.due_date.asc().nullslast())
    ).all()
    return [_despesa_out(d) for d in despeses]


@router.get("/despeses/{despesa_id}", response_model=DespesaOut)
def get_despesa(despesa_id: uuid.UUID, db: Session = Depends(get_db)):
    d = db.scalar(
        select(Despesa).options(selectinload(Despesa.compras)).where(Despesa.id == despesa_id)
    )
    if d is None:
        raise HTTPException(404, "Despesa no trobada")
    return _despesa_out(d)


@router.get("/despeses/{despesa_id}/pdf")
def despesa_pdf(despesa_id: uuid.UUID, db: Session = Depends(get_db)):
    """Formalitza la despesa (factura de compra ja registrada) com a PDF —
    veure docs/PLAN_PARIDAD_HOLDED.md bloc B1."""
    d = db.get(Despesa, despesa_id)
    if d is None:
        raise HTTPException(404, "Despesa no trobada")
    pdf_bytes = generate_despesa_pdf(d, db)
    filename = f"factura_compra_{d.id}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.patch("/despeses/{despesa_id}", response_model=DespesaOut)
def update_despesa(despesa_id: uuid.UUID, payload: DespesaUpdate, db: Session = Depends(get_db)):
    d = db.scalar(
        select(Despesa).options(selectinload(Despesa.compras)).where(Despesa.id == despesa_id)
    )
    if d is None:
        raise HTTPException(404, "Despesa no trobada")
    data = payload.model_dump(exclude_unset=True)
    # Si es canvia el tipus d'IVA, el seu percentatge mana sobre vat_pct
    if "tipus_iva_id" in data and data["tipus_iva_id"] is not None:
        tipus = db.get(TipusIva, data["tipus_iva_id"])
        if tipus is None:
            raise HTTPException(404, "Tipus d'IVA no trobat")
        data.setdefault("vat_pct", tipus.percentage)
    # Recalcula vat_amount si canvia base, vat_pct o tipus_iva_id
    if "taxable_base" in data or "vat_pct" in data or "tipus_iva_id" in data:
        base = data.get("taxable_base", d.taxable_base)
        pct = data.get("vat_pct", d.vat_pct)
        data.setdefault("vat_amount", (base * pct / 100).quantize(Decimal("0.01")))
        data.setdefault("total", base + data["vat_amount"])
    for k, v in data.items():
        setattr(d, k, v)
    db.commit()
    db.refresh(d)
    return _despesa_out(d)


@router.delete("/despeses/{despesa_id}", status_code=204)
def delete_despesa(despesa_id: uuid.UUID, db: Session = Depends(get_db)):
    d = db.get(Despesa, despesa_id)
    if d is None:
        raise HTTPException(404, "Despesa no trobada")
    if d.payment_status == EstatPagamentDespesa.pagat:
        raise HTTPException(409, "No es pot eliminar una despesa ja pagada")
    db.delete(d)
    db.commit()


@router.post("/despeses/des-de-compres", status_code=201, response_model=DespesaOut)
def crear_despesa_des_de_compres(payload: DespesaDesDeComprasIn, db: Session = Depends(get_db)):
    """Crea la factura d'un proveïdor a partir d'una o més recepcions (Compra) encara
    sense facturar. Permet agrupar diversos albarans en una única factura."""
    compres = db.scalars(
        select(Compra).where(Compra.id.in_(payload.compra_ids))
        .options(selectinload(Compra.items), selectinload(Compra.proveedor))
    ).all()
    if len(compres) != len(set(payload.compra_ids)):
        raise HTTPException(404, "Alguna de les recepcions indicades no existeix")
    for c in compres:
        if c.type != "proveedor":
            raise HTTPException(422, "Només es poden facturar recepcions de proveïdor")
        if c.despesa_id is not None:
            raise HTTPException(409, f"La recepció del {c.date.date()} ja té una factura associada")
    proveidor_ids = {c.proveedor_id for c in compres}
    if len(proveidor_ids) > 1:
        raise HTTPException(422, "Totes les recepcions han de ser del mateix proveïdor")

    prov = compres[0].proveedor
    prov_nom = prov.name if prov else "Proveïdor"
    # `Compra.total_cost` es la fuente fiable desde que una línea nou puede
    # acumular varias recepciones en la misma fila Item (que solo puede
    # apuntar a una compra_id, la última) — sumar item.acquisition_cost vía
    # Compra.items ya no reflejaría el coste real de recepciones anteriores.
    # Fallback al cálculo antiguo solo para compras previas a este campo.
    total_cost = sum(
        c.total_cost if c.total_cost is not None
        else sum((it.acquisition_cost or Decimal("0")) for it in c.items)
        for c in compres
    )
    total_items = sum(len(c.items) for c in compres)

    tipus = db.get(TipusIva, payload.tipus_iva_id) if payload.tipus_iva_id else db.scalar(
        select(TipusIva).where(TipusIva.active == True, TipusIva.is_rebu == False)
        .order_by(TipusIva.percentage.desc())
    )
    pct = tipus.percentage if tipus else Decimal("21.00")
    base = (total_cost / (1 + pct / 100)).quantize(Decimal("0.01"))
    iva = total_cost - base

    data_factura = payload.invoice_date or date.today()
    data_venciment = _calc_venciment(data_factura, prov)

    despesa = Despesa(
        invoice_number=payload.invoice_number,
        invoice_date=data_factura,
        due_date=data_venciment,
        proveidor_id=prov.id if prov else None,
        supplier_name=prov_nom,
        tipus_iva_id=tipus.id if tipus else None,
        category=CategoriaDespesa.compres_material,
        concept=f"Compra discos ({len(compres)} recepcions, {total_items} exemplars)",
        taxable_base=base,
        vat_pct=pct,
        vat_amount=iva,
        total=total_cost,
        payment_status=EstatPagamentDespesa.pendent,
        notes=payload.notes,
    )
    db.add(despesa)
    db.flush()
    for c in compres:
        c.despesa_id = despesa.id
    db.commit()
    db.refresh(despesa)
    return _despesa_out(despesa)
