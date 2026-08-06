"""Router de comptabilitat: despeses, comptes bancaris, conciliació, informes i periodes."""

import calendar
import io
import uuid
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy import extract, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import (
    CaixaDiaria, CategoriaDespesa, CompteBancari, Compra, Despesa, EstatConciliacio,
    EstatPagamentDespesa, Item, MetodoPago, MovimentBancari, Order, OrderItem, OrderStatus,
    PeriodeComptable, Proveedor, TipusIva, VentaExterna, CanalVenta,
)
from ..schemas import (
    CAIXA_DIARIA_CAMPS, CaixaDiariaLiniaIn, CaixaDiariaLiniaOut, CaixaDiariaMesOut,
    CompteBancariIn, CompteBancariOut, ConciliarMovimentIn,
    DespesaDesDeComprasIn, DespesaIn, DespesaOut, DespesaUpdate,
    IVALiniaOut, IVATrimestralOut,
    MovimentBancariOut,
    PeriodeComptableOut,
    ProveedorIn, ProveedorOut,
    ResultatLiniaDespesa, ResultatMensualOut,
    VendesRealsLiniaOut,
)
from ..services.caixa_diaria_export import generate_caixa_diaria_excel, generate_caixa_diaria_pdf
from ..services.n43 import parse_csv_generic, parse_n43
from ..services.security import require_admin

router = APIRouter(prefix="/admin", tags=["comptabilitat"], dependencies=[Depends(require_admin)])


# ---------------------------------------------------------------------------
# Proveïdors (PATCH + GET individual — CREATE ja és a erp.py)
# ---------------------------------------------------------------------------

@router.patch("/proveedores/{prov_id}", response_model=ProveedorOut)
def update_proveidor(prov_id: uuid.UUID, payload: ProveedorIn, db: Session = Depends(get_db)):
    prov = db.get(Proveedor, prov_id)
    if prov is None:
        raise HTTPException(404, "Proveïdor no trobat")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(prov, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"Ja existeix un proveïdor amb el nom '{payload.nombre}'")
    db.refresh(prov)
    return prov


@router.get("/proveedores/{prov_id}", response_model=ProveedorOut)
def get_proveidor(prov_id: uuid.UUID, db: Session = Depends(get_db)):
    prov = db.get(Proveedor, prov_id)
    if prov is None:
        raise HTTPException(404, "Proveïdor no trobat")
    return prov


# ---------------------------------------------------------------------------
# Despeses
# ---------------------------------------------------------------------------

def _calc_venciment(data_factura: date, prov: Proveedor | None) -> date | None:
    if prov is None or prov.dies_pagament is None:
        return None
    due = data_factura + timedelta(days=prov.dies_pagament)
    if prov.dia_pagament_mes:
        # Avança al dia fix del mes: si el dia ja ha passat, va al mes següent
        d = prov.dia_pagament_mes
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
        "id": d.id, "num_factura": d.num_factura, "data_factura": d.data_factura,
        "data_venciment": d.data_venciment, "proveidor_id": d.proveidor_id,
        "proveidor_nom": d.proveidor_nom, "categoria": d.categoria, "concepte": d.concepte,
        "base_imposable": d.base_imposable, "tipus_iva_id": d.tipus_iva_id, "iva_pct": d.iva_pct,
        "iva_import": d.iva_import, "total": d.total, "estat_pagament": d.estat_pagament,
        "data_pagament": d.data_pagament, "metode_pagament": d.metode_pagament,
        "compra_ids": [c.id for c in d.compras], "notes": d.notes, "created_at": d.created_at,
    }


