"""ERP: entradas de stock (comandas a proveïdor + compres a particular) y
ventas externas (TPV + Discogs).

Flujo de entrada de stock a proveïdor:
  1. POST /admin/proveedores                    (si es proveedor nuevo)
  2. POST /admin/comandas                        (comanda amb línies; opcionalment
                                                  /admin/comandas/resolver-csv per
                                                  afegir-ne en bloc)
  3. POST /admin/comandas/{id}/enviar            (PDF al proveïdor)
  4. POST /admin/comandas/{id}/recepcio          (albarà: crea la Compra + Items reals,
                                                  poden fer-se vàries recepcions parcials)
  5. POST /admin/despeses/des-de-compres         (factura: agrupa una o més recepcions
                                                  encara sense facturar en una Despesa
                                                  pendent de pagament — comptabilitat.py)

Flujo de compra ràpida a particular (neix entregada):
  POST /admin/compras/particular

Flujo de venta externa:
  POST /admin/ventas-externas      (marca el item como retirado atómicamente
                                    y registra precio/canal para reporting)
"""

import csv
import io
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import (
    CajaMovimiento, CajaSession, CanalVenta, Comanda, ComandaLinea, CondicionItem, Compra,
    DevolucionCompra, DevolucionVenta, EstadoComanda, EstadoPeticionCliente, EstadoSolicitud,
    HistorialCompra, Item, ItemStatus, MetodoPago, Order, OrderItem, OrderStatus,
    OrigenSolicitud, PeticionCliente, Proveedor, Release,
    SolicitudCompra, SolicitudCompraLinea, StockHold, TipoCompra, TipoMovimiento, TipusIva, User,
    VentaExterna,
)
from ..schemas import (
    CajaCierreIn, CajaMovimientoIn, CajaMovimientoOut, CajaSessionIn, CajaSessionOut,
    ComandaIn, ComandaOut, CompraItemOut, CompraOut, CompraParticularIn,
    ComprasStatsMesOut, ComprasStatsOut, ComprasStatsProveedorOut,
    DevolucionCompraIn, DevolucionCompraOut,
    DevolucionVentaIn, DevolucionVentaOut,
    HistorialCompraOut, HistorialResumProveedorOut,
    PeticionCatalogarIn, PeticionClienteAdminOut, PeticionPrecioIn, PeticionTiendaIn,
    PeticionVincularIn, PeticionVincularItemIn, ReservaRecollidaOut,
    RefillSugerenciaOut,
    ProveedorIn, ProveedorOut, RecepcionIn,
    ResoldreEstocIn,
    SolicitudCompraIn, SolicitudCompraLineaIn, SolicitudCompraLineaOut, SolicitudCompraOut, SolicitudResolverIn,
    VentaExternaIn, VentaExternaOut, VentaExternaLoteIn, VincularUsuariTicketIn,
)
from ..services import discogs
from ..services.comanda_pdf import generate_comanda_pdf
from ..services.recepcio_pdf import generate_recepcio_pdf
from ..services.discogs_sync import remove_item_from_discogs, sync_stock_listing
from ..services.emailer import render_email_html, send_email
from ..services.i18n import frontend_url, translate
from ..services.iva import compute_iva_venda
from ..services.reservations import release_expired
from ..services.security import create_magic_link_token, require_admin

router = APIRouter(prefix="/admin", tags=["erp"], dependencies=[Depends(require_admin)])

_NO_SYNC = {"synchronize_session": False}


# ---------------------------------------------------------------------------
# Proveedores
# ---------------------------------------------------------------------------

@router.post("/proveedores", status_code=201, response_model=ProveedorOut)
def create_proveedor(payload: ProveedorIn, db: Session = Depends(get_db)):
    proveedor = Proveedor(**payload.model_dump())
    db.add(proveedor)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"Ya existe un proveedor con el nombre '{payload.nombre}'")
    db.refresh(proveedor)
    return proveedor


@router.get("/proveedores", response_model=list[ProveedorOut])
def list_proveedores(db: Session = Depends(get_db)):
    return db.scalars(select(Proveedor).order_by(Proveedor.nombre)).all()


# Nota: GET/PATCH d'un proveïdor individual ja existeixen a comptabilitat.py


# ---------------------------------------------------------------------------
# Compras (entradas de stock)
# ---------------------------------------------------------------------------

def _resolve_release_by_discogs_id(db: Session, discogs_release_id: int) -> Release:
    release = db.scalar(select(Release).where(Release.discogs_release_id == discogs_release_id))
    if release is not None:
        return release
    data = discogs.get_release(discogs_release_id)
    release = Release(
        artista=data.get("artista") or f"Discogs #{discogs_release_id}",
        titulo=data.get("titulo") or "",
        sello=data.get("sello"), referencia=data.get("referencia"),
        anio=data.get("anio"), genero=data.get("genero"), estilos=data.get("estilos"),
        pais=data.get("pais"), imagen_url=data.get("imagen_url"),
        tracklist=data.get("tracklist"), credits=data.get("credits"),
        discogs_release_id=discogs_release_id,
    )
    db.add(release)
    db.flush()
    return release


def _registrar_sortida_caixa(db: Session, concepto: str, importe: Decimal, fecha: datetime) -> None:
    """Best-effort: si hi ha una sessió de caixa oberta, hi apunta la despesa."""
    sesion = db.scalar(
        select(CajaSession).where(CajaSession.fecha_cierre.is_(None))
        .order_by(CajaSession.fecha_apertura.desc())
    )
    if sesion:
        db.add(CajaMovimiento(
            session_id=sesion.id, tipo=TipoMovimiento.salida,
            concepto=concepto, importe=importe, fecha=fecha,
        ))


@router.post("/compras/particular", status_code=201)
def create_compra_particular(payload: CompraParticularIn, db: Session = Depends(get_db)):
    """Compra ràpida a un particular que ve a la botiga: neix entregada (stock
    disponible a l'instant) i s'apunta com a sortida de caixa si hi ha sessió oberta."""
    for line in payload.items:
        if db.get(Release, line.release_id) is None:
            raise HTTPException(404, f"Release {line.release_id} no encontrado")

    total_coste = sum((line.coste_adquisicion for line in payload.items), Decimal("0"))
    compra = Compra(
        tipo=TipoCompra.particular,
        nombre_particular=payload.nombre_particular,
        user_id=payload.user_id,
        fecha=payload.fecha,
        notas=payload.notas,
        coste_total=total_coste,
    )
    db.add(compra)
    db.flush()

    for line in payload.items:
        db.add(Item(
            release_id=line.release_id, precio=line.precio, condicion=line.condicion,
            coste_adquisicion=line.coste_adquisicion, estado_disco=line.estado_disco,
            estado_funda=line.estado_funda, compra_id=compra.id,
            fecha_entrada=compra.fecha,
        ))

    if total_coste > 0:
        nombre = payload.nombre_particular or "particular"
        _registrar_sortida_caixa(db, f"Compra a particular: {nombre}", total_coste, payload.fecha)

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
        .order_by(Compra.fecha.desc())
    )
    if tipo:
        stmt = stmt.where(Compra.tipo == tipo)
    if proveedor_id:
        stmt = stmt.where(Compra.proveedor_id == proveedor_id)
    if sense_facturar:
        stmt = stmt.where(Compra.despesa_id.is_(None))
    if desde:
        stmt = stmt.where(Compra.fecha >= desde)
    if hasta:
        stmt = stmt.where(Compra.fecha <= hasta)
    compras = db.scalars(stmt).all()

    if q:
        ql = q.lower()
        compras = [
            c for c in compras
            if (c.nombre_particular and ql in c.nombre_particular.lower())
            or (c.client and c.client.nombre and ql in c.client.nombre.lower())
            or (c.num_albaran and ql in c.num_albaran.lower())
            or (c.proveedor and ql in c.proveedor.nombre.lower())
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

    # Compra.coste_total (fijado al crear la recepción) es la fuente fiable:
    # sumar Item.coste_adquisicion vía Item.compra_id ya no basta desde que
    # una línea nou puede acumular varias recepciones en la misma fila
    # (que solo apunta a la compra_id de la última).
    rows = db.execute(
        select(
            Compra.id, Compra.tipo, Compra.proveedor_id, Compra.fecha, Compra.despesa_id,
            Proveedor.nombre, func.coalesce(Compra.coste_total, 0),
        )
        .select_from(Compra)
        .outerjoin(Proveedor, Proveedor.id == Compra.proveedor_id)
        .where(Compra.fecha >= fa_12_mesos)
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
    filename = f"recepcio_{compra.num_albaran or compra.id}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _compra_out(compra: Compra, returned_item_ids: set | None = None) -> dict:
    returned_item_ids = returned_item_ids or set()
    return {
        "id": compra.id,
        "tipo": compra.tipo,
        "proveedor_id": compra.proveedor_id,
        "nombre_particular": compra.nombre_particular,
        "user_id": compra.user_id,
        "user_nom": compra.client.nombre if compra.client else None,
        "fecha": compra.fecha,
        "num_albaran": compra.num_albaran,
        "notas": compra.notas,
        "comanda_id": compra.comanda_id,
        "despesa_id": compra.despesa_id,
        "despesa_estat": compra.despesa.estat_pagament if compra.despesa else None,
        "created_at": compra.created_at,
        "items": [
            CompraItemOut(
                item_id=it.id,
                release_id=it.release_id,
                artista=it.release.artista,
                titulo=it.release.titulo,
                precio=it.precio,
                coste_adquisicion=it.coste_adquisicion,
                item_status=it.status,
                devuelto=it.id in returned_item_ids,
            )
            for it in compra.items
        ],
    }


# ---------------------------------------------------------------------------
# Comandas a proveïdor (abans de l'entrada de stock)
# ---------------------------------------------------------------------------

def _comanda_out(comanda: Comanda) -> dict:
    return {
        "id": comanda.id,
        "proveedor_id": comanda.proveedor_id,
        "proveedor_nombre": comanda.proveedor.nombre,
        "fecha": comanda.fecha,
        "status": comanda.status,
        "num_comanda": comanda.num_comanda,
        "notas": comanda.notas,
        "enviada_at": comanda.enviada_at,
        "created_at": comanda.created_at,
        "lineas": [
            {
                "id": linea.id,
                "release_id": linea.release_id,
                "artista": linea.release.artista,
                "titulo": linea.release.titulo,
                "cantidad": linea.cantidad,
                "precio_unitario_estimado": linea.precio_unitario_estimado,
                "cantidad_rebuda": linea.cantidad_rebuda,
                "notas": linea.notas,
            }
            for linea in comanda.lineas
        ],
    }


def _get_comanda_or_404(db: Session, comanda_id: uuid.UUID) -> Comanda:
    comanda = db.scalar(
        select(Comanda)
        .options(selectinload(Comanda.lineas).selectinload(ComandaLinea.release), selectinload(Comanda.proveedor))
        .where(Comanda.id == comanda_id)
    )
    if comanda is None:
        raise HTTPException(404, "Comanda no encontrada")
    return comanda


COMANDA_CSV_FIELDS = ["discogs_release_id", "cantidad", "precio_unitario_estimado"]


@router.get("/comandas/plantilla.csv")
def comanda_csv_template():
    """Plantilla per afegir línies a una comanda en bloc: discogs_release_id + quantitat + preu estimat."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(COMANDA_CSV_FIELDS)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=plantilla_comanda.csv"},
    )


@router.post("/comandas/resolver-csv")
async def resolver_comanda_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Resol un CSV de discogs_release_id+cantidad+precio_unitario_estimado a línies
    de comanda (resolent o creant el release a partir de Discogs). No crea cap comanda:
    només retorna les línies per afegir-les al formulari que s'estigui editant."""
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))

    lineas: list[dict] = []
    errors: list[dict] = []
    for n, row in enumerate(reader, start=2):  # fila 1 és la capçalera
        discogs_id_raw = (row.get("discogs_release_id") or "").strip()
        if not discogs_id_raw:
            errors.append({"fila": n, "motiu": "Falta discogs_release_id"})
            continue
        try:
            discogs_release_id = int(discogs_id_raw)
        except ValueError:
            errors.append({"fila": n, "motiu": "discogs_release_id invàlid"})
            continue

        cantidad_raw = (row.get("cantidad") or "1").strip()
        precio_raw = (row.get("precio_unitario_estimado") or "").strip()
        try:
            cantidad = int(cantidad_raw) if cantidad_raw else 1
            precio_unitario_estimado = Decimal(precio_raw) if precio_raw else None
        except (ValueError, InvalidOperation):
            errors.append({"fila": n, "motiu": "cantidad o precio_unitario_estimado invàlid"})
            continue

        try:
            release = _resolve_release_by_discogs_id(db, discogs_release_id)
        except Exception as exc:
            errors.append({"fila": n, "discogs_release_id": discogs_release_id, "motiu": f"Error consultant Discogs: {exc}"})
            continue

        lineas.append({
            "release_id": str(release.id), "artista": release.artista, "titulo": release.titulo,
            "cantidad": cantidad, "precio_unitario_estimado": precio_unitario_estimado,
            "existing": True,
        })

    db.commit()  # persisteix els releases creats encara que no es desi la comanda
    return {"lineas": lineas, "errors": errors}


