import io
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ...database import get_db
from ...models import (
    CajaMovimiento, CajaSession, Comanda, Compra, DevolucionCompra, EstadoComanda, Item,
    Proveedor, Release, TipoCompra, TipoMovimiento,
)
from ...schemas import (
    CompraItemOut, CompraOut, CompraParticularIn, ComprasStatsMesOut, ComprasStatsOut,
    ComprasStatsProveedorOut,
)
from ...services.recepcio_pdf import generate_recepcio_pdf
from ...services.security import require_admin

router = APIRouter(prefix="/admin", tags=["erp"], dependencies=[Depends(require_admin)])


def _registrar_sortida_caixa(db: Session, concept: str, amount: Decimal, date: datetime) -> None:
    """Best-effort: si hi ha una sessió de caixa oberta, hi apunta la despesa."""
    sesion = db.scalar(
        select(CajaSession).where(CajaSession.closed_at.is_(None))
        .order_by(CajaSession.opened_at.desc())
    )
    if sesion:
        db.add(CajaMovimiento(
            session_id=sesion.id, type=TipoMovimiento.salida,
            concept=concept, amount=amount, date=date,
        ))


@router.post("/compras/particular", status_code=201)
def create_compra_particular(payload: CompraParticularIn, db: Session = Depends(get_db)):
    """Compra ràpida a un particular que ve a la botiga: neix entregada (stock
    disponible a l'instant) i s'apunta com a sortida de caixa si hi ha sessió oberta."""
    for line in payload.items:
        if db.get(Release, line.release_id) is None:
            raise HTTPException(404, f"Release {line.release_id} no encontrado")

    total_coste = sum((line.acquisition_cost for line in payload.items), Decimal("0"))
    compra = Compra(
        type=TipoCompra.particular,
        individual_name=payload.individual_name,
        user_id=payload.user_id,
        date=payload.date,
        notes=payload.notes,
        total_cost=total_coste,
    )
    db.add(compra)
    db.flush()

    for line in payload.items:
        db.add(Item(
            release_id=line.release_id, price=line.price, condition=line.condition,
            acquisition_cost=line.acquisition_cost, estado_disco=line.estado_disco,
            estado_funda=line.estado_funda, compra_id=compra.id,
            entry_date=compra.date,
        ))

    if total_coste > 0:
        nombre = payload.individual_name or "particular"
        _registrar_sortida_caixa(db, f"Compra a particular: {nombre}", total_coste, payload.date)

    db.commit()
    return {"id": str(compra.id), "items_creados": len(payload.items)}


@router.get("/compras", response_model=list[CompraOut])
def list_compras(
    tipo: str | None = None,
    proveedor_id: uuid.UUID | None = None,
    sense_facturar: bool = False,
    q: str | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    db: Session = Depends(get_db),
):
    stmt = (
        select(Compra)
        .options(
            selectinload(Compra.items).selectinload(Item.release),
            selectinload(Compra.client),
            selectinload(Compra.proveedor),
            selectinload(Compra.despesa),
        )
        .order_by(Compra.date.desc())
    )
    if tipo:
        stmt = stmt.where(Compra.type == tipo)
    if proveedor_id:
        stmt = stmt.where(Compra.proveedor_id == proveedor_id)
    if sense_facturar:
        stmt = stmt.where(Compra.despesa_id.is_(None))
    if desde:
        stmt = stmt.where(Compra.date >= desde)
    if hasta:
        stmt = stmt.where(Compra.date <= hasta)
    compras = db.scalars(stmt).all()

    if q:
        ql = q.lower()
        compras = [
            c for c in compras
            if (c.individual_name and ql in c.individual_name.lower())
            or (c.client and c.client.name and ql in c.client.name.lower())
            or (c.delivery_note_number and ql in c.delivery_note_number.lower())
            or (c.proveedor and ql in c.proveedor.name.lower())
        ]

    all_item_ids = [it.id for c in compras for it in c.items]
    returned = set(db.scalars(
        select(DevolucionCompra.item_id).where(DevolucionCompra.item_id.in_(all_item_ids))
    ).all())
    return [_compra_out(c, returned) for c in compras]