@router.post("/despeses", status_code=201, response_model=DespesaOut)
def create_despesa(payload: DespesaIn, db: Session = Depends(get_db)):
    prov = db.get(Proveedor, payload.proveidor_id) if payload.proveidor_id else None

    # Si es tria un tipus d'IVA del catàleg, el seu percentatge mana sobre el iva_pct enviat.
    iva_pct = payload.iva_pct
    if payload.tipus_iva_id is not None:
        tipus = db.get(TipusIva, payload.tipus_iva_id)
        if tipus is None:
            raise HTTPException(404, "Tipus d'IVA no trobat")
        iva_pct = tipus.percentatge

    iva_import = (payload.base_imposable * iva_pct / 100).quantize(Decimal("0.01"))
    total = payload.total if payload.total is not None else payload.base_imposable + iva_import

    data_venciment = payload.data_venciment or _calc_venciment(payload.data_factura, prov)

    despesa = Despesa(
        num_factura=payload.num_factura,
        data_factura=payload.data_factura,
        data_venciment=data_venciment,
        proveidor_id=payload.proveidor_id,
        proveidor_nom=payload.proveidor_nom,
        categoria=CategoriaDespesa(payload.categoria),
        concepte=payload.concepte,
        base_imposable=payload.base_imposable,
        tipus_iva_id=payload.tipus_iva_id,
        iva_pct=iva_pct,
        iva_import=iva_import,
        total=total,
        estat_pagament=EstatPagamentDespesa(payload.estat_pagament),
        data_pagament=payload.data_pagament,
        metode_pagament=payload.metode_pagament,
        notes=payload.notes,
    )
    db.add(despesa)
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
    stmt = select(Despesa).options(selectinload(Despesa.compras)).order_by(Despesa.data_factura.desc())
    if categoria:
        stmt = stmt.where(Despesa.categoria == categoria)
    if estat:
        stmt = stmt.where(Despesa.estat_pagament == estat)
    if proveidor_id:
        stmt = stmt.where(Despesa.proveidor_id == proveidor_id)
    if des_de:
        stmt = stmt.where(Despesa.data_factura >= des_de)
    if fins_a:
        stmt = stmt.where(Despesa.data_factura <= fins_a)
    return [_despesa_out(d) for d in db.scalars(stmt).all()]