def _next_num_comanda(db: Session, year: int) -> str:
    """Numeració automàtica per any: '2026-000001', '2026-000002'..."""
    prefix = f"{year}-"
    existentes = db.scalars(
        select(Comanda.num_comanda).where(Comanda.num_comanda.like(f"{prefix}%"))
    ).all()
    max_n = 0
    for num in existentes:
        try:
            max_n = max(max_n, int(num.split("-", 1)[1]))
        except (IndexError, ValueError):
            continue
    return f"{prefix}{max_n + 1:06d}"


@router.post("/comandas", status_code=201, response_model=ComandaOut)
def create_comanda(payload: ComandaIn, db: Session = Depends(get_db)):
    if db.get(Proveedor, payload.proveedor_id) is None:
        raise HTTPException(404, "Proveedor no encontrado")
    for linea in payload.lineas:
        if db.get(Release, linea.release_id) is None:
            raise HTTPException(404, f"Release {linea.release_id} no encontrado")

    for intento in range(3):
        comanda = Comanda(
            proveedor_id=payload.proveedor_id, fecha=payload.fecha,
            num_comanda=_next_num_comanda(db, payload.fecha.year), notas=payload.notas,
        )
        db.add(comanda)
        try:
            db.flush()
            break
        except IntegrityError:
            db.rollback()
            if intento == 2:
                raise HTTPException(409, "No s'ha pogut generar el número de comanda, torna-ho a provar")
    for linea in payload.lineas:
        db.add(ComandaLinea(
            comanda_id=comanda.id, release_id=linea.release_id, cantidad=linea.cantidad,
            precio_unitario_estimado=linea.precio_unitario_estimado, notas=linea.notas,
        ))
    db.commit()
    return _comanda_out(_get_comanda_or_404(db, comanda.id))


@router.get("/comandas", response_model=list[ComandaOut])
def list_comandas(
    status: str | None = None,
    q: str | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    db: Session = Depends(get_db),
):
    stmt = (
        select(Comanda)
        .options(selectinload(Comanda.lineas).selectinload(ComandaLinea.release), selectinload(Comanda.proveedor))
        .order_by(Comanda.fecha.desc())
    )
    if status:
        stmt = stmt.where(Comanda.status == EstadoComanda(status))
    if desde:
        stmt = stmt.where(Comanda.fecha >= desde)
    if hasta:
        stmt = stmt.where(Comanda.fecha <= hasta)
    comandas = db.scalars(stmt).all()

    if q:
        ql = q.lower()
        comandas = [
            c for c in comandas
            if (c.num_comanda and ql in c.num_comanda.lower())
            or ql in c.proveedor.nombre.lower()
        ]

    return [_comanda_out(c) for c in comandas]


@router.get("/comandas/{comanda_id}", response_model=ComandaOut)
def get_comanda(comanda_id: uuid.UUID, db: Session = Depends(get_db)):
    return _comanda_out(_get_comanda_or_404(db, comanda_id))


@router.delete("/comandas/{comanda_id}", status_code=204)
def delete_comanda(comanda_id: uuid.UUID, db: Session = Depends(get_db)):
    comanda = db.get(Comanda, comanda_id)
    if comanda is None:
        raise HTTPException(404, "Comanda no encontrada")
    if comanda.status != EstadoComanda.esborrany:
        raise HTTPException(409, "Només es poden eliminar comandes en esborrany")
    db.delete(comanda)
    db.commit()


@router.get("/comandas/{comanda_id}/pdf")
def comanda_pdf(comanda_id: uuid.UUID, db: Session = Depends(get_db)):
    comanda = _get_comanda_or_404(db, comanda_id)
    pdf_bytes = generate_comanda_pdf(comanda, db)
    filename = f"comanda_{comanda.num_comanda or comanda.id}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/comandas/{comanda_id}/enviar", response_model=ComandaOut)
def enviar_comanda(comanda_id: uuid.UUID, db: Session = Depends(get_db)):
    """Envia la comanda per email al proveïdor (amb el PDF adjunt) i la marca com a enviada."""
    comanda = _get_comanda_or_404(db, comanda_id)
    if comanda.status not in (EstadoComanda.esborrany, EstadoComanda.enviada):
        raise HTTPException(409, "Aquesta comanda no es pot enviar en el seu estat actual")
    if not comanda.proveedor.email:
        raise HTTPException(422, "El proveïdor no té email configurat")

    pdf_bytes = generate_comanda_pdf(comanda, db)
    filename = f"comanda_{comanda.num_comanda or comanda.id}.pdf"
    send_email(
        to=comanda.proveedor.email,
        subject=f"Comanda {comanda.num_comanda or comanda.id}",
        body="Adjuntem la comanda. Gràcies!",
        attachment=(filename, pdf_bytes, "application/pdf"),
    )
    comanda.enviada_at = datetime.now(timezone.utc)
    if comanda.status == EstadoComanda.esborrany:
        comanda.status = EstadoComanda.enviada
    db.commit()
    return _comanda_out(_get_comanda_or_404(db, comanda.id))


@router.patch("/comandas/{comanda_id}/marcar-enviada", response_model=ComandaOut)
def marcar_comanda_enviada(comanda_id: uuid.UUID, db: Session = Depends(get_db)):
    """Marca la comanda com a enviada a mà (quan s'ha enviat el PDF per un altre canal)."""
    comanda = db.get(Comanda, comanda_id)
    if comanda is None:
        raise HTTPException(404, "Comanda no encontrada")
    if comanda.status != EstadoComanda.esborrany:
        raise HTTPException(409, "Aquesta comanda no es pot marcar com a enviada en el seu estat actual")
    comanda.status = EstadoComanda.enviada
    comanda.enviada_at = datetime.now(timezone.utc)
    db.commit()
    return _comanda_out(_get_comanda_or_404(db, comanda.id))


@router.patch("/comandas/{comanda_id}/cancelar", response_model=ComandaOut)
def cancelar_comanda(comanda_id: uuid.UUID, db: Session = Depends(get_db)):
    comanda = db.get(Comanda, comanda_id)
    if comanda is None:
        raise HTTPException(404, "Comanda no encontrada")
    if comanda.status in (EstadoComanda.rebuda, EstadoComanda.cancelada):
        raise HTTPException(409, "Aquesta comanda no es pot cancel·lar en el seu estat actual")
    comanda.status = EstadoComanda.cancelada
    db.commit()
    return _comanda_out(_get_comanda_or_404(db, comanda.id))


@router.post("/comandas/{comanda_id}/recepcio", status_code=201)
def recibir_comanda(comanda_id: uuid.UUID, payload: RecepcionIn, db: Session = Depends(get_db)):
    """Registra l'arribada de l'albarà (total o parcial): crea la Compra + Items
    (pujada a stock real) i actualitza les quantitats rebudes de cada línia."""
    comanda = _get_comanda_or_404(db, comanda_id)
    if comanda.status not in (EstadoComanda.enviada, EstadoComanda.rebuda_parcial):
        raise HTTPException(409, "Aquesta comanda no està en condicions de rebre mercaderia")

    lineas_por_id = {linea.id: linea for linea in comanda.lineas}
    pendientes: dict[uuid.UUID, int] = {}
    for item in payload.items:
        linea = lineas_por_id.get(item.comanda_linea_id)
        if linea is None:
            raise HTTPException(404, f"Línia de comanda {item.comanda_linea_id} no trobada en aquesta comanda")
        # Per a segona_ma, cada entrada és una còpia física (cantidad=1); per
        # a nou, una entrada pot representar-ne diverses (stock agregat).
        pendientes[item.comanda_linea_id] = pendientes.get(item.comanda_linea_id, 0) + item.cantidad

    for linea_id, cantidad in pendientes.items():
        linea = lineas_por_id[linea_id]
        disponible = linea.cantidad - linea.cantidad_rebuda
        if cantidad > disponible:
            raise HTTPException(
                422,
                f"La línia de '{linea.release.artista} - {linea.release.titulo}' només té "
                f"{disponible} unitats pendents de rebre (s'han enviat {cantidad})",
            )

    compra = Compra(
        tipo=TipoCompra.proveedor, proveedor_id=comanda.proveedor_id,
        fecha=payload.fecha, num_albaran=payload.num_albaran, notas=payload.notas,
        comanda_id=comanda.id,
        coste_total=sum((item.coste_adquisicion or Decimal("0")) * item.cantidad for item in payload.items),
    )
    db.add(compra)
    db.flush()

    # Peticions de client 'en_tramit' que esperen precisament aquesta línia
    # de comanda: reservem l'exemplar acabat d'arribar directament, sense
    # haver de fer després el pas manual de "vincular exemplar".
    peticiones_por_linea: dict[uuid.UUID, PeticionCliente] = {
        sol_linea.comanda_linea_id: peticion
        for peticion, sol_linea in db.execute(
            select(PeticionCliente, SolicitudCompraLinea)
            .join(SolicitudCompraLinea, SolicitudCompraLinea.id == PeticionCliente.solicitud_compra_linea_id)
            .where(
                SolicitudCompraLinea.comanda_linea_id.in_(pendientes.keys()),
                PeticionCliente.estado == EstadoPeticionCliente.en_tramit,
            )
        ).all()
    }

    # Para condicion='nou' (stock agregado), varias entradas de la misma
    # línea de comanda —o una recepción posterior de la misma línea, ver
    # `linea_nou_id` abajo— se acumulan en UNA sola fila `Item` en vez de
    # crear una por unidad; `lineas_nou_vistas` evita recalcular el coste
    # medio dos veces si esta misma llamada trae 2+ entradas nou de la
    # misma línea de comanda.
    items_creados: list[Item] = []
    lineas_nou_vistas: dict[uuid.UUID, Item] = {}
    for item in payload.items:
        linea = lineas_por_id[item.comanda_linea_id]
        if item.condicion != CondicionItem.nou.value:
            nuevo_item = Item(
                release_id=linea.release_id, precio=item.precio, condicion=item.condicion,
                coste_adquisicion=item.coste_adquisicion, estado_disco=item.estado_disco,
                estado_funda=item.estado_funda, compra_id=compra.id,
                fecha_entrada=compra.fecha,
            )
            db.add(nuevo_item)
            items_creados.append(nuevo_item)
            continue

        agregado = lineas_nou_vistas.get(item.comanda_linea_id)
        if agregado is None:
            agregado = db.scalar(
                select(Item).where(Item.release_id == linea.release_id, Item.condicion == CondicionItem.nou)
            )
        n = item.cantidad
        if agregado is None:
            agregado = Item(
                release_id=linea.release_id, precio=item.precio, condicion=CondicionItem.nou,
                cantidad=n, coste_adquisicion=item.coste_adquisicion,
                compra_id=compra.id, fecha_entrada=compra.fecha,
            )
            db.add(agregado)
        else:
            coste_anterior = agregado.coste_adquisicion or Decimal("0")
            coste_nuevo = item.coste_adquisicion if item.coste_adquisicion is not None else coste_anterior
            agregado.coste_adquisicion = (
                agregado.cantidad * coste_anterior + n * coste_nuevo
            ) / (agregado.cantidad + n)
            agregado.cantidad += n
            agregado.precio = item.precio
            agregado.compra_id = compra.id
            agregado.fecha_entrada = compra.fecha
        sync_stock_listing(db, agregado)
        lineas_nou_vistas[item.comanda_linea_id] = agregado
        items_creados.append(agregado)

    for linea_id, cantidad in pendientes.items():
        lineas_por_id[linea_id].cantidad_rebuda += cantidad

    comanda.status = (
        EstadoComanda.rebuda
        if all(l.cantidad_rebuda >= l.cantidad for l in comanda.lineas)
        else EstadoComanda.rebuda_parcial
    )

    # Nota: la línia de sol·licitud d'aquestes peticions ja va quedar
    # marcada amb `comanda_linea_id` en el moment de resoldre la sol·licitud
    # cap a aquesta Comanda (abans d'enviar-la), no aquí.
    peticiones_afectadas_ids: list[uuid.UUID] = []
    if peticiones_por_linea:
        db.flush()  # cal l'id dels items acabats de crear
        for nuevo_item, item_in in zip(items_creados, payload.items):
            peticion = peticiones_por_linea.pop(item_in.comanda_linea_id, None)
            if peticion is None:
                continue
            _reservar_item_para_peticion(db, peticion, nuevo_item)
            peticiones_afectadas_ids.append(peticion.id)

    db.commit()

    for peticion in db.scalars(
        select(PeticionCliente)
        .where(PeticionCliente.id.in_(peticiones_afectadas_ids))
        .options(selectinload(PeticionCliente.release), selectinload(PeticionCliente.user))
    ):
        _enviar_email_item_arribat(db, peticion)

    return {"compra_id": str(compra.id), "items_creados": len(payload.items), "comanda_status": comanda.status}