@router.get("/compras/stats", response_model=ComprasStatsOut)
def compras_stats(db: Session = Depends(get_db)):
    """Resum per al dashboard de compres: despesa per període, pendents de
    rebre/facturar i evolució mensual (últims 12 mesos)."""
    now = datetime.now(timezone.utc)
    inici_any = datetime(now.year, 1, 1, tzinfo=timezone.utc)
    inici_mes = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    inici_trimestre = datetime(now.year, 3 * ((now.month - 1) // 3) + 1, 1, tzinfo=timezone.utc)
    mes_index = (now.year * 12 + (now.month - 1)) - 11
    fa_12_mesos = datetime(mes_index // 12, mes_index % 12 + 1, 1, tzinfo=timezone.utc)

    # Compra.total_cost (fijado al crear la recepción) es la fuente fiable:
    # sumar Item.acquisition_cost vía Item.compra_id ya no basta desde que
    # una línea nou puede acumular varias recepciones en la misma fila
    # (que solo apunta a la compra_id de la última).
    rows = db.execute(
        select(
            Compra.id, Compra.type, Compra.proveedor_id, Compra.date, Compra.despesa_id,
            Proveedor.name, func.coalesce(Compra.total_cost, 0),
        )
        .select_from(Compra)
        .outerjoin(Proveedor, Proveedor.id == Compra.proveedor_id)
        .where(Compra.date >= fa_12_mesos)
    ).all()

    total_mes = total_trimestre = total_any = Decimal("0")
    total_mes_proveidor = total_mes_particular = Decimal("0")
    sense_facturar_count = 0
    sense_facturar_import = Decimal("0")
    per_proveidor: dict[uuid.UUID, dict] = {}
    per_mes: dict[str, dict] = {}

    for _id, tipo, proveedor_id, fecha, despesa_id, prov_nombre, total in rows:
        total = Decimal(total)
        if fecha.tzinfo is None:  # SQLite (tests) no conserva la timezone
            fecha = fecha.replace(tzinfo=timezone.utc)
        if fecha >= inici_any:
            total_any += total
        if fecha >= inici_trimestre:
            total_trimestre += total
        if fecha >= inici_mes:
            total_mes += total
            if tipo == TipoCompra.proveedor:
                total_mes_proveidor += total
            else:
                total_mes_particular += total

        if tipo == TipoCompra.proveedor and despesa_id is None and total > 0:
            sense_facturar_count += 1
            sense_facturar_import += total

        if tipo == TipoCompra.proveedor and proveedor_id is not None:
            entry = per_proveidor.setdefault(proveedor_id, {"nombre": prov_nombre, "total": Decimal("0")})
            entry["total"] += total

        mes_key = fecha.strftime("%Y-%m")
        mes_entry = per_mes.setdefault(mes_key, {"proveidor": Decimal("0"), "particular": Decimal("0")})
        if tipo == TipoCompra.proveedor:
            mes_entry["proveidor"] += total
        else:
            mes_entry["particular"] += total

    top_proveidors = [
        ComprasStatsProveedorOut(proveedor_id=pid, nombre=v["nombre"], total=v["total"])
        for pid, v in sorted(per_proveidor.items(), key=lambda kv: kv[1]["total"], reverse=True)[:5]
    ]

    serie_mensual = []
    cursor = fa_12_mesos
    for _ in range(12):
        key = cursor.strftime("%Y-%m")
        entry = per_mes.get(key, {"proveidor": Decimal("0"), "particular": Decimal("0")})
        serie_mensual.append(ComprasStatsMesOut(
            mes=key, proveidor=entry["proveidor"], particular=entry["particular"],
        ))
        cursor = datetime(cursor.year + (1 if cursor.month == 12 else 0), 1 if cursor.month == 12 else cursor.month + 1, 1, tzinfo=timezone.utc)

    comandes_pendents = db.scalar(
        select(func.count()).select_from(Comanda).where(
            Comanda.status.in_([EstadoComanda.esborrany, EstadoComanda.enviada, EstadoComanda.rebuda_parcial])
        )
    ) or 0

    return ComprasStatsOut(
        total_mes=total_mes, total_trimestre=total_trimestre, total_any=total_any,
        total_mes_proveidor=total_mes_proveidor, total_mes_particular=total_mes_particular,
        comandes_pendents=comandes_pendents,
        sense_facturar_count=sense_facturar_count, sense_facturar_import=sense_facturar_import,
        top_proveidors=top_proveidors, serie_mensual=serie_mensual,
    )


@router.get("/compras/{compra_id}", response_model=CompraOut)
def get_compra(compra_id: uuid.UUID, db: Session = Depends(get_db)):
    stmt = (
        select(Compra)
        .where(Compra.id == compra_id)
        .options(
            selectinload(Compra.items).selectinload(Item.release),
            selectinload(Compra.client),
            selectinload(Compra.despesa),
        )
    )
    compra = db.scalar(stmt)
    if compra is None:
        raise HTTPException(404, "Compra no encontrada")
    returned = set(db.scalars(
        select(DevolucionCompra.item_id).where(
            DevolucionCompra.item_id.in_([it.id for it in compra.items])
        )
    ).all())
    return _compra_out(compra, returned)


@router.get("/compras/{compra_id}/pdf")
def compra_pdf(compra_id: uuid.UUID, db: Session = Depends(get_db)):
    """Llista de recepció (preu de venda real fixat en registrar l'entrada),
    per imprimir i escriure a mà les etiquetes de preu dels exemplars."""
    compra = db.scalar(
        select(Compra)
        .where(Compra.id == compra_id)
        .options(
            selectinload(Compra.items).selectinload(Item.release),
            selectinload(Compra.proveedor),
        )
    )
    if compra is None:
        raise HTTPException(404, "Compra no encontrada")
    pdf_bytes = generate_recepcio_pdf(compra, db)
    filename = f"recepcio_{compra.delivery_note_number or compra.id}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _compra_out(compra: Compra, returned_item_ids: set | None = None) -> dict:
    returned_item_ids = returned_item_ids or set()
    return {
        "id": compra.id,
        "type": compra.type,
        "proveedor_id": compra.proveedor_id,
        "individual_name": compra.individual_name,
        "user_id": compra.user_id,
        "user_nom": compra.client.name if compra.client else None,
        "date": compra.date,
        "delivery_note_number": compra.delivery_note_number,
        "notes": compra.notes,
        "comanda_id": compra.comanda_id,
        "despesa_id": compra.despesa_id,
        "despesa_estat": compra.despesa.payment_status if compra.despesa else None,
        "created_at": compra.created_at,
        "items": [
            CompraItemOut(
                item_id=it.id,
                release_id=it.release_id,
                artista=it.release.artista,
                title=it.release.title,
                price=it.price,
                acquisition_cost=it.acquisition_cost,
                item_status=it.status,
                devuelto=it.id in returned_item_ids,
            )
            for it in compra.items
        ],
    }