@router.get("/despeses/pendents", response_model=list[DespesaOut])
def list_despeses_pendents(db: Session = Depends(get_db)):
    """Factures pendents de pagament ordenades per data de venciment (vençudes primer)."""
    today = date.today()
    # Actualitza vençudes automàticament
    db.execute(
        update(Despesa)
        .where(Despesa.estat_pagament == EstatPagamentDespesa.pendent)
        .where(Despesa.data_venciment < today)
        .values(estat_pagament=EstatPagamentDespesa.vencut)
        .execution_options(synchronize_session=False)
    )
    db.commit()
    despeses = db.scalars(
        select(Despesa)
        .options(selectinload(Despesa.compras))
        .where(Despesa.estat_pagament.in_([EstatPagamentDespesa.pendent, EstatPagamentDespesa.vencut]))
        .order_by(Despesa.data_venciment.asc().nullslast())
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


@router.patch("/despeses/{despesa_id}", response_model=DespesaOut)
def update_despesa(despesa_id: uuid.UUID, payload: DespesaUpdate, db: Session = Depends(get_db)):
    d = db.scalar(
        select(Despesa).options(selectinload(Despesa.compras)).where(Despesa.id == despesa_id)
    )
    if d is None:
        raise HTTPException(404, "Despesa no trobada")
    data = payload.model_dump(exclude_unset=True)
    # Si es canvia el tipus d'IVA, el seu percentatge mana sobre iva_pct
    if "tipus_iva_id" in data and data["tipus_iva_id"] is not None:
        tipus = db.get(TipusIva, data["tipus_iva_id"])
        if tipus is None:
            raise HTTPException(404, "Tipus d'IVA no trobat")
        data.setdefault("iva_pct", tipus.percentatge)
    # Recalcula iva_import si canvia base, iva_pct o tipus_iva_id
    if "base_imposable" in data or "iva_pct" in data or "tipus_iva_id" in data:
        base = data.get("base_imposable", d.base_imposable)
        pct = data.get("iva_pct", d.iva_pct)
        data.setdefault("iva_import", (base * pct / 100).quantize(Decimal("0.01")))
        data.setdefault("total", base + data["iva_import"])
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
    if d.estat_pagament == EstatPagamentDespesa.pagat:
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
        if c.tipo != "proveedor":
            raise HTTPException(422, "Només es poden facturar recepcions de proveïdor")
        if c.despesa_id is not None:
            raise HTTPException(409, f"La recepció del {c.fecha.date()} ja té una factura associada")
    proveidor_ids = {c.proveedor_id for c in compres}
    if len(proveidor_ids) > 1:
        raise HTTPException(422, "Totes les recepcions han de ser del mateix proveïdor")

    prov = compres[0].proveedor
    prov_nom = prov.nombre if prov else "Proveïdor"
    # `Compra.coste_total` es la fuente fiable desde que una línea nou puede
    # acumular varias recepciones en la misma fila Item (que solo puede
    # apuntar a una compra_id, la última) — sumar item.coste_adquisicion vía
    # Compra.items ya no reflejaría el coste real de recepciones anteriores.
    # Fallback al cálculo antiguo solo para compras previas a este campo.
    total_cost = sum(
        c.coste_total if c.coste_total is not None
        else sum((it.coste_adquisicion or Decimal("0")) for it in c.items)
        for c in compres
    )
    total_items = sum(len(c.items) for c in compres)

    tipus = db.get(TipusIva, payload.tipus_iva_id) if payload.tipus_iva_id else db.scalar(
        select(TipusIva).where(TipusIva.actiu == True, TipusIva.es_rebu == False)
        .order_by(TipusIva.percentatge.desc())
    )
    pct = tipus.percentatge if tipus else Decimal("21.00")
    base = (total_cost / (1 + pct / 100)).quantize(Decimal("0.01"))
    iva = total_cost - base

    data_factura = payload.data_factura or date.today()
    data_venciment = _calc_venciment(data_factura, prov)

    despesa = Despesa(
        num_factura=payload.num_factura,
        data_factura=data_factura,
        data_venciment=data_venciment,
        proveidor_id=prov.id if prov else None,
        proveidor_nom=prov_nom,
        tipus_iva_id=tipus.id if tipus else None,
        categoria=CategoriaDespesa.compres_material,
        concepte=f"Compra discos ({len(compres)} recepcions, {total_items} exemplars)",
        base_imposable=base,
        iva_pct=pct,
        iva_import=iva,
        total=total_cost,
        estat_pagament=EstatPagamentDespesa.pendent,
        notes=payload.notes,
    )
    db.add(despesa)
    db.flush()
    for c in compres:
        c.despesa_id = despesa.id
    db.commit()
    db.refresh(despesa)
    return _despesa_out(despesa)


# ---------------------------------------------------------------------------
# Comptes bancaris
# ---------------------------------------------------------------------------

@router.post("/comptes", status_code=201, response_model=CompteBancariOut)
def create_compte(payload: CompteBancariIn, db: Session = Depends(get_db)):
    compte = CompteBancari(**payload.model_dump())
    db.add(compte)
    db.commit()
    db.refresh(compte)
    return compte


@router.get("/comptes", response_model=list[CompteBancariOut])
def list_comptes(db: Session = Depends(get_db)):
    return db.scalars(select(CompteBancari).where(CompteBancari.actiu == True).order_by(CompteBancari.id)).all()


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


# ---------------------------------------------------------------------------
# Moviments bancaris — import N43/CSV
# ---------------------------------------------------------------------------

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
        .where(MovimentBancari.data_operacio >= moviments[0].data_operacio)
    ).all()
    existents_key = {(m.data_operacio, m.concepte[:30], m.import_moviment) for m in existents}

    nous = 0
    for m in moviments:
        key = (m.data_operacio, m.concepte[:30], m.import_moviment)
        if key in existents_key:
            continue
        db.add(MovimentBancari(
            compte_id=compte_id,
            data_operacio=m.data_operacio,
            data_valor=m.data_valor,
            concepte=m.concepte,
            import_moviment=m.import_moviment,
            saldo=m.saldo,
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
        .order_by(MovimentBancari.data_operacio.desc())
    )
    if estat:
        stmt = stmt.where(MovimentBancari.estat == estat)
    if des_de:
        stmt = stmt.where(MovimentBancari.data_operacio >= des_de)
    if fins_a:
        stmt = stmt.where(MovimentBancari.data_operacio <= fins_a)

    movs = db.scalars(stmt).all()
    return [
        MovimentBancariOut(
            **{c: getattr(m, c) for c in MovimentBancariOut.model_fields if hasattr(m, c)},
            despesa_concepte=m.despesa.concepte if m.despesa else None,
            despesa_proveidor=m.despesa.proveidor_nom if m.despesa else None,
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
    if mov.estat == EstatConciliacio.conciliat:
        raise HTTPException(409, "El moviment ja està conciliat")

    mov.estat = EstatConciliacio(payload.estat)
    mov.despesa_id = payload.despesa_id
    mov.order_id = payload.order_id
    mov.venta_externa_id = payload.venta_externa_id
    mov.notes_conciliacio = payload.notes_conciliacio

    # Si conciliem amb una despesa, la marquem com a pagada
    if payload.estat == "conciliat" and payload.despesa_id:
        despesa = db.get(Despesa, payload.despesa_id)
        if despesa and despesa.estat_pagament != EstatPagamentDespesa.pagat:
            despesa.estat_pagament = EstatPagamentDespesa.pagat
            despesa.data_pagament = mov.data_operacio

    # Si conciliem amb una venda externa, la marquem com a cobrada
    if payload.estat == "conciliat" and payload.venta_externa_id:
        venta = db.get(VentaExterna, payload.venta_externa_id)
        if venta and venta.cobrat_at is None:
            venta.cobrat_at = datetime.combine(mov.data_operacio, datetime.min.time()).replace(tzinfo=timezone.utc)

    # Si conciliem amb un order, el marquem com a cobrat
    if payload.estat == "conciliat" and payload.order_id:
        order = db.get(Order, payload.order_id)
        if order and order.cobrat_at is None:
            order.cobrat_at = datetime.combine(mov.data_operacio, datetime.min.time()).replace(tzinfo=timezone.utc)

    db.commit()
    db.refresh(mov)
    return MovimentBancariOut(
        **{c: getattr(mov, c) for c in MovimentBancariOut.model_fields if hasattr(mov, c)},
        despesa_concepte=mov.despesa.concepte if mov.despesa else None,
        despesa_proveidor=mov.despesa.proveidor_nom if mov.despesa else None,
    )


# ---------------------------------------------------------------------------
# Informe: Resultat mensual
# ---------------------------------------------------------------------------

@router.get("/resultat/{year}/{mes}", response_model=ResultatMensualOut)
def resultat_mensual(year: int, mes: int, db: Session = Depends(get_db)):
    if not (1 <= mes <= 12):
        raise HTTPException(422, "Mes ha de ser entre 1 i 12")

    # Periode
    periode = db.scalar(
        select(PeriodeComptable).where(PeriodeComptable.year == year, PeriodeComptable.mes == mes)
    )
    tancat = periode.tancat if periode else False

    def _mes_filter(col):
        return (extract("year", col) == year) & (extract("month", col) == mes)

    # Vendes web (orders pagades/enviades/entregades)
    vendes_web_rows = db.execute(
        select(func.sum(OrderItem.precio))
        .join(Order, Order.id == OrderItem.order_id)
        .where(_mes_filter(Order.created_at))
        .where(Order.status.in_([OrderStatus.pagado, OrderStatus.enviado, OrderStatus.entregado]))
    ).scalar() or Decimal("0")

    # Vendes TPV mostrador
    vendes_mostrador = db.execute(
        select(func.sum(VentaExterna.precio_venta))
        .where(_mes_filter(VentaExterna.fecha))
        .where(VentaExterna.canal == CanalVenta.mostrador)
    ).scalar() or Decimal("0")

    # Vendes Discogs
    vendes_discogs = db.execute(
        select(func.sum(VentaExterna.precio_venta))
        .where(_mes_filter(VentaExterna.fecha))
        .where(VentaExterna.canal == CanalVenta.discogs)
    ).scalar() or Decimal("0")

    total_ingressos = vendes_web_rows + vendes_mostrador + vendes_discogs

    # COGS web: cost dels items venuts via web aquell mes
    cogs_web_row = db.execute(
        select(
            # coste_adquisicion es por unidad: para nou, una OrderItem puede
            # vender más de 1 unidad de la misma línea de golpe.
            func.coalesce(func.sum(Item.coste_adquisicion * OrderItem.cantidad), Decimal("0")),
            func.count(Item.id).filter(Item.coste_adquisicion.is_(None)),
        )
        .join(OrderItem, OrderItem.item_id == Item.id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(_mes_filter(Order.created_at))
        .where(Order.status.in_([OrderStatus.pagado, OrderStatus.enviado, OrderStatus.entregado]))
    ).one()
    cogs_web = cogs_web_row[0] or Decimal("0")
    sense_cost_web = cogs_web_row[1] or 0

    # COGS extern: cost dels items venuts via TPV/Discogs aquell mes
    cogs_extern_row = db.execute(
        select(
            func.coalesce(func.sum(Item.coste_adquisicion * VentaExterna.cantidad), Decimal("0")),
            func.count(Item.id).filter(Item.coste_adquisicion.is_(None)),
        )
        .join(VentaExterna, VentaExterna.item_id == Item.id)
        .where(_mes_filter(VentaExterna.fecha))
    ).one()
    cogs_extern = cogs_extern_row[0] or Decimal("0")
    sense_cost_extern = cogs_extern_row[1] or 0

    total_cogs = cogs_web + cogs_extern
    items_sense_cost = sense_cost_web + sense_cost_extern
    marge_brut = total_ingressos - total_cogs

    # Despeses del mes per categoria (totes, per compatibilitat i IVA)
    despeses_rows = db.execute(
        select(Despesa.categoria, func.sum(Despesa.total), func.count(Despesa.id))
        .where(_mes_filter(Despesa.data_factura))
        .group_by(Despesa.categoria)
        .order_by(Despesa.categoria)
    ).all()

    despeses_out = [
        ResultatLiniaDespesa(categoria=r[0], total=r[1], num_factures=r[2])
        for r in despeses_rows
    ]
    total_despeses = sum(d.total for d in despeses_out)

    # Despeses operatives: exclou compres_material (ja reflectit al COGS per-venda)
    total_despeses_operatives = sum(
        d.total for d in despeses_out if d.categoria != "compres_material"
    )

    return ResultatMensualOut(
        year=year,
        mes=mes,
        periode_tancat=tancat,
        vendes_web=Decimal(vendes_web_rows),
        vendes_mostrador=Decimal(vendes_mostrador),
        vendes_discogs=Decimal(vendes_discogs),
        total_ingressos=total_ingressos,
        cogs_web=cogs_web,
        cogs_extern=cogs_extern,
        total_cogs=total_cogs,
        items_sense_cost=items_sense_cost,
        marge_brut=marge_brut,
        despeses=despeses_out,
        total_despeses_operatives=total_despeses_operatives,
        total_despeses=total_despeses,
        resultat=marge_brut - total_despeses_operatives,
    )


# ---------------------------------------------------------------------------
# Informe: IVA trimestral
# ---------------------------------------------------------------------------

@router.get("/iva/{year}/{trimestre}", response_model=IVATrimestralOut)
def iva_trimestral(year: int, trimestre: int, db: Session = Depends(get_db)):
    if not (1 <= trimestre <= 4):
        raise HTTPException(422, "Trimestre ha de ser entre 1 i 4")

    mesos = [(trimestre - 1) * 3 + i for i in range(1, 4)]  # [1,2,3], [4,5,6]...

    def _in_trimestre(col):
        return (extract("year", col) == year) & (extract("month", col).in_(mesos))

    # IVA suportat (despeses)
    suportat_rows = db.execute(
        select(Despesa.categoria, Despesa.iva_pct, func.sum(Despesa.base_imposable), func.sum(Despesa.iva_import))
        .where(_in_trimestre(Despesa.data_factura))
        .group_by(Despesa.categoria, Despesa.iva_pct)
        .order_by(Despesa.categoria)
    ).all()

    iva_suportat = [
        IVALiniaOut(categoria=r[0], iva_pct=r[1], base=r[2], iva_import=r[3])
        for r in suportat_rows
    ]

    # IVA repercutit (vendes). Cada línia ja porta el seu iva_pct/iva_import desat
    # en el moment de la venda (règim general sobre preu, o REBU sobre el marge).
    # Per a vendes anteriors a aquesta funcionalitat (iva_import NULL) s'assumeix
    # el tipus general (21%) sobre el preu, igual que feia l'informe abans.
    web_rows = db.execute(
        select(OrderItem.iva_pct, OrderItem.precio, OrderItem.iva_import)
        .join(Order, Order.id == OrderItem.order_id)
        .where(_in_trimestre(Order.created_at))
        .where(Order.status.in_([OrderStatus.pagado, OrderStatus.enviado, OrderStatus.entregado]))
    ).all()

    canal_labels = {"mostrador": "vendes_mostrador", "discogs": "vendes_discogs", "otro": "vendes_altres"}
    ve_rows = db.execute(
        select(VentaExterna.canal, VentaExterna.iva_pct, VentaExterna.precio_venta, VentaExterna.iva_import)
        .where(_in_trimestre(VentaExterna.fecha))
    ).all()

    hay_rebu = db.execute(
        select(func.count())
        .select_from(VentaExterna)
        .join(Item, Item.id == VentaExterna.item_id)
        .where(_in_trimestre(VentaExterna.fecha))
        .where(Item.rebu == True)
    ).scalar() > 0

    def _agregar(label_pct_precio_iva: list[tuple[str, Decimal | None, Decimal, Decimal | None]]) -> list[IVALiniaOut]:
        buckets: dict[tuple[str, Decimal], list[Decimal]] = {}
        for label, pct, precio, iva_import in label_pct_precio_iva:
            pct_efectiu = pct if pct is not None else Decimal("21.00")
            if iva_import is None:
                iva_import = (precio * pct_efectiu / (Decimal("100") + pct_efectiu)).quantize(Decimal("0.01"))
            key = (label, pct_efectiu)
            acc = buckets.setdefault(key, [Decimal("0"), Decimal("0")])
            acc[0] += precio - iva_import
            acc[1] += iva_import
        return [
            IVALiniaOut(categoria=k[0], iva_pct=k[1], base=v[0], iva_import=v[1])
            for k, v in buckets.items()
        ]

    repercutit_rows = [("vendes_web", pct, precio, iva) for pct, precio, iva in web_rows]
    repercutit_rows += [
        (canal_labels.get(canal, canal), pct, precio, iva) for canal, pct, precio, iva in ve_rows
    ]
    iva_repercutit = _agregar(repercutit_rows)

    total_base_suportat = sum(r.base for r in iva_suportat)
    total_iva_suportat = sum(r.iva_import for r in iva_suportat)
    total_base_repercutit = sum(r.base for r in iva_repercutit)
    total_iva_repercutit = sum(r.iva_import for r in iva_repercutit)

    return IVATrimestralOut(
        year=year,
        trimestre=trimestre,
        mesos=mesos,
        iva_suportat=iva_suportat,
        total_base_suportat=total_base_suportat,
        total_iva_suportat=total_iva_suportat,
        iva_repercutit=iva_repercutit,
        total_base_repercutit=total_base_repercutit,
        total_iva_repercutit=total_iva_repercutit,
        resultat_iva=total_iva_repercutit - total_iva_suportat,
        nota_rebu=hay_rebu,
    )


# ---------------------------------------------------------------------------
# Informe: Valor d'estoc
# ---------------------------------------------------------------------------

@router.get("/stock/valor")
def stock_valor(db: Session = Depends(get_db)):
    """Valor actual de l'estoc a preu de cost, desglossat per estat i condició."""
    from ..models import ItemStatus, CondicionItem

    rows = db.execute(
        select(
            Item.status,
            Item.condicion,
            # Para nou, una fila representa `cantidad` unidades físicas: hay
            # que ponderar por cantidad para reflejar el valor real de estoc,
            # no el de una sola unidad por línea.
            func.coalesce(func.sum(Item.cantidad), 0).label("num_items"),
            func.coalesce(func.sum(Item.coste_adquisicion * Item.cantidad), Decimal("0")).label("valor_cost"),
            func.coalesce(func.sum(Item.precio * Item.cantidad), Decimal("0")).label("valor_pvp"),
            func.count(Item.id).filter(Item.coste_adquisicion.is_(None)).label("sense_cost"),
        )
        .where(Item.status.in_([ItemStatus.disponible, ItemStatus.reservado]))
        .group_by(Item.status, Item.condicion)
        .order_by(Item.status, Item.condicion)
    ).all()

    total_items = sum(r.num_items for r in rows)
    total_valor_cost = sum(r.valor_cost for r in rows)
    total_valor_pvp = sum(r.valor_pvp for r in rows)
    total_sense_cost = sum(r.sense_cost for r in rows)

    return {
        "total_items": total_items,
        "total_valor_cost": total_valor_cost,
        "total_valor_pvp": total_valor_pvp,
        "marge_potencial": total_valor_pvp - total_valor_cost,
        "items_sense_cost": total_sense_cost,
        "detall": [
            {
                "status": r.status,
                "condicion": r.condicion,
                "num_items": r.num_items,
                "valor_cost": r.valor_cost,
                "valor_pvp": r.valor_pvp,
                "sense_cost": r.sense_cost,
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# Periodes comptables
# ---------------------------------------------------------------------------

@router.get("/periodes", response_model=list[PeriodeComptableOut])
def list_periodes(db: Session = Depends(get_db)):
    return db.scalars(
        select(PeriodeComptable).order_by(PeriodeComptable.year.desc(), PeriodeComptable.mes.desc())
    ).all()


def _get_or_create_periode(year: int, mes: int, db: Session) -> PeriodeComptable:
    periode = db.scalar(
        select(PeriodeComptable).where(PeriodeComptable.year == year, PeriodeComptable.mes == mes)
    )
    if periode is None:
        periode = PeriodeComptable(year=year, mes=mes)
        db.add(periode)
        db.flush()
    return periode


@router.post("/periodes/{year}/{mes}/tancar", response_model=PeriodeComptableOut)
def tancar_periode(year: int, mes: int, db: Session = Depends(get_db)):
    p = _get_or_create_periode(year, mes, db)
    if p.tancat:
        raise HTTPException(409, "El mes ja estava tancat")
    p.tancat = True
    p.data_tancament = datetime.now(timezone.utc)
    db.commit()
    db.refresh(p)
    return p


@router.post("/periodes/{year}/{mes}/obrir", response_model=PeriodeComptableOut)
def obrir_periode(year: int, mes: int, db: Session = Depends(get_db)):
    p = _get_or_create_periode(year, mes, db)
    p.tancat = False
    p.data_tancament = None
    db.commit()
    db.refresh(p)
    return p


@router.patch("/periodes/{year}/{mes}/notes", response_model=PeriodeComptableOut)
def update_notes_periode(year: int, mes: int, notes: str, db: Session = Depends(get_db)):
    p = _get_or_create_periode(year, mes, db)
    p.notes = notes
    db.commit()
    db.refresh(p)
    return p


# ---------------------------------------------------------------------------
# Caixa diària (full manual de cobraments per mètode de pagament / IVA —
# equivalent digital de l'Excel de caixa que portava la botiga)
# ---------------------------------------------------------------------------

def _validar_mes(mes: int):
    if not (1 <= mes <= 12):
        raise HTTPException(422, "Mes ha de ser entre 1 i 12")


def _dies_del_mes(year: int, mes: int) -> list[date]:
    n = calendar.monthrange(year, mes)[1]
    return [date(year, mes, d) for d in range(1, n + 1)]


def _linia_out(data_: date, caixa: CaixaDiaria | None) -> CaixaDiariaLiniaOut:
    valors = {camp: getattr(caixa, camp) if caixa else Decimal("0") for camp in CAIXA_DIARIA_CAMPS}
    return CaixaDiariaLiniaOut(data=data_, total_dia=sum(valors.values()), **valors)


def _get_caixa_diaria_mes(year: int, mes: int, db: Session) -> CaixaDiariaMesOut:
    periode = db.scalar(
        select(PeriodeComptable).where(PeriodeComptable.year == year, PeriodeComptable.mes == mes)
    )
    dies = _dies_del_mes(year, mes)
    existents = {c.data: c for c in db.scalars(select(CaixaDiaria).where(CaixaDiaria.data.in_(dies)))}
    linies = [_linia_out(d, existents.get(d)) for d in dies]

    totals = {camp: sum(getattr(l, camp) for l in linies) for camp in CAIXA_DIARIA_CAMPS}
    total_mes = sum(totals.values())

    return CaixaDiariaMesOut(
        year=year, mes=mes,
        periode_tancat=periode.tancat if periode else False,
        dies=linies,
        totals=CaixaDiariaLiniaOut(data=dies[0], total_dia=total_mes, **totals),
        total_mes=total_mes,
    )


@router.get("/caixa-diaria/{year}/{mes}", response_model=CaixaDiariaMesOut)
def get_caixa_diaria(year: int, mes: int, db: Session = Depends(get_db)):
    _validar_mes(mes)
    return _get_caixa_diaria_mes(year, mes, db)


def _camp_iva(prefix: str, iva_pct: Decimal | None) -> str | None:
    if iva_pct == 21:
        return f"{prefix}_21"
    if iva_pct == 4:
        return f"{prefix}_4"
    return None  # tipus d'IVA configurat fora de 21%/4% — no hi encaixa a la graella


_PREFIX_PER_METODE = {
    MetodoPago.tarjeta: "targeta",
    MetodoPago.efectivo: "efectiu",
    MetodoPago.bizum: "bizum",
    # bono_cultural no es desglossa per IVA: una sola columna a la graella.
}


@router.get("/caixa-diaria/{year}/{mes}/vendes-reals", response_model=list[VendesRealsLiniaOut])
def get_vendes_reals(year: int, mes: int, db: Session = Depends(get_db)):
    """Reconstrueix targeta/efectiu/bizum/bono cultural per dia a partir de
    vendes reals, perquè l'admin no hagi de teclejar-les: vendes web pagades
    amb Redsys (sempre targeta) i vendes de mostrador (TPV, `VentaExterna.canal
    == mostrador`) amb el mètode de pagament que es va triar al cobrar. Deixa
    fora Discogs (cobrament fora de la nostra caixa) i les comandes web 'paga
    en recollir' (un cop cobrades a mostrador no queda registrat si van pagar
    en efectiu o targeta) — aquests casos, com paypal/transferència, s'ajusten
    a mà."""
    _validar_mes(mes)

    def _mes_filter(col):
        return (extract("year", col) == year) & (extract("month", col) == mes)

    acumulat: dict[date, dict[str, Decimal]] = {}

    def _afegeix(dia: date, camp: str, import_: Decimal):
        fila = acumulat.setdefault(dia, {
            "targeta_21": Decimal("0"), "targeta_4": Decimal("0"),
            "efectiu_21": Decimal("0"), "efectiu_4": Decimal("0"),
            "bizum_21": Decimal("0"), "bizum_4": Decimal("0"),
            "bono_cultural": Decimal("0"),
        })
        fila[camp] += import_

    web_rows = db.execute(
        select(func.date(Order.created_at), OrderItem.iva_pct, func.sum(OrderItem.precio))
        .join(Order, Order.id == OrderItem.order_id)
        .where(_mes_filter(Order.created_at))
        .where(Order.status.in_([OrderStatus.pagado, OrderStatus.enviado, OrderStatus.entregado]))
        .where(Order.metodo_pago == "redsys")
        .group_by(func.date(Order.created_at), OrderItem.iva_pct)
    ).all()
    for dia, iva_pct, total in web_rows:
        camp = _camp_iva("targeta", iva_pct)
        if camp and total:
            _afegeix(dia, camp, total)

    tpv_rows = db.execute(
        select(func.date(VentaExterna.fecha), VentaExterna.metodo_pago, VentaExterna.iva_pct,
               func.sum(VentaExterna.precio_venta))
        .where(_mes_filter(VentaExterna.fecha))
        .where(VentaExterna.canal == CanalVenta.mostrador)
        .group_by(func.date(VentaExterna.fecha), VentaExterna.metodo_pago, VentaExterna.iva_pct)
    ).all()
    for dia, metode, iva_pct, total in tpv_rows:
        if not total:
            continue
        if metode == MetodoPago.bono_cultural:
            _afegeix(dia, "bono_cultural", total)
            continue
        prefix = _PREFIX_PER_METODE.get(metode)
        camp = _camp_iva(prefix, iva_pct) if prefix else None
        if camp:
            _afegeix(dia, camp, total)

    return [
        VendesRealsLiniaOut(data=dia, **valors)
        for dia, valors in sorted(acumulat.items())
    ]


@router.put("/caixa-diaria/{year}/{mes}", response_model=CaixaDiariaMesOut)
def save_caixa_diaria(year: int, mes: int, payload: list[CaixaDiariaLiniaIn], db: Session = Depends(get_db)):
    _validar_mes(mes)
    periode = db.scalar(
        select(PeriodeComptable).where(PeriodeComptable.year == year, PeriodeComptable.mes == mes)
    )
    if periode and periode.tancat:
        raise HTTPException(409, "El mes està tancat — obre'l primer per editar la caixa")

    dies_valids = set(_dies_del_mes(year, mes))
    existents = {c.data: c for c in db.scalars(select(CaixaDiaria).where(CaixaDiaria.data.in_(dies_valids)))}
    for linia in payload:
        if linia.data not in dies_valids:
            raise HTTPException(422, f"{linia.data} no pertany a {mes}/{year}")
        caixa = existents.get(linia.data)
        if caixa is None:
            caixa = CaixaDiaria(data=linia.data)
            db.add(caixa)
            existents[linia.data] = caixa
        for camp in CAIXA_DIARIA_CAMPS:
            setattr(caixa, camp, getattr(linia, camp))
    db.commit()

    return _get_caixa_diaria_mes(year, mes, db)


@router.get("/caixa-diaria/{year}/{mes}/excel")
def export_caixa_diaria_excel(year: int, mes: int, db: Session = Depends(get_db)):
    _validar_mes(mes)
    mes_data = _get_caixa_diaria_mes(year, mes, db)
    xlsx_bytes = generate_caixa_diaria_excel(mes_data)
    filename = f"caixa_{year}_{mes:02d}.xlsx"
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/caixa-diaria/{year}/{mes}/pdf")
def export_caixa_diaria_pdf(year: int, mes: int, db: Session = Depends(get_db)):
    _validar_mes(mes)
    mes_data = _get_caixa_diaria_mes(year, mes, db)
    pdf_bytes = generate_caixa_diaria_pdf(mes_data)
    filename = f"caixa_{year}_{mes:02d}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