# ---------------------------------------------------------------------------
# Historial de compres — buscador de proveïdor
# ---------------------------------------------------------------------------

# Estats d'una Comanda que compten com a "senyal real de compra" per al
# buscador de proveïdor: esborrany encara no s'ha enviat de veritat i
# cancelada mai va arribar a fer-se, així que no diuen res sobre qui
# subministra què.
_ESTATS_COMANDA_REALS = [EstadoComanda.enviada, EstadoComanda.rebuda_parcial, EstadoComanda.rebuda]


@router.get("/historial-compres/resum", response_model=list[HistorialResumProveedorOut])
def resum_historial_compres(q: str | None = None, db: Session = Depends(get_db)):
    """Llistat de proveïdors amb quantes línies de l'històric hi ha i quan
    va ser l'última, per mostrar-ho com a llista desplegable per defecte
    (sense necessitat de cercar). Si es passa `q`, filtra igual que la cerca.

    Combina dues fonts perquè el buscador vagi "aprenent" amb el temps, no
    només amb la importació inicial dels fulls de càlcul (veure
    buscar_historial_compres per l'explicació completa)."""
    stmt = (
        select(
            Proveedor.id, Proveedor.nombre,
            func.count(HistorialCompra.id), func.max(HistorialCompra.fecha),
        )
        .join(HistorialCompra, HistorialCompra.proveedor_id == Proveedor.id)
    )
    if q is not None and len(q.strip()) >= 2:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            (HistorialCompra.artista.ilike(like))
            | (HistorialCompra.titulo.ilike(like))
            | (HistorialCompra.sello.ilike(like))
            | (HistorialCompra.notas.ilike(like))
        )
    stmt = stmt.group_by(Proveedor.id, Proveedor.nombre)

    resum: dict[uuid.UUID, list] = {}
    for pid, nom, count, ultima in db.execute(stmt).all():
        resum[pid] = [nom, count, ultima]

    stmt2 = (
        select(
            Proveedor.id, Proveedor.nombre,
            func.count(ComandaLinea.id), func.max(Comanda.fecha),
        )
        .select_from(ComandaLinea)
        .join(Comanda, Comanda.id == ComandaLinea.comanda_id)
        .join(Proveedor, Proveedor.id == Comanda.proveedor_id)
        .join(Release, Release.id == ComandaLinea.release_id)
        .where(Comanda.status.in_(_ESTATS_COMANDA_REALS))
    )
    if q is not None and len(q.strip()) >= 2:
        like = f"%{q.strip()}%"
        stmt2 = stmt2.where(
            (Release.artista.ilike(like))
            | (Release.titulo.ilike(like))
            | (Release.sello.ilike(like))
            | (ComandaLinea.notas.ilike(like))
        )
    stmt2 = stmt2.group_by(Proveedor.id, Proveedor.nombre)
    for pid, nom, count, ultima in db.execute(stmt2).all():
        ultima = ultima.date() if hasattr(ultima, "date") else ultima
        if pid in resum:
            resum[pid][1] += count
            resum[pid][2] = max(resum[pid][2], ultima)
        else:
            resum[pid] = [nom, count, ultima]

    result = [
        HistorialResumProveedorOut(proveedor_id=pid, proveedor_nombre=nom, count=count, ultima_compra=ultima)
        for pid, (nom, count, ultima) in resum.items()
    ]
    result.sort(key=lambda r: r.count, reverse=True)
    return result


@router.get("/historial-compres", response_model=list[HistorialCompraOut])
def buscar_historial_compres(
    q: str | None = None, release_id: uuid.UUID | None = None,
    proveedor_id: uuid.UUID | None = None, db: Session = Depends(get_db),
):
    """Llistat/cerca de l'històric de compres per saber a quins proveïdors
    s'ha comprat abans un disc semblant. No és estoc en temps real, només
    senyal de l'històric. Sense cap filtre, retorna les més recents.

    `release_id`: coincidència exacta (senyal fort). `proveedor_id`: totes
    les línies d'un proveïdor concret. `q`: text lliure per artista/títol/
    segell/notes (mínim 2 caràcters). Combinables entre si.

    Combina dues fonts: `HistorialCompra` (fulls de càlcul d'abans del
    sistema de Comanda/Compra, importació única i congelada) i les línies de
    `Comanda` reals fetes des d'aquí (enviada/rebuda_parcial/rebuda). Sense
    això, el buscador es quedaria congelat a la importació inicial i mai
    "aprendria" de les comandes noves — que és precisament el que ha de fer
    de motor de recomanació de proveïdor."""
    limit = 1000 if proveedor_id is not None else 200

    conditions = []
    if release_id is not None:
        conditions.append(HistorialCompra.release_id == release_id)
    if proveedor_id is not None:
        conditions.append(HistorialCompra.proveedor_id == proveedor_id)
    if q is not None and len(q.strip()) >= 2:
        like = f"%{q.strip()}%"
        conditions.append(
            (HistorialCompra.artista.ilike(like))
            | (HistorialCompra.titulo.ilike(like))
            | (HistorialCompra.sello.ilike(like))
            | (HistorialCompra.notas.ilike(like))
        )

    stmt = (
        select(HistorialCompra)
        .options(selectinload(HistorialCompra.proveedor), selectinload(HistorialCompra.release))
        .order_by(HistorialCompra.fecha.desc())
        .limit(limit)
    )
    for cond in conditions:
        stmt = stmt.where(cond)
    resultados = [
        HistorialCompraOut(
            id=r.id, proveedor_id=r.proveedor_id, proveedor_nombre=r.proveedor.nombre,
            fecha=r.fecha, artista=r.artista, titulo=r.titulo, sello=r.sello,
            formato=r.formato, cantidad=r.cantidad, precio_coste=r.precio_coste, notas=r.notas,
            release_id=r.release_id, ean=r.release.ean if r.release else None,
        )
        for r in db.scalars(stmt).all()
    ]

    stmt2 = (
        select(
            ComandaLinea.id, Comanda.proveedor_id, Proveedor.nombre, Comanda.fecha,
            Release.artista, Release.titulo, Release.sello, Release.formato,
            ComandaLinea.cantidad, ComandaLinea.precio_unitario_estimado, ComandaLinea.notas,
            ComandaLinea.release_id, Release.ean,
        )
        .join(Comanda, Comanda.id == ComandaLinea.comanda_id)
        .join(Proveedor, Proveedor.id == Comanda.proveedor_id)
        .join(Release, Release.id == ComandaLinea.release_id)
        .where(Comanda.status.in_(_ESTATS_COMANDA_REALS))
        .order_by(Comanda.fecha.desc())
        .limit(limit)
    )
    if release_id is not None:
        stmt2 = stmt2.where(ComandaLinea.release_id == release_id)
    if proveedor_id is not None:
        stmt2 = stmt2.where(Comanda.proveedor_id == proveedor_id)
    if q is not None and len(q.strip()) >= 2:
        like = f"%{q.strip()}%"
        stmt2 = stmt2.where(
            (Release.artista.ilike(like))
            | (Release.titulo.ilike(like))
            | (Release.sello.ilike(like))
            | (ComandaLinea.notas.ilike(like))
        )
    for lid, pid, pnom, fecha, artista, titulo, sello, formato, cantidad, precio, notas, rel_id, ean in db.execute(stmt2).all():
        resultados.append(HistorialCompraOut(
            id=lid, proveedor_id=pid, proveedor_nombre=pnom, fecha=fecha.date(),
            artista=artista, titulo=titulo, sello=sello, formato=formato,
            cantidad=cantidad, precio_coste=precio, notas=notas, release_id=rel_id, ean=ean,
        ))

    resultados.sort(key=lambda r: r.fecha, reverse=True)
    return resultados[:limit]


# ---------------------------------------------------------------------------
# Solicitudes de compra (previ, opcional, a la Comanda: encara sense proveïdor triat)
# ---------------------------------------------------------------------------

def _solicitud_linea_out(linea: SolicitudCompraLinea) -> SolicitudCompraLineaOut:
    return SolicitudCompraLineaOut(
        id=linea.id,
        release_id=linea.release_id,
        artista=linea.release.artista if linea.release else linea.artista,
        titulo=linea.release.titulo if linea.release else linea.titulo,
        sello=linea.release.sello if linea.release else linea.sello,
        formato=linea.release.formato if linea.release else linea.formato,
        cantidad=linea.cantidad,
        proveedor_sugerido_id=linea.proveedor_sugerido_id,
        proveedor_sugerido_nombre=linea.proveedor_sugerido.nombre if linea.proveedor_sugerido else None,
        comanda_linea_id=linea.comanda_linea_id,
        item_resuelto_id=linea.item_resuelto_id,
        resuelta=linea.comanda_linea_id is not None or linea.item_resuelto_id is not None,
        notas=linea.notas,
    )


def _solicitud_out(solicitud: SolicitudCompra) -> SolicitudCompraOut:
    return SolicitudCompraOut(
        id=solicitud.id,
        estado=solicitud.estado,
        origen=solicitud.origen,
        user_id=solicitud.user_id,
        user_nom=solicitud.user.nombre if solicitud.user else None,
        notas=solicitud.notas,
        created_at=solicitud.created_at,
        lineas=[_solicitud_linea_out(linea) for linea in solicitud.lineas],
    )


def _get_solicitud_or_404(db: Session, solicitud_id: uuid.UUID) -> SolicitudCompra:
    solicitud = db.scalar(
        select(SolicitudCompra)
        .options(
            selectinload(SolicitudCompra.lineas).selectinload(SolicitudCompraLinea.release),
            selectinload(SolicitudCompra.lineas).selectinload(SolicitudCompraLinea.proveedor_sugerido),
            selectinload(SolicitudCompra.user),
        )
        .where(SolicitudCompra.id == solicitud_id)
    )
    if solicitud is None:
        raise HTTPException(404, "Solicitud de compra no encontrada")
    return solicitud


VENTAS_WINDOW_DAYS = 60
URGENCIA_DIAS_ESTOC = 21
COBERTURA_OBJECTIU_DIAS = 30
ORDER_STATUS_VENUT = (OrderStatus.pagado, OrderStatus.enviado, OrderStatus.entregado)


