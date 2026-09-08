import io
import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ...database import get_db
from ...models import (
    Factura, FacturaLinia, FacturaOrigen, FacturaStatus, JournalSourceType, Order, OrderItem, User, VentaExterna,
)
from ...schemas import FacturaManualIn, FacturaOut
from ...services.comptabilitat_posting import post_factura_manual, unpost_source
from ...services.documents_numbering import next_document_number
from ...services.documents_pdf import generate_factura_pdf
from ...services.security import require_admin

router = APIRouter(prefix="/admin", tags=["documents"], dependencies=[Depends(require_admin)])

VAT_PCT_DEFAULT = Decimal("21.00")


def _factura_out(factura: Factura) -> dict:
    return {
        "id": factura.id, "fiscal_year": factura.fiscal_year, "number": factura.number,
        "origen": factura.origen, "status": factura.status,
        "order_id": factura.order_id, "user_id": factura.user_id,
        "client_name": factura.client_name, "client_nif": factura.client_nif,
        "client_address": factura.client_address,
        "issue_date": factura.issue_date, "notes": factura.notes,
        "base_total": factura.base_total, "vat_total": factura.vat_total, "total": factura.total,
        "created_at": factura.created_at,
        "lines": [
            {
                "id": linia.id, "description": linia.description,
                "quantity": linia.quantity, "unit_price": linia.unit_price, "vat_pct": linia.vat_pct,
            }
            for linia in factura.lines
        ],
    }


def _get_factura_or_404(db: Session, factura_id: uuid.UUID) -> Factura:
    factura = db.scalar(
        select(Factura).options(selectinload(Factura.lines)).where(Factura.id == factura_id)
    )
    if factura is None:
        raise HTTPException(404, "Factura no trobada")
    return factura


def _preu_net_unitari(price_brut_linia: Decimal, quantity, vat_amount: Decimal | None, vat_pct: Decimal | None) -> Decimal:
    """OrderItem.price/VentaExterna.sale_price són SEMPRE bruts (IVA inclòs
    — mateix criteri que aeat.py::_acumula i post_venda), mentre que
    FacturaLinia.unit_price és NET (mateix criteri que PressupostLinia: la
    base sobre la qual es calcula l'IVA en pintar la factura). Cal
    convertir, no copiar tal qual, o la factura duplicaria l'IVA."""
    total_brut = price_brut_linia * quantity
    if vat_amount is not None:
        total_net = total_brut - vat_amount
    else:
        pct = vat_pct or VAT_PCT_DEFAULT
        total_net = total_brut / (1 + pct / 100)
    return (total_net / quantity).quantize(Decimal("0.01"))


def _totals(lines: list[FacturaLinia]) -> tuple[Decimal, Decimal, Decimal]:
    base_total = Decimal("0.00")
    vat_total = Decimal("0.00")
    for l in lines:
        subtotal = (l.quantity * l.unit_price).quantize(Decimal("0.01"))
        iva = (subtotal * l.vat_pct / 100).quantize(Decimal("0.01"))
        base_total += subtotal
        vat_total += iva
    return base_total, vat_total, base_total + vat_total


@router.post("/factures", status_code=201, response_model=FacturaOut)
def crear_factura_manual(payload: FacturaManualIn, db: Session = Depends(get_db)):
    """Factura des de zero (servei fora del catàleg) — es comptabilitza en
    emetre's, ver post_factura_manual."""
    fiscal_year = date.today().year
    number = next_document_number(db, "factura", fiscal_year)
    lines = [
        FacturaLinia(
            position=i, description=linia.description,
            quantity=linia.quantity, unit_price=linia.unit_price, vat_pct=linia.vat_pct,
        )
        for i, linia in enumerate(payload.lines)
    ]
    base_total, vat_total, total = _totals(lines)

    factura = Factura(
        fiscal_year=fiscal_year, number=number, origen=FacturaOrigen.manual, status=FacturaStatus.emesa,
        user_id=payload.user_id, client_name=payload.client_name, client_nif=payload.client_nif,
        notes=payload.notes, base_total=base_total, vat_total=vat_total, total=total, lines=lines,
    )
    db.add(factura)
    db.flush()
    post_factura_manual(db, factura)
    db.commit()
    return _factura_out(_get_factura_or_404(db, factura.id))


@router.post("/factures/des-de-order/{order_id}", status_code=201, response_model=FacturaOut)
def crear_factura_des_de_order(order_id: uuid.UUID, client_nif: str | None = None, db: Session = Depends(get_db)):
    """Factura a partir d'una venda web ja registrada — NO genera cap
    assentament nou (la venda ja es va comptabilitzar amb post_venda en el
    seu moment, ver services/checkout.py)."""
    order = db.scalar(
        select(Order)
        .options(selectinload(Order.items).selectinload(OrderItem.release))
        .where(Order.id == order_id)
    )
    if order is None:
        raise HTTPException(404, "Comanda no trobada")
    ja_existeix = db.scalar(
        select(Factura.id).where(Factura.order_id == order_id, Factura.status == FacturaStatus.emesa)
    )
    if ja_existeix is not None:
        raise HTTPException(409, "Aquesta comanda ja té una factura emesa")

    usuari = db.get(User, order.user_id) if order.user_id else None
    client_name = (
        (order.shipping_address or {}).get("recipient_name")
        or (usuari.name if usuari else None)
        or order.contact_email
    )
    lines = [
        FacturaLinia(
            position=i,
            description=f"{it.release.artista} - {it.release.title}" if it.release else "Article",
            quantity=Decimal(it.quantity), unit_price=_preu_net_unitari(it.price, it.quantity, it.vat_amount, it.vat_pct),
            vat_pct=it.vat_pct or VAT_PCT_DEFAULT,
        )
        for i, it in enumerate(order.items)
    ]
    base_total, vat_total, total = _totals(lines)

    factura = Factura(
        fiscal_year=date.today().year, number=next_document_number(db, "factura", date.today().year),
        origen=FacturaOrigen.ticket, status=FacturaStatus.emesa, order_id=order.id, user_id=order.user_id,
        client_name=client_name, client_nif=client_nif, client_address=order.shipping_address,
        base_total=base_total, vat_total=vat_total, total=total, lines=lines,
    )
    db.add(factura)
    db.commit()
    return _factura_out(_get_factura_or_404(db, factura.id))


@router.post("/factures/des-de-venda-externa/{ticket_id}", status_code=201, response_model=FacturaOut)
def crear_factura_des_de_venda_externa(ticket_id: uuid.UUID, client_nif: str | None = None, db: Session = Depends(get_db)):
    """Factura a partir d'un tiquet de TPV (una o més VentaExterna amb el
    mateix ticket_id) — NO genera cap assentament nou (ja comptabilitzat en
    vendre, ver routers/erp/ventas_externas.py)."""
    ventes = db.scalars(
        select(VentaExterna)
        .options(selectinload(VentaExterna.item), selectinload(VentaExterna.client))
        .where(VentaExterna.ticket_id == ticket_id)
    ).all()
    if not ventes:
        raise HTTPException(404, "Tiquet no trobat")
    ja_existeix = db.scalar(
        select(Factura.id).where(
            Factura.venta_externa_ticket_id == ticket_id, Factura.status == FacturaStatus.emesa,
        )
    )
    if ja_existeix is not None:
        raise HTTPException(409, "Aquest tiquet ja té una factura emesa")

    primera = ventes[0]
    client_name = primera.client_name or (primera.client.name if primera.client else None) or "Client mostrador"
    lines = [
        FacturaLinia(
            position=i,
            description=(
                f"{v.item.release.artista} - {v.item.release.title}"
                if v.item and v.item.release else (v.description or "Article")
            ),
            quantity=Decimal("1"),
            unit_price=_preu_net_unitari(v.sale_price, Decimal("1"), v.vat_amount, v.vat_pct),
            vat_pct=v.vat_pct or VAT_PCT_DEFAULT,
        )
        for i, v in enumerate(ventes)
    ]
    base_total, vat_total, total = _totals(lines)

    factura = Factura(
        fiscal_year=date.today().year, number=next_document_number(db, "factura", date.today().year),
        origen=FacturaOrigen.ticket, status=FacturaStatus.emesa, venta_externa_ticket_id=ticket_id,
        user_id=primera.user_id, client_name=client_name, client_nif=client_nif,
        base_total=base_total, vat_total=vat_total, total=total, lines=lines,
    )
    db.add(factura)
    db.commit()
    return _factura_out(_get_factura_or_404(db, factura.id))


@router.get("/factures", response_model=list[FacturaOut])
def llistar_factures(status: str | None = None, db: Session = Depends(get_db)):
    query = select(Factura).options(selectinload(Factura.lines)).order_by(Factura.created_at.desc())
    if status:
        query = query.where(Factura.status == status)
    return [_factura_out(f) for f in db.scalars(query)]


@router.get("/factures/{factura_id}", response_model=FacturaOut)
def obtenir_factura(factura_id: uuid.UUID, db: Session = Depends(get_db)):
    return _factura_out(_get_factura_or_404(db, factura_id))


@router.get("/factures/{factura_id}/pdf")
def factura_pdf(factura_id: uuid.UUID, db: Session = Depends(get_db)):
    factura = _get_factura_or_404(db, factura_id)
    pdf_bytes = generate_factura_pdf(factura, db)
    filename = f"factura_{factura.fiscal_year}_{factura.number:04d}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/factures/{factura_id}/anullar", response_model=FacturaOut)
def anullar_factura(factura_id: uuid.UUID, db: Session = Depends(get_db)):
    """Anul·la la factura sense reutilitzar mai el número (mateix criteri
    legal que una rectificativa simplificada). Si era una factura manual,
    reverteix el seu assentament — una de tipus 'ticket' no en té cap de
    propi (ver docstring dels endpoints de creació)."""
    factura = _get_factura_or_404(db, factura_id)
    if factura.status == FacturaStatus.anullada:
        raise HTTPException(409, "Aquesta factura ja està anul·lada")
    if factura.origen == FacturaOrigen.manual:
        unpost_source(db, JournalSourceType.factura_manual, factura.id)
    factura.status = FacturaStatus.anullada
    db.commit()
    return _factura_out(_get_factura_or_404(db, factura.id))