def _suggest_proveedor_para_release(db: Session, release_id: uuid.UUID, artista: str) -> tuple[uuid.UUID | None, str | None]:
    """Mateixa lògica que el frontend fa servir en afegir un disc a mà: primer
    coincidència exacta de release_id a l'històric, si no n'hi ha, per artista."""
    rows = db.execute(
        select(HistorialCompra.proveedor_id, func.count())
        .where(HistorialCompra.release_id == release_id)
        .group_by(HistorialCompra.proveedor_id)
    ).all()
    if not rows and artista:
        rows = db.execute(
            select(HistorialCompra.proveedor_id, func.count())
            .where(HistorialCompra.artista.ilike(f"%{artista}%"))
            .group_by(HistorialCompra.proveedor_id)
        ).all()
    if not rows:
        return None, None
    top_id = sorted(rows, key=lambda r: -r[1])[0][0]
    prov = db.get(Proveedor, top_id)
    return (prov.id, prov.nombre) if prov else (None, None)


@router.get("/solicitudes-compra/refill-sugerencias", response_model=list[RefillSugerenciaOut])
def refill_sugerencias(db: Session = Depends(get_db)):
    """Previsualització (no crea res) de discos candidats a reposició:
    estoc baix, es continuen venent, i falten dies_estoc_actuals per
    esgotar-se segons la velocitat de venda dels últims 60 dies. No
    inclou releases que ja tenen una Comanda oberta pendent."""
    now = datetime.now(timezone.utc)
    inici_periode = now - timedelta(days=VENTAS_WINDOW_DAYS)
    inici_periode_anterior = now - timedelta(days=2 * VENTAS_WINDOW_DAYS)

    # Estoc actual (només còpies noves: la segona mà no es "reposa"). Suma
    # unitats lliures (cantidad - cantidad_reservada), no files: una sola
    # línia nou pot representar-ne moltes.
    stock_por_release: dict[uuid.UUID, int] = dict(db.execute(
        select(Item.release_id, func.sum(Item.cantidad - Item.cantidad_reservada))
        .where(Item.status == ItemStatus.disponible, Item.condicion == CondicionItem.nou)
        .group_by(Item.release_id)
    ).all())

    def _ventas_periode(desde: datetime, fins: datetime) -> dict[uuid.UUID, int]:
        web = dict(db.execute(
            select(Item.release_id, func.count())
            .select_from(OrderItem)
            .join(Order, Order.id == OrderItem.order_id)
            .join(Item, Item.id == OrderItem.item_id)
            .where(
                Order.status.in_(ORDER_STATUS_VENUT), Item.condicion == CondicionItem.nou,
                Order.created_at >= desde, Order.created_at < fins,
            )
            .group_by(Item.release_id)
        ).all())
        externa = dict(db.execute(
            select(Item.release_id, func.count())
            .select_from(VentaExterna)
            .join(Item, Item.id == VentaExterna.item_id)
            .where(Item.condicion == CondicionItem.nou, VentaExterna.fecha >= desde, VentaExterna.fecha < fins)
            .group_by(Item.release_id)
        ).all())
        combinado: dict[uuid.UUID, int] = dict(web)
        for rid, count in externa.items():
            combinado[rid] = combinado.get(rid, 0) + count
        return combinado

    vendes_actual = _ventas_periode(inici_periode, now)
    vendes_anterior = _ventas_periode(inici_periode_anterior, inici_periode)

    # Marge mitjà: preu de venda - cost d'adquisició dels ítems venuts al període.
    marge_web = db.execute(
        select(Item.release_id, func.avg(OrderItem.precio - Item.coste_adquisicion))
        .select_from(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .join(Item, Item.id == OrderItem.item_id)
        .where(
            Order.status.in_(ORDER_STATUS_VENUT), Item.coste_adquisicion.isnot(None),
            Order.created_at >= inici_periode,
        )
        .group_by(Item.release_id)
    ).all()
    marge_externa = db.execute(
        select(Item.release_id, func.avg(VentaExterna.precio_venta - Item.coste_adquisicion))
        .select_from(VentaExterna)
        .join(Item, Item.id == VentaExterna.item_id)
        .where(Item.coste_adquisicion.isnot(None), VentaExterna.fecha >= inici_periode)
        .group_by(Item.release_id)
    ).all()
    marge_por_release: dict[uuid.UUID, Decimal] = {}
    contador_marge: dict[uuid.UUID, int] = {}
    for rid, avg_marge in [*marge_web, *marge_externa]:
        if avg_marge is None:
            continue
        marge_por_release[rid] = marge_por_release.get(rid, Decimal("0")) + avg_marge
        contador_marge[rid] = contador_marge.get(rid, 0) + 1
    for rid in marge_por_release:
        marge_por_release[rid] = marge_por_release[rid] / contador_marge[rid]

    # Devolucions recents (senyal negatiu, es mostra però no exclou automàticament).
    devolucions_por_release: dict[uuid.UUID, int] = dict(db.execute(
        select(Item.release_id, func.count())
        .select_from(DevolucionVenta)
        .join(Item, Item.id == DevolucionVenta.item_id)
        .where(DevolucionVenta.fecha >= inici_periode)
        .group_by(Item.release_id)
    ).all())

    # Releases amb comanda ja oberta: no re-suggerir.
    releases_amb_comanda_pendent = set(db.execute(
        select(ComandaLinea.release_id)
        .join(Comanda, Comanda.id == ComandaLinea.comanda_id)
        .where(Comanda.status.in_([EstadoComanda.esborrany, EstadoComanda.enviada, EstadoComanda.rebuda_parcial]))
        .distinct()
    ).scalars().all())

    candidats = []
    for release_id, vendes in vendes_actual.items():
        if vendes == 0 or release_id in releases_amb_comanda_pendent:
            continue
        stock = stock_por_release.get(release_id, 0)
        velocitat_diaria = vendes / VENTAS_WINDOW_DAYS
        dies_estoc = stock / velocitat_diaria if velocitat_diaria > 0 else float("inf")
        if dies_estoc > URGENCIA_DIAS_ESTOC:
            continue

        release = db.get(Release, release_id)
        if release is None:
            continue

        vendes_prev = vendes_anterior.get(release_id, 0)
        if vendes > vendes_prev:
            tendencia = "accelerant"
        elif vendes < vendes_prev:
            tendencia = "frenant"
        else:
            tendencia = "estable"

        cantidad_sugerida = max(1, round(velocitat_diaria * COBERTURA_OBJECTIU_DIAS) - stock)
        prov_id, prov_nombre = _suggest_proveedor_para_release(db, release_id, release.artista)

        candidats.append(RefillSugerenciaOut(
            release_id=release_id, artista=release.artista, titulo=release.titulo, formato=release.formato,
            stock_actual=stock, vendes_periode=vendes, vendes_periode_anterior=vendes_prev,
            tendencia=tendencia, dies_estoc=round(dies_estoc, 1),
            marge_mitja=marge_por_release.get(release_id),
            devolucions_recents=devolucions_por_release.get(release_id, 0),
            cantidad_sugerida=cantidad_sugerida,
            proveedor_sugerido_id=prov_id, proveedor_sugerido_nombre=prov_nombre,
        ))

    candidats.sort(key=lambda c: (c.dies_estoc, -(c.marge_mitja or Decimal("0"))))
    return candidats


@router.post("/solicitudes-compra", status_code=201, response_model=SolicitudCompraOut)
def create_solicitud_compra(payload: SolicitudCompraIn, db: Session = Depends(get_db)):
    for linea in payload.lineas:
        if linea.release_id and db.get(Release, linea.release_id) is None:
            raise HTTPException(404, f"Release {linea.release_id} no encontrado")
        if linea.proveedor_sugerido_id and db.get(Proveedor, linea.proveedor_sugerido_id) is None:
            raise HTTPException(404, f"Proveedor {linea.proveedor_sugerido_id} no encontrado")

    solicitud = SolicitudCompra(
        origen=OrigenSolicitud(payload.origen), user_id=payload.user_id, notas=payload.notas,
    )
    db.add(solicitud)
    db.flush()
    for linea in payload.lineas:
        db.add(SolicitudCompraLinea(
            solicitud_id=solicitud.id, release_id=linea.release_id,
            artista=linea.artista, titulo=linea.titulo, sello=linea.sello, formato=linea.formato,
            cantidad=linea.cantidad, proveedor_sugerido_id=linea.proveedor_sugerido_id, notas=linea.notas,
        ))
    db.commit()
    return _solicitud_out(_get_solicitud_or_404(db, solicitud.id))


@router.get("/solicitudes-compra", response_model=list[SolicitudCompraOut])
def list_solicitudes_compra(estado: str | None = None, db: Session = Depends(get_db)):
    stmt = (
        select(SolicitudCompra)
        .options(
            selectinload(SolicitudCompra.lineas).selectinload(SolicitudCompraLinea.release),
            selectinload(SolicitudCompra.lineas).selectinload(SolicitudCompraLinea.proveedor_sugerido),
            selectinload(SolicitudCompra.user),
        )
        .order_by(SolicitudCompra.created_at.desc())
    )
    if estado:
        stmt = stmt.where(SolicitudCompra.estado == EstadoSolicitud(estado))
    solicitudes = db.scalars(stmt).all()
    return [_solicitud_out(s) for s in solicitudes]


@router.get("/solicitudes-compra/{solicitud_id}", response_model=SolicitudCompraOut)
def get_solicitud_compra(solicitud_id: uuid.UUID, db: Session = Depends(get_db)):
    return _solicitud_out(_get_solicitud_or_404(db, solicitud_id))


@router.delete("/solicitudes-compra/{solicitud_id}", status_code=204)
def delete_solicitud_compra(solicitud_id: uuid.UUID, db: Session = Depends(get_db)):
    solicitud = _get_solicitud_or_404(db, solicitud_id)
    if any(linea.comanda_linea_id is not None or linea.item_resuelto_id is not None for linea in solicitud.lineas):
        raise HTTPException(409, "No es pot eliminar: té línies ja resoltes")
    db.delete(solicitud)
    db.commit()


@router.patch("/solicitudes-compra/{solicitud_id}/cancelar", response_model=SolicitudCompraOut)
def cancelar_solicitud_compra(solicitud_id: uuid.UUID, db: Session = Depends(get_db)):
    solicitud = _get_solicitud_or_404(db, solicitud_id)
    if solicitud.estado != EstadoSolicitud.oberta:
        raise HTTPException(409, "Aquesta sol·licitud no es pot cancel·lar en el seu estat actual")
    solicitud.estado = EstadoSolicitud.cancelada
    db.commit()
    return _solicitud_out(_get_solicitud_or_404(db, solicitud.id))


@router.post("/solicitudes-compra/{solicitud_id}/lineas", status_code=201, response_model=SolicitudCompraOut)
def add_linea_solicitud(solicitud_id: uuid.UUID, payload: SolicitudCompraLineaIn, db: Session = Depends(get_db)):
    solicitud = _get_solicitud_or_404(db, solicitud_id)
    if solicitud.estado != EstadoSolicitud.oberta:
        raise HTTPException(409, "Aquesta sol·licitud no accepta noves línies en el seu estat actual")
    if payload.release_id and db.get(Release, payload.release_id) is None:
        raise HTTPException(404, f"Release {payload.release_id} no encontrado")
    if payload.proveedor_sugerido_id and db.get(Proveedor, payload.proveedor_sugerido_id) is None:
        raise HTTPException(404, f"Proveedor {payload.proveedor_sugerido_id} no encontrado")

    db.add(SolicitudCompraLinea(
        solicitud_id=solicitud.id, release_id=payload.release_id,
        artista=payload.artista, titulo=payload.titulo, sello=payload.sello, formato=payload.formato,
        cantidad=payload.cantidad, proveedor_sugerido_id=payload.proveedor_sugerido_id, notas=payload.notas,
    ))
    db.commit()
    return _solicitud_out(_get_solicitud_or_404(db, solicitud.id))


@router.delete("/solicitudes-compra/{solicitud_id}/lineas/{linea_id}", response_model=SolicitudCompraOut)
def delete_linea_solicitud(solicitud_id: uuid.UUID, linea_id: uuid.UUID, db: Session = Depends(get_db)):
    solicitud = _get_solicitud_or_404(db, solicitud_id)
    linea = next((l for l in solicitud.lineas if l.id == linea_id), None)
    if linea is None:
        raise HTTPException(404, "Línia no trobada en aquesta sol·licitud")
    if linea.comanda_linea_id is not None or linea.item_resuelto_id is not None:
        raise HTTPException(409, "No es pot eliminar: la línia ja s'ha resolt")
    db.delete(linea)
    db.commit()
    return _solicitud_out(_get_solicitud_or_404(db, solicitud.id))


@router.post("/solicitudes-compra/resolver", status_code=201, response_model=ComandaOut)
def resolver_solicitud_compra(payload: SolicitudResolverIn, db: Session = Depends(get_db)):
    """Construeix una Comanda real per a un proveïdor concret a partir de línies
    de sol·licituds seleccionades (poden venir de sol·licituds diferents). Cada
    línia ha de tenir `release_id` (si el disc encara no existeix al catàleg,
    cal donar-lo d'alta abans). Marca les línies com a resoltes i, si totes les
    línies de la seva sol·licitud ja estan resoltes, la passa a 'resolta'."""
    if db.get(Proveedor, payload.proveedor_id) is None:
        raise HTTPException(404, "Proveedor no encontrado")

    solicitud_lineas: list[SolicitudCompraLinea] = []
    for item in payload.lineas:
        linea = db.get(SolicitudCompraLinea, item.solicitud_linea_id)
        if linea is None:
            raise HTTPException(404, f"Línia de sol·licitud {item.solicitud_linea_id} no trobada")
        if linea.comanda_linea_id is not None or linea.item_resuelto_id is not None:
            raise HTTPException(409, f"La línia {item.solicitud_linea_id} ja està resolta")
        if linea.release_id is None:
            raise HTTPException(
                422,
                f"La línia '{linea.artista} - {linea.titulo}' no té release_id: "
                "cal donar d'alta el disc al catàleg abans de resoldre-la",
            )
        solicitud_lineas.append(linea)

    for intento in range(3):
        comanda = Comanda(
            proveedor_id=payload.proveedor_id, fecha=payload.fecha,
            num_comanda=_next_num_comanda(db, payload.fecha.year), notas=payload.notas,
        )
        db.add(comanda)
        try:
            db.flush()
            break
        except IntegrityError:
            db.rollback()
            if intento == 2:
                raise HTTPException(409, "No s'ha pogut generar el número de comanda, torna-ho a provar")

    lineas_por_solicitud: dict[uuid.UUID, list[SolicitudCompraLinea]] = {}
    for item, linea in zip(payload.lineas, solicitud_lineas):
        cantidad = item.cantidad if item.cantidad is not None else linea.cantidad
        comanda_linea = ComandaLinea(
            comanda_id=comanda.id, release_id=linea.release_id, cantidad=cantidad,
            precio_unitario_estimado=item.precio_unitario_estimado, notas=linea.notas,
        )
        db.add(comanda_linea)
        db.flush()
        linea.comanda_linea_id = comanda_linea.id
        lineas_por_solicitud.setdefault(linea.solicitud_id, []).append(linea)

    for solicitud_id in lineas_por_solicitud:
        solicitud = db.get(SolicitudCompra, solicitud_id)
        if all(l.comanda_linea_id is not None or l.item_resuelto_id is not None for l in solicitud.lineas):
            solicitud.estado = EstadoSolicitud.resolta

    db.commit()
    return _comanda_out(_get_comanda_or_404(db, comanda.id))


# ---------------------------------------------------------------------------
# Peticions de client (discos sense estoc demanats des del portal)
# ---------------------------------------------------------------------------

def _peticion_admin_out(p: PeticionCliente) -> PeticionClienteAdminOut:
    artista = p.release.artista if p.release else p.artista_lliure
    titulo = p.release.titulo if p.release else p.titulo_lliure
    return PeticionClienteAdminOut(
        id=p.id, user_id=p.user_id, user_nombre=p.user.nombre, user_email=p.user.email,
        canal=p.canal, release_id=p.release_id, artista=artista, titulo=titulo, estado=p.estado,
        precio_estimado=p.precio_estimado, metodo_entrega_triat=p.metodo_entrega_triat,
        notas_cliente=p.notas_cliente, notas_admin=p.notas_admin,
        solicitud_compra_linea_id=p.solicitud_compra_linea_id, order_id=p.order_id,
        pagada=p.order is not None and p.order.status == OrderStatus.pagado,
        created_at=p.created_at,
    )


def _get_peticion_or_404(db: Session, peticion_id: uuid.UUID) -> PeticionCliente:
    p = db.scalar(
        select(PeticionCliente)
        .where(PeticionCliente.id == peticion_id)
        .options(
            selectinload(PeticionCliente.release), selectinload(PeticionCliente.user),
            selectinload(PeticionCliente.order),
        )
    )
    if p is None:
        raise HTTPException(404, "Petició no trobada")
    return p


@router.get("/peticiones", response_model=list[PeticionClienteAdminOut])
def list_peticiones_admin(estado: str | None = None, db: Session = Depends(get_db)):
    stmt = (
        select(PeticionCliente)
        .options(
            selectinload(PeticionCliente.release), selectinload(PeticionCliente.user),
            selectinload(PeticionCliente.order),
        )
        .order_by(PeticionCliente.created_at.desc())
    )
    if estado:
        stmt = stmt.where(PeticionCliente.estado == EstadoPeticionCliente(estado))
    return [_peticion_admin_out(p) for p in db.scalars(stmt).all()]


@router.post("/peticiones/tienda", status_code=201, response_model=PeticionClienteAdminOut)
def crear_peticion_tienda(payload: PeticionTiendaIn, db: Session = Depends(get_db)):
    """Petició creada per l'admin en nom d'un client que truca o ve a
    mostrador: mateixa validació i punt de partida (estat 'pendent') que
    `POST /me/peticiones`, però amb canal='tienda' — això fa que
    `fijar_precio_peticion` es salti l'acceptació online del client (ja
    l'ha acceptat de paraula) i la doni per acceptada directament amb
    recollida i pagament a botiga."""
    if db.get(User, payload.user_id) is None:
        raise HTTPException(404, "Client no trobat")

    if payload.release_id:
        if db.get(Release, payload.release_id) is None:
            raise HTTPException(404, "Disc no trobat")
        stock = db.scalar(
            select(func.count()).select_from(Item)
            .where(
                Item.release_id == payload.release_id, Item.status == ItemStatus.disponible,
                Item.condicion == CondicionItem.nou, Item.cantidad > Item.cantidad_reservada,
            )
        )
        if stock:
            raise HTTPException(409, "Aquest disc ja té estoc disponible: es pot vendre directament")

    peticion = PeticionCliente(
        user_id=payload.user_id, canal="tienda", release_id=payload.release_id,
        artista_lliure=payload.artista_lliure, titulo_lliure=payload.titulo_lliure,
        notas_cliente=payload.notas_cliente,
    )
    db.add(peticion)
    db.commit()
    return _peticion_admin_out(_get_peticion_or_404(db, peticion.id))


@router.get("/peticiones/reserves-recollida", response_model=list[ReservaRecollidaOut])
def list_reserves_recollida(db: Session = Depends(get_db)):
    """Peticions reservades a recollir I PAGAR a botiga (Via 2): el TPV les
    mostra a la pestanya 'Reserves web' perquè el mostrador les trobi sense
    haver de saber l'item_id de memòria — la venda mateixa es fa amb
    POST /admin/ventas-externas com sempre."""
    release_expired(db)
    peticiones = db.scalars(
        select(PeticionCliente)
        .where(
            PeticionCliente.estado == EstadoPeticionCliente.reservada,
            PeticionCliente.metodo_entrega_triat == "recollida_paga_botiga",
        )
        .options(
            selectinload(PeticionCliente.release), selectinload(PeticionCliente.user),
            selectinload(PeticionCliente.item),
        )
        .order_by(PeticionCliente.updated_at)
    ).all()
    return [
        ReservaRecollidaOut(
            peticion_id=p.id, item_id=p.item.id, artista=p.release.artista, titulo=p.release.titulo,
            imagen_url=p.release.imagen_url, precio=p.item.precio, condicion=p.item.condicion,
            estado_disco=p.item.estado_disco, user_id=p.user.id, user_nombre=p.user.nombre,
            user_email=p.user.email, reserved_until=p.item.reserved_until,
        )
        for p in peticiones
        if p.item is not None and p.release is not None
    ]


@router.patch("/peticiones/{peticion_id}/catalogar", response_model=PeticionClienteAdminOut)
def catalogar_peticion(peticion_id: uuid.UUID, payload: PeticionCatalogarIn, db: Session = Depends(get_db)):
    """Per a peticions fora de catàleg (text lliure): enllaça-la a un release
    ja donat d'alta (l'admin l'ha buscat/creat a Discogs des del seu propi
    panell, com sempre — el client mai toca Discogs). Es pot fer servir per
    corregir un mal enllaç mentre la petició encara no s'hagi acceptat
    (pendent o pendent_acceptacio); si ja tenia preu fixat i el disc canvia
    de veritat, es torna a 'pendent' i s'esborra el preu — no té sentit
    mantenir un preu calculat per a un disc diferent."""
    peticion = _get_peticion_or_404(db, peticion_id)
    if peticion.estado not in (EstadoPeticionCliente.pendent, EstadoPeticionCliente.pendent_acceptacio):
        raise HTTPException(409, "Només es pot modificar el disc abans que el client accepti la petició")
    if db.get(Release, payload.release_id) is None:
        raise HTTPException(404, "Release no trobat")

    canvia_disc = peticion.release_id != payload.release_id
    peticion.release_id = payload.release_id
    if canvia_disc and peticion.estado == EstadoPeticionCliente.pendent_acceptacio:
        peticion.precio_estimado = None
        peticion.estado = EstadoPeticionCliente.pendent
    db.commit()
    return _peticion_admin_out(_get_peticion_or_404(db, peticion.id))


def _link_un_clic_a_peticions(db: Session, email: str, lang: str = "ca") -> str:
    """Magic link (14 dies de caducitat) que porta directament a "Les meves
    peticions" ja loguejat — perquè el client pugui acceptar el preu amb un
    sol clic des de l'email, sense haver de fer login a part."""
    raw = create_magic_link_token(db, email, timedelta(days=14))
    return f"{frontend_url('/auth/magic', lang)}?token={raw}&next=/compte/peticions"


@router.patch("/peticiones/{peticion_id}/precio", response_model=PeticionClienteAdminOut)
def fijar_precio_peticion(peticion_id: uuid.UUID, payload: PeticionPrecioIn, db: Session = Depends(get_db)):
    """Fixa el preu estimat. Petició web: notifica el client per email
    perquè l'accepti o el rebutgi des del seu compte, abans de comprar res
    al proveïdor. Petició de tienda (trucada o mostrador): el client ja ha
    acceptat el preu de paraula, així que es salta aquest pas — passa
    directament a 'acceptada' amb recollida i pagament a botiga."""
    peticion = _get_peticion_or_404(db, peticion_id)
    if peticion.estado != EstadoPeticionCliente.pendent:
        raise HTTPException(409, "Aquesta petició no està en estat pendent")
    if peticion.release_id is None:
        raise HTTPException(422, "Cal catalogar el disc (release_id) abans de fixar preu")

    peticion.precio_estimado = payload.precio_estimado

    if peticion.canal == "tienda":
        peticion.estado = EstadoPeticionCliente.acceptada
        peticion.metodo_entrega_triat = "recollida_paga_botiga"
        db.commit()
        return _peticion_admin_out(_get_peticion_or_404(db, peticion.id))

    peticion.estado = EstadoPeticionCliente.pendent_acceptacio
    db.commit()
    db.refresh(peticion)

    disco = f"{peticion.release.artista} - {peticion.release.titulo}"
    lang = peticion.user.idioma
    link = _link_un_clic_a_peticions(db, peticion.user.email, lang)
    nombre = peticion.user.nombre or ""
    precio = payload.precio_estimado
    send_email(
        to=peticion.user.email,
        subject=translate(db, "email.peticion_price_ready.subject", lang, disco=disco),
        body=translate(db, "email.peticion_price_ready.body_text", lang, nombre=nombre, disco=disco, precio=precio, link=link),
        html=render_email_html(
            translate(db, "email.peticion_price_ready.heading", lang),
            translate(db, "email.peticion_price_ready.body_html", lang, disco=disco, precio=precio),
            cta=(translate(db, "email.peticion_price_ready.cta", lang), link),
        ),
    )
    return _peticion_admin_out(_get_peticion_or_404(db, peticion.id))


@router.post("/peticiones/{peticion_id}/vincular-solicitud", status_code=201, response_model=SolicitudCompraOut)
def vincular_peticion_a_solicitud(peticion_id: uuid.UUID, payload: PeticionVincularIn, db: Session = Depends(get_db)):
    """Un cop el client ha acceptat el preu: crea una SolicitudCompra
    (origen='peticion_cliente') amb una línia per aquest release, per
    continuar amb el flux normal (resoldre-la cap a una Comanda, com sempre)."""
    peticion = _get_peticion_or_404(db, peticion_id)
    if peticion.estado != EstadoPeticionCliente.acceptada:
        raise HTTPException(409, "Només es pot vincular una petició ja acceptada pel client")
    if peticion.release_id is None:
        raise HTTPException(422, "La petició no té un disc catalogat")

    solicitud = SolicitudCompra(
        origen=OrigenSolicitud.peticion_cliente, notas=f"Petició de {peticion.user.email}",
    )
    db.add(solicitud)
    db.flush()
    linea = SolicitudCompraLinea(
        solicitud_id=solicitud.id, release_id=peticion.release_id,
        cantidad=payload.cantidad, proveedor_sugerido_id=payload.proveedor_sugerido_id,
    )
    db.add(linea)
    db.flush()

    peticion.solicitud_compra_linea_id = linea.id
    peticion.estado = EstadoPeticionCliente.en_tramit
    db.commit()
    return _solicitud_out(_get_solicitud_or_404(db, solicitud.id))


def _completar_order_pagada(db: Session, peticion: PeticionCliente, item: Item) -> bool:
    """Envio / recollida_paga_ara: el client ja va pagar en acceptar (veure
    me.py, aceptar_peticion), amb una Order que té una línia 'de reserva'
    (item_id=None). Si la trobem, hi assignem l'exemplar real ara (calculant
    l'IVA, que abans no es podia saber) i la petició queda 'recollida'
    directament — no cal cap pas més del client.

    Retorna False si no hi ha cap Order pagada esperant (petició anterior a
    aquesta funcionalitat, o el pagament encara no s'ha completat): en
    aquest cas cal caure al camí antic (reservar i esperar "Comprar ara")."""
    if peticion.order_id is None:
        return False
    order = db.get(Order, peticion.order_id)
    if order is None or order.status != OrderStatus.pagado:
        return False
    linia = db.scalar(
        select(OrderItem).where(OrderItem.order_id == order.id, OrderItem.item_id.is_(None))
    )
    if linia is None:
        return False

    if item.condicion == CondicionItem.nou:
        result = db.execute(
            update(Item)
            .where(Item.id == item.id, Item.cantidad - Item.cantidad_reservada >= 1)
            .values(cantidad=Item.cantidad - 1)
            .execution_options(synchronize_session=False)
        )
    else:
        result = db.execute(
            update(Item)
            .where(Item.id == item.id, Item.status == ItemStatus.disponible)
            .values(status=ItemStatus.vendido, reserved_until=None)
            .execution_options(synchronize_session=False)
        )
    if result.rowcount == 0:
        raise HTTPException(409, "Aquest exemplar ja no està disponible")

    tipus_iva_id, iva_pct, iva_import = compute_iva_venda(item, linia.precio, db)
    linia.item_id = item.id
    linia.release_id = None
    linia.condicion = item.condicion
    linia.cantidad = 1
    linia.tipus_iva_id = tipus_iva_id
    linia.iva_pct = iva_pct
    linia.iva_import = iva_import

    peticion.item_id = item.id
    peticion.estado = EstadoPeticionCliente.recollida

    # El listing virtual de nou es retira sol quan `cantidad` arriba a 0
    # (ver services/discogs_sync.sync_stock_listing); aquí només cal fer-ho
    # explícit per a segona_ma, que és 1 còpia = 1 listing sempre.
    if item.condicion != CondicionItem.nou and item.codi_discogs:
        remove_item_from_discogs(item.codi_discogs)

    return True


def _reservar_item_para_peticion(db: Session, peticion: PeticionCliente, item: Item) -> None:
    """Assigna `item` a `peticion`, aplicant la bifurcació que el client ja
    va triar en acceptar (`metodo_entrega_triat`):
    - envio / recollida_paga_ara: si ja hi ha una Order pagada esperant
      (cas normal, veure `_completar_order_pagada`), s'hi assigna
      l'exemplar i la petició queda 'recollida' d'una vegada. Si no (cas
      antic, abans del pagament en acceptar), es reserva sense caducitat i
      el client l'ha de comprar des del seu compte com abans.
    - recollida_paga_botiga: reserva de 72h (Via 2); si no ve a recollir-lo
      i pagar-lo, s'allibera sol i la petició caduca.
    NO fa commit: qui la crida ha de fer-ho, per poder incloure en la
    mateixa transacció altres canvis (p.ex. tancar la línia de la
    sol·licitud de compra associada)."""
    if peticion.estado != EstadoPeticionCliente.en_tramit:
        raise HTTPException(409, "Aquesta petició no està en tràmit")
    if peticion.metodo_entrega_triat is None:
        raise HTTPException(422, "La petició no té mètode d'entrega triat")
    if item.release_id != peticion.release_id:
        raise HTTPException(422, "Aquest exemplar no correspon al disc de la petició")

    if peticion.metodo_entrega_triat != "recollida_paga_botiga":
        if _completar_order_pagada(db, peticion, item):
            return

    es_recollida_sense_pagar = peticion.metodo_entrega_triat == "recollida_paga_botiga"
    reserved_until = (
        datetime.now(timezone.utc) + timedelta(hours=72) if es_recollida_sense_pagar else None
    )
    if item.condicion == CondicionItem.nou:
        # Igual patró que reserve_stock (services/reservations.py) però SENSE
        # commit: cal poder-ho incloure a la mateixa transacció que la resta
        # de `recibir_comanda`/`vincular_item_peticion`.
        result = db.execute(
            update(Item)
            .where(Item.id == item.id, Item.cantidad - Item.cantidad_reservada >= 1)
            .values(cantidad_reservada=Item.cantidad_reservada + 1)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount == 0:
            raise HTTPException(409, "Aquest exemplar ja no està disponible")
        db.add(StockHold(item_id=item.id, cantidad=1, peticion_id=peticion.id, reserved_until=reserved_until))
    else:
        result = db.execute(
            update(Item)
            .where(Item.id == item.id, Item.status == ItemStatus.disponible)
            .values(status=ItemStatus.reservado, reserved_for_peticion_id=peticion.id, reserved_until=reserved_until)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount == 0:
            raise HTTPException(409, "Aquest exemplar ja no està disponible")

    peticion.item_id = item.id
    peticion.estado = EstadoPeticionCliente.reservada


def _enviar_email_item_arribat(db: Session, peticion: PeticionCliente) -> None:
    disco = f"{peticion.release.artista} - {peticion.release.titulo}"
    lang = peticion.user.idioma
    necessita_accio = peticion.estado != EstadoPeticionCliente.recollida
    link = _link_un_clic_a_peticions(db, peticion.user.email, lang) if necessita_accio else None

    if peticion.estado == EstadoPeticionCliente.recollida:
        key = "email.peticion_arrived.paid_ship" if peticion.metodo_entrega_triat == "envio" else "email.peticion_arrived.paid_pickup"
        cos = translate(db, key, lang, disco=disco)
    elif peticion.metodo_entrega_triat == "recollida_paga_botiga":
        cos = translate(db, "email.peticion_arrived.pay_in_store", lang, disco=disco, link=link)
    else:
        key = "email.peticion_arrived.complete_ship" if peticion.metodo_entrega_triat == "envio" else "email.peticion_arrived.complete_pickup"
        cos = translate(db, key, lang, disco=disco, link=link)

    send_email(
        to=peticion.user.email,
        subject=translate(db, "email.peticion_arrived.subject", lang, disco=disco),
        body=cos,
        html=render_email_html(
            translate(db, "email.peticion_arrived.heading", lang),
            f'<p style="font-size:14px;line-height:1.5">{cos}</p>',
            cta=(translate(db, "email.peticion_arrived.cta", lang), link) if link else None,
        ),
    )


def _tancar_linea_solicitud_desde_stock(db: Session, linea: SolicitudCompraLinea, item: Item) -> None:
    """Marca la línia de sol·licitud com a resolta amb un exemplar d'estoc
    (sense compra) i, si totes les línies de la sol·licitud ja estan
    resoltes, la passa a 'resolta'."""
    linea.item_resuelto_id = item.id
    solicitud = db.get(SolicitudCompra, linea.solicitud_id)
    if all(l.comanda_linea_id is not None or l.item_resuelto_id is not None for l in solicitud.lineas):
        solicitud.estado = EstadoSolicitud.resolta


@router.post("/peticiones/{peticion_id}/vincular-item", response_model=PeticionClienteAdminOut)
def vincular_item_peticion(
    peticion_id: uuid.UUID, payload: PeticionVincularItemIn, db: Session = Depends(get_db),
):
    """Quan arriba l'exemplar demanat per una via que no passa per la
    recepció normal d'una comanda (per exemple, ja hi havia un exemplar a
    estoc): l'hi vincula a mà. Si la petició ve d'una sol·licitud de
    compra, també la tanca (evita que es quedi oberta per sempre)."""
    peticion = _get_peticion_or_404(db, peticion_id)
    item = db.get(Item, payload.item_id)
    if item is None:
        raise HTTPException(404, "Exemplar no trobat")

    _reservar_item_para_peticion(db, peticion, item)

    if peticion.solicitud_compra_linea_id is not None:
        linea = db.get(SolicitudCompraLinea, peticion.solicitud_compra_linea_id)
        if linea is not None and linea.comanda_linea_id is None and linea.item_resuelto_id is None:
            _tancar_linea_solicitud_desde_stock(db, linea, item)

    db.commit()
    db.refresh(peticion)
    _enviar_email_item_arribat(db, peticion)

    return _peticion_admin_out(_get_peticion_or_404(db, peticion.id))


@router.post("/solicitudes-compra/lineas/{linea_id}/resoldre-estoc", response_model=SolicitudCompraOut)
def resolver_linea_desde_stock(linea_id: uuid.UUID, payload: ResoldreEstocIn, db: Session = Depends(get_db)):
    """Tanca una línia de sol·licitud SENSE comprar-la a proveïdor, perquè
    ja hi ha un exemplar disponible a estoc. Si la sol·licitud ve d'una
    petició de client, reserva aquest exemplar per a la petició (mateixa
    bifurcació Via 1/Via 2 que `vincular_item_peticion`) i avisa el client
    per email; si no, només tanca la línia (p.ex. refill_stock o manual:
    ja no cal comprar-ho)."""
    linea = db.get(SolicitudCompraLinea, linea_id)
    if linea is None:
        raise HTTPException(404, "Línia no trobada")
    if linea.comanda_linea_id is not None or linea.item_resuelto_id is not None:
        raise HTTPException(409, "Aquesta línia ja està resolta")
    if linea.release_id is None:
        raise HTTPException(422, "Cal un release per resoldre una línia des d'estoc")

    solicitud = db.get(SolicitudCompra, linea.solicitud_id)
    if solicitud.estado != EstadoSolicitud.oberta:
        raise HTTPException(409, "Aquesta sol·licitud no està oberta")

    item = db.get(Item, payload.item_id)
    if item is None:
        raise HTTPException(404, "Exemplar no trobat")
    if item.release_id != linea.release_id:
        raise HTTPException(422, "Aquest exemplar no correspon al disc de la línia")

    peticion = None
    if solicitud.origen == OrigenSolicitud.peticion_cliente:
        peticion = db.scalar(
            select(PeticionCliente)
            .where(
                PeticionCliente.solicitud_compra_linea_id == linea.id,
                PeticionCliente.estado == EstadoPeticionCliente.en_tramit,
            )
            .options(selectinload(PeticionCliente.release), selectinload(PeticionCliente.user))
        )
        if peticion is None:
            raise HTTPException(422, "No s'ha trobat la petició de client associada a aquesta línia")
        _reservar_item_para_peticion(db, peticion, item)
    elif item.condicion != CondicionItem.nou:
        # Marca la còpia com a reservada sense caducitat (l'admin la gestiona
        # a mà); per a nou no cal tocar res, l'estoc agregat no es
        # "reserva" per aquest motiu administratiu, només es fa constar que
        # ja no cal comprar-ho (veure _tancar_linea_solicitud_desde_stock).
        result = db.execute(
            update(Item)
            .where(Item.id == item.id, Item.status == ItemStatus.disponible)
            .values(status=ItemStatus.reservado)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount == 0:
            raise HTTPException(409, "Aquest exemplar ja no està disponible")

    _tancar_linea_solicitud_desde_stock(db, linea, item)
    db.commit()

    if peticion is not None:
        db.refresh(peticion)
        _enviar_email_item_arribat(db, peticion)

    return _solicitud_out(_get_solicitud_or_404(db, solicitud.id))


@router.patch("/peticiones/{peticion_id}/cancelar", response_model=PeticionClienteAdminOut)
def cancelar_peticion_admin(peticion_id: uuid.UUID, db: Session = Depends(get_db)):
    peticion = _get_peticion_or_404(db, peticion_id)
    if peticion.estado in (EstadoPeticionCliente.recollida, EstadoPeticionCliente.cancelada):
        raise HTTPException(409, "Aquesta petició no es pot cancel·lar en el seu estat actual")
    peticion.estado = EstadoPeticionCliente.cancelada
    db.commit()
    return _peticion_admin_out(_get_peticion_or_404(db, peticion.id))


# ---------------------------------------------------------------------------
# Ventas externas: TPV mostrador + Discogs
# ---------------------------------------------------------------------------

def _iva_articulo_manual(db: Session, tipus_iva_id: int, precio_venta: Decimal) -> tuple[int, Decimal, Decimal]:
    """Un article manual no té `Item` del qual deduir el règim d'IVA (nou vs
    REBU): el tria l'admin a mà entre els tipus configurats. REBU es basa en
    el marge sobre un cost d'adquisició que un article manual no té, així
    que no és una opció vàlida aquí."""
    tipus = db.get(TipusIva, tipus_iva_id)
    if tipus is None or not tipus.actiu:
        raise HTTPException(404, "Tipus d'IVA no trobat o inactiu")
    if tipus.es_rebu:
        raise HTTPException(422, "Aquest tipus d'IVA és de règim REBU (marge) i no és aplicable a un article manual")
    if precio_venta <= 0:
        return tipus.id, tipus.percentatge, Decimal("0.00")
    pct = tipus.percentatge
    iva_import = (precio_venta * pct / (Decimal("100") + pct)).quantize(Decimal("0.01"))
    return tipus.id, pct, iva_import


def _crear_linia_venta(
    db: Session,
    *,
    ticket_id: uuid.UUID,
    item_id: uuid.UUID | None,
    descripcion: str | None,
    tipus_iva_id: int | None,
    canal: str,
    metodo_pago: str,
    precio_venta: Decimal,
    fecha: datetime,
    nombre_cliente: str | None,
    user_id: uuid.UUID | None,
    discogs_sale_id: int | None = None,
    notas: str | None = None,
    cantidad: int = 1,
) -> tuple[VentaExterna, Item | None]:
    """Crea una VentaExterna (sin commitear: quien llama decide cuándo, para
    poder agrupar varias líneas en una sola transacción — venta de un item
    suelto, o de un lote). `ticket_id` lo decide siempre el caller: el mismo
    valor para todas las líneas de un lote, uno nuevo para una venta suelta.
    Dos casos:
    - item_id presente: venda de catàleg, reserva atòmica de l'ejemplar.
      Per a nou, `cantidad` és quantes unitats es venen d'aquesta línia
      (descompta `Item.cantidad` en comptes de canviar `status`, que a nou
      no representa res); per a segona_ma sempre és 1.
    - item_id ausent: article manual (llibre, samarreta...), sense estoc
      que reservar; l'IVA es tria a mà (veure `_iva_articulo_manual`)."""
    if item_id is None:
        tipus_iva_id_calc, iva_pct, iva_import = _iva_articulo_manual(db, tipus_iva_id, precio_venta)
        venta = VentaExterna(
            ticket_id=ticket_id,
            item_id=None,
            descripcion=descripcion,
            canal=CanalVenta(canal),
            metodo_pago=MetodoPago(metodo_pago),
            precio_venta=precio_venta,
            fecha=fecha,
            nombre_cliente=nombre_cliente,
            user_id=user_id,
            discogs_sale_id=discogs_sale_id,
            notas=notas,
            tipus_iva_id=tipus_iva_id_calc,
            iva_pct=iva_pct,
            iva_import=iva_import,
        )
        db.add(venta)
        db.flush()
        return venta, None

    # Una PeticionCliente en Via 2 (recollida_paga_botiga) reté l'ítem amb
    # status='reservado' (segona_ma) o un StockHold (nou): cal saber-ho
    # ABANS de vendre, que el buidarà si té èxit.
    peticion_vinculada = db.scalar(
        select(PeticionCliente).where(
            PeticionCliente.item_id == item_id, PeticionCliente.estado == EstadoPeticionCliente.reservada,
        )
    )
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "Ejemplar no encontrado")

    if item.condicion == CondicionItem.nou:
        hold_peticion = (
            db.scalar(select(StockHold).where(StockHold.item_id == item_id, StockHold.peticion_id == peticion_vinculada.id))
            if peticion_vinculada else None
        )
        if hold_peticion is not None:
            if hold_peticion.cantidad != cantidad:
                raise HTTPException(409, "La reserva d'aquesta petició no coincideix amb la quantitat a vendre")
            result = db.execute(
                update(Item)
                .where(Item.id == item_id, Item.cantidad >= cantidad, Item.cantidad_reservada >= cantidad)
                .values(cantidad=Item.cantidad - cantidad, cantidad_reservada=Item.cantidad_reservada - cantidad)
                .execution_options(**_NO_SYNC)
            )
            if result.rowcount == 1:
                db.delete(hold_peticion)
        else:
            result = db.execute(
                update(Item)
                .where(Item.id == item_id, Item.cantidad - Item.cantidad_reservada >= cantidad)
                .values(cantidad=Item.cantidad - cantidad)
                .execution_options(**_NO_SYNC)
            )
        if result.rowcount == 0:
            raise HTTPException(409, f"No hi ha prou stock per vendre {cantidad} unitats")
        db.refresh(item)
        sync_stock_listing(db, item)
    else:
        # Reserva atómica: disponible, o retingut per aquesta petició concreta.
        result = db.execute(
            update(Item)
            .where(
                Item.id == item_id,
                or_(
                    Item.status == ItemStatus.disponible,
                    and_(Item.status == ItemStatus.reservado, Item.reserved_for_peticion_id.isnot(None)),
                ),
            )
            .values(
                status=ItemStatus.retirado, reserved_until=None,
                reserved_by_cart_id=None, reserved_for_peticion_id=None,
            )
            .execution_options(**_NO_SYNC)
        )
        if result.rowcount == 0:
            raise HTTPException(409, f"Ejemplar no disponible (estado actual: {item.status})")

    if peticion_vinculada:
        peticion_vinculada.estado = EstadoPeticionCliente.recollida

    # precio_venta es el TOTAL cobrado por la línea (todas las unidades),
    # no por unidad — igual criterio que ya asumían los informes de
    # comptabilitat.py que suman VentaExterna.precio_venta directamente.
    tipus_iva_id_calc, iva_pct, iva_import = compute_iva_venda(item, precio_venta, db)
    venta = VentaExterna(
        ticket_id=ticket_id,
        item_id=item_id,
        condicion=item.condicion,
        cantidad=cantidad,
        canal=CanalVenta(canal),
        metodo_pago=MetodoPago(metodo_pago),
        precio_venta=precio_venta,
        fecha=fecha,
        nombre_cliente=nombre_cliente,
        user_id=user_id,
        discogs_sale_id=discogs_sale_id,
        notas=notas,
        tipus_iva_id=tipus_iva_id_calc,
        iva_pct=iva_pct,
        iva_import=iva_import,
    )
    db.add(venta)
    db.flush()
    return venta, item


def _venta_externa_out(venta: VentaExterna, item: Item | None) -> VentaExternaOut:
    return VentaExternaOut(
        id=venta.id,
        ticket_id=venta.ticket_id,
        item_id=venta.item_id,
        descripcion=venta.descripcion,
        canal=venta.canal,
        metodo_pago=venta.metodo_pago,
        precio_venta=venta.precio_venta,
        coste_adquisicion=item.coste_adquisicion if item else None,
        fecha=venta.fecha,
        nombre_cliente=venta.nombre_cliente,
        user_id=venta.user_id,
        user_nom=venta.client.nombre if venta.client else None,
        discogs_sale_id=venta.discogs_sale_id,
        notas=venta.notas,
        created_at=venta.created_at,
        tipus_iva_id=venta.tipus_iva_id,
        iva_pct=venta.iva_pct,
        iva_import=venta.iva_import,
        cantidad=venta.cantidad,
        condicion=venta.condicion.value if venta.condicion else None,
        artista=item.release.artista if item else None,
        titulo=item.release.titulo if item else None,
    )


@router.post("/ventas-externas", status_code=201, response_model=VentaExternaOut)
def create_venta_externa(payload: VentaExternaIn, db: Session = Depends(get_db)):
    release_expired(db)
    venta, item = _crear_linia_venta(
        db,
        ticket_id=uuid.uuid4(),
        item_id=payload.item_id,
        descripcion=payload.descripcion,
        tipus_iva_id=payload.tipus_iva_id,
        canal=payload.canal,
        metodo_pago=payload.metodo_pago,
        precio_venta=payload.precio_venta,
        fecha=payload.fecha,
        nombre_cliente=payload.nombre_cliente,
        user_id=payload.user_id,
        discogs_sale_id=payload.discogs_sale_id,
        notas=payload.notas,
        cantidad=payload.cantidad,
    )
    db.commit()
    db.refresh(venta)
    return _venta_externa_out(venta, item)


@router.post("/ventas-externas/lote", status_code=201, response_model=list[VentaExternaOut])
def create_venta_externa_lote(payload: VentaExternaLoteIn, db: Session = Depends(get_db)):
    """Vende varios ejemplares (discos distintos, o varias copias del mismo
    álbum, o articles manuals) en una sola operación de TPV: si alguna línea
    falla (ejemplar ya no disponible, tipo de IVA inválido...), no se
    commitea nada del lote — o se cobran todos, o ninguno."""
    release_expired(db)
    ticket_id = uuid.uuid4()
    pendientes: list[tuple[VentaExterna, Item | None]] = []
    for linea in payload.lineas:
        venta, item = _crear_linia_venta(
            db,
            ticket_id=ticket_id,
            item_id=linea.item_id,
            descripcion=linea.descripcion,
            tipus_iva_id=linea.tipus_iva_id,
            canal=payload.canal,
            metodo_pago=payload.metodo_pago,
            precio_venta=linea.precio_venta,
            fecha=payload.fecha,
            nombre_cliente=payload.nombre_cliente,
            user_id=payload.user_id,
            notas=payload.notas,
            cantidad=linea.cantidad,
        )
        pendientes.append((venta, item))

    db.commit()
    for venta, _ in pendientes:
        db.refresh(venta)
    return [_venta_externa_out(venta, item) for venta, item in pendientes]


@router.patch("/ventas-externas/tickets/{ticket_id}/usuari", response_model=list[VentaExternaOut])
def vincular_usuari_ticket(ticket_id: uuid.UUID, payload: VincularUsuariTicketIn, db: Session = Depends(get_db)):
    """Vincula (o, amb user_id=None, desvincula) un usuari registrat a totes
    les línies d'un tiquet ja cobrat. No canvia cap altra dada de la venda
    (preu, IVA, estoc...) — només qui hi queda associat."""
    ventas = db.scalars(select(VentaExterna).where(VentaExterna.ticket_id == ticket_id)).all()
    if not ventas:
        raise HTTPException(404, "Tiquet no trobat")
    if payload.user_id is not None and db.get(User, payload.user_id) is None:
        raise HTTPException(404, "Usuari no trobat")

    for venta in ventas:
        venta.user_id = payload.user_id
    db.commit()

    result = []
    for venta in ventas:
        db.refresh(venta)
        item = db.get(Item, venta.item_id) if venta.item_id else None
        result.append(_venta_externa_out(venta, item))
    return result


@router.get("/ventas-externas", response_model=list[VentaExternaOut])
def list_ventas_externas(
    canal: str | None = None,
    metodo_pago: str | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
):
    stmt = (
        select(VentaExterna)
        .options(
            selectinload(VentaExterna.item).selectinload(Item.release),
            selectinload(VentaExterna.client),
        )
        .order_by(VentaExterna.fecha.desc())
    )
    if canal:
        stmt = stmt.where(VentaExterna.canal == canal)
    if metodo_pago:
        stmt = stmt.where(VentaExterna.metodo_pago == metodo_pago)
    if desde:
        stmt = stmt.where(VentaExterna.fecha >= desde)
    if hasta:
        stmt = stmt.where(VentaExterna.fecha <= hasta)
    ventas = db.scalars(stmt).all()

    # Filtro de texto sobre artista/título/descripción (client-friendly: hacerlo en Python)
    if q:
        ql = q.lower()
        ventas = [
            v for v in ventas
            if (v.item and v.item.release and (
                ql in v.item.release.artista.lower() or ql in v.item.release.titulo.lower()
            ))
            or (v.descripcion and ql in v.descripcion.lower())
            or (v.nombre_cliente and ql in v.nombre_cliente.lower())
        ]

    returned = set(db.scalars(
        select(DevolucionVenta.venta_externa_id)
        .where(DevolucionVenta.venta_externa_id.in_([v.id for v in ventas]))
    ).all())
    return [
        VentaExternaOut(
            id=v.id,
            ticket_id=v.ticket_id,
            item_id=v.item_id,
            descripcion=v.descripcion,
            canal=v.canal,
            metodo_pago=v.metodo_pago,
            precio_venta=v.precio_venta,
            coste_adquisicion=v.item.coste_adquisicion if v.item else None,
            fecha=v.fecha,
            nombre_cliente=v.nombre_cliente,
            user_id=v.user_id,
            user_nom=v.client.nombre if v.client else None,
            discogs_sale_id=v.discogs_sale_id,
            notas=v.notas,
            created_at=v.created_at,
            tipus_iva_id=v.tipus_iva_id,
            iva_pct=v.iva_pct,
            iva_import=v.iva_import,
            artista=v.item.release.artista if v.item and v.item.release else None,
            titulo=v.item.release.titulo if v.item and v.item.release else None,
            devuelta=v.id in returned,
        )
        for v in ventas
    ]


# ---------------------------------------------------------------------------
# Caja (control de efectivo)
# ---------------------------------------------------------------------------

def _mov_totals(session_id: uuid.UUID, db: Session) -> tuple:
    """Returns (total_entrades, total_sortides) from caja_movimientos for a session."""
    from decimal import Decimal as D
    movs = db.scalars(
        select(CajaMovimiento).where(CajaMovimiento.session_id == session_id)
    ).all()
    entrades = sum((m.importe for m in movs if m.tipo == TipoMovimiento.entrada), D("0"))
    sortides = sum((m.importe for m in movs if m.tipo == TipoMovimiento.salida), D("0"))
    return entrades, sortides


def _caja_out(s: CajaSession, total_entrades=None, total_sortides=None) -> CajaSessionOut:
    from decimal import Decimal as D
    te = total_entrades if total_entrades is not None else (s.total_entradas or D("0"))
    ts = total_sortides if total_sortides is not None else (s.total_salidas or D("0"))
    diferencia = None
    if s.conteo_real is not None and s.total_ventas_efectivo is not None:
        diferencia = s.conteo_real - s.fondo_inicial - s.total_ventas_efectivo - te + ts
    return CajaSessionOut(
        id=s.id,
        fecha_apertura=s.fecha_apertura,
        fondo_inicial=s.fondo_inicial,
        fecha_cierre=s.fecha_cierre,
        total_ventas_efectivo=s.total_ventas_efectivo,
        total_entradas=te,
        total_salidas=ts,
        conteo_real=s.conteo_real,
        diferencia=diferencia,
        notas=s.notas,
        created_at=s.created_at,
    )


@router.post("/caja/apertura", status_code=201, response_model=CajaSessionOut)
def abrir_caja(payload: CajaSessionIn, db: Session = Depends(get_db)):
    sesion_activa = db.scalar(
        select(CajaSession).where(CajaSession.fecha_cierre.is_(None))
        .order_by(CajaSession.fecha_apertura.desc())
    )
    if sesion_activa:
        raise HTTPException(409, "Ya hay una sesión de caja abierta")
    s = CajaSession(
        fecha_apertura=payload.fecha_apertura,
        fondo_inicial=payload.fondo_inicial,
        notas=payload.notas,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    from decimal import Decimal as D
    return _caja_out(s, D("0"), D("0"))


@router.post("/caja/cierre/{session_id}", response_model=CajaSessionOut)
def cerrar_caja(session_id: uuid.UUID, payload: CajaCierreIn, db: Session = Depends(get_db)):
    s = db.get(CajaSession, session_id)
    if s is None:
        raise HTTPException(404, "Sesión de caja no encontrada")
    if s.fecha_cierre is not None:
        raise HTTPException(409, "La sesión ya está cerrada")

    ventas_efectivo = db.scalars(
        select(VentaExterna).where(
            VentaExterna.metodo_pago == MetodoPago.efectivo,
            VentaExterna.fecha >= s.fecha_apertura,
        )
    ).all()
    total = sum(v.precio_venta for v in ventas_efectivo)

    te, ts = _mov_totals(session_id, db)

    s.fecha_cierre = datetime.now(timezone.utc)
    s.total_ventas_efectivo = total
    s.total_entradas = te
    s.total_salidas = ts
    s.conteo_real = payload.conteo_real
    if payload.notas:
        s.notas = payload.notas
    db.commit()
    db.refresh(s)
    return _caja_out(s, te, ts)


@router.get("/caja/activa", response_model=CajaSessionOut | None)
def get_caja_activa(db: Session = Depends(get_db)):
    s = db.scalar(
        select(CajaSession).where(CajaSession.fecha_cierre.is_(None))
        .order_by(CajaSession.fecha_apertura.desc())
    )
    if s is None:
        return None
    te, ts = _mov_totals(s.id, db)
    return _caja_out(s, te, ts)


@router.get("/caja/sessions", response_model=list[CajaSessionOut])
def list_caja_sessions(db: Session = Depends(get_db)):
    sessions = db.scalars(
        select(CajaSession).order_by(CajaSession.fecha_apertura.desc())
    ).all()
    return [_caja_out(s) for s in sessions]


# ---------------------------------------------------------------------------
# Moviments de caixa (entrades i sortides manuals)
# ---------------------------------------------------------------------------

@router.post("/caja/movimientos", status_code=201, response_model=CajaMovimientoOut)
def create_movimiento(payload: CajaMovimientoIn, db: Session = Depends(get_db)):
    sesion = db.scalar(
        select(CajaSession).where(CajaSession.fecha_cierre.is_(None))
        .order_by(CajaSession.fecha_apertura.desc())
    )
    if sesion is None:
        raise HTTPException(409, "No hay ninguna sesión de caja abierta")
    mov = CajaMovimiento(
        session_id=sesion.id,
        tipo=TipoMovimiento(payload.tipo),
        concepto=payload.concepto,
        importe=payload.importe,
        fecha=payload.fecha,
    )
    db.add(mov)
    db.commit()
    db.refresh(mov)
    return mov


@router.get("/caja/movimientos", response_model=list[CajaMovimientoOut])
def list_movimientos_activa(db: Session = Depends(get_db)):
    sesion = db.scalar(
        select(CajaSession).where(CajaSession.fecha_cierre.is_(None))
        .order_by(CajaSession.fecha_apertura.desc())
    )
    if sesion is None:
        return []
    return db.scalars(
        select(CajaMovimiento)
        .where(CajaMovimiento.session_id == sesion.id)
        .order_by(CajaMovimiento.fecha)
    ).all()


@router.get("/caja/sessions/{session_id}/movimientos", response_model=list[CajaMovimientoOut])
def list_movimientos_session(session_id: uuid.UUID, db: Session = Depends(get_db)):
    if db.get(CajaSession, session_id) is None:
        raise HTTPException(404, "Sesión no encontrada")
    return db.scalars(
        select(CajaMovimiento)
        .where(CajaMovimiento.session_id == session_id)
        .order_by(CajaMovimiento.fecha)
    ).all()


# ---------------------------------------------------------------------------
# Devoluciones
# ---------------------------------------------------------------------------

@router.post("/devolucions/venta", status_code=201, response_model=DevolucionVentaOut)
def create_devolucion_venta(payload: DevolucionVentaIn, db: Session = Depends(get_db)):
    item = db.get(Item, payload.item_id)
    if item is None:
        raise HTTPException(404, "Ejemplar no encontrado")

    dev = DevolucionVenta(
        order_item_id=payload.order_item_id,
        venta_externa_id=payload.venta_externa_id,
        item_id=payload.item_id,
        motivo=payload.motivo,
        destino_item=payload.destino_item,
        fecha=payload.fecha,
        notas=payload.notas,
        cantidad=payload.cantidad,
    )
    db.add(dev)

    if item.condicion == CondicionItem.nou:
        # No hay status individual que restaurar: si vuelve a la venta, se
        # suman las unidades de vuelta a la línea agregada.
        if payload.destino_item == "disponible":
            item.cantidad += payload.cantidad
            sync_stock_listing(db, item)
    else:
        item.status = ItemStatus.disponible if payload.destino_item == "disponible" else ItemStatus.retirado
        item.reserved_until = None
        item.reserved_by_cart_id = None

    # Si la venda original era en efectiu, registrar la devolució com a sortida de caixa
    if payload.venta_externa_id:
        venta = db.get(VentaExterna, payload.venta_externa_id)
        if venta and venta.metodo_pago == MetodoPago.efectivo:
            sesion = db.scalar(
                select(CajaSession).where(CajaSession.fecha_cierre.is_(None))
                .order_by(CajaSession.fecha_apertura.desc())
            )
            if sesion:
                release = db.get(Release, item.release_id) if item.release_id else None
                concepto = (
                    f"Devolució: {release.artista} — {release.titulo}"
                    if release else "Devolució venda efectiu"
                )
                db.add(CajaMovimiento(
                    session_id=sesion.id,
                    tipo=TipoMovimiento.salida,
                    concepto=concepto,
                    importe=venta.precio_venta,
                    fecha=payload.fecha,
                ))

    db.commit()
    db.refresh(dev)
    return dev


@router.post("/devolucions/compra", status_code=201, response_model=DevolucionCompraOut)
def create_devolucion_compra(payload: DevolucionCompraIn, db: Session = Depends(get_db)):
    item = db.get(Item, payload.item_id)
    if item is None:
        raise HTTPException(404, "Ejemplar no encontrado")

    if item.condicion == CondicionItem.nou:
        if item.cantidad - item.cantidad_reservada < payload.cantidad:
            raise HTTPException(409, "No hi ha prou unitats lliures per tornar al proveïdor")
        item.cantidad -= payload.cantidad
        sync_stock_listing(db, item)
    else:
        if item.status != ItemStatus.disponible:
            raise HTTPException(409, f"El exemplar no està disponible (estat: {item.status})")
        item.status = ItemStatus.retirado

    dev = DevolucionCompra(
        item_id=payload.item_id,
        compra_id=payload.compra_id,
        motivo=payload.motivo,
        fecha=payload.fecha,
        notas=payload.notas,
        cantidad=payload.cantidad,
    )
    db.add(dev)
    db.commit()
    db.refresh(dev)
    return dev


@router.get("/devolucions/venta", response_model=list[DevolucionVentaOut])
def list_devolucions_venta(db: Session = Depends(get_db)):
    return db.scalars(select(DevolucionVenta).order_by(DevolucionVenta.fecha.desc())).all()


@router.get("/devolucions/compra", response_model=list[DevolucionCompraOut])
def list_devolucions_compra(db: Session = Depends(get_db)):
    return db.scalars(select(DevolucionCompra).order_by(DevolucionCompra.fecha.desc())).all()
