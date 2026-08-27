import csv
import io
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ...database import get_db
from ...models import (
    Comanda, ComandaLinea, CondicionItem, Compra, EstadoComanda, EstadoPeticionCliente, Item,
    PeticionCliente, Proveedor, RecordProduct, Release, SolicitudCompraLinea, TipoCompra,
)
from ...schemas import ComandaIn, ComandaOut, RecepcionIn
from ...services import discogs
from ...services.comanda_pdf import generate_comanda_pdf
from ...services.discogs_sync import get_discogs_token_if_enabled, sync_stock_listing
from ...services.emailer import send_email
from ...services.security import require_admin
from ..admin import require_discogs_enabled
from ._peticiones_stock import _enviar_email_item_arribat, _reservar_item_para_peticion

router = APIRouter(prefix="/admin", tags=["erp"], dependencies=[Depends(require_admin)])


def _resolve_release_by_discogs_id(db: Session, discogs_release_id: int, token: str | None) -> Release:
    release = db.scalar(
        select(Release).join(RecordProduct).where(RecordProduct.discogs_release_id == discogs_release_id)
    )
    if release is not None:
        return release
    data = discogs.get_release(token, discogs_release_id)
    release = Release(
        artista=data.get("artista") or f"Discogs #{discogs_release_id}",
        title=data.get("titulo") or "",
        sello=data.get("sello"), referencia=data.get("referencia"),
        anio=data.get("anio"), genero=data.get("genero"), estilos=data.get("estilos"),
        pais=data.get("pais"), image_url=data.get("imagen_url"),
        tracklist=data.get("tracklist"), credits=data.get("credits"),
        discogs_release_id=discogs_release_id,
    )
    db.add(release)
    db.flush()
    return release


def _comanda_out(comanda: Comanda) -> dict:
    return {
        "id": comanda.id,
        "proveedor_id": comanda.proveedor_id,
        "proveedor_nombre": comanda.proveedor.name,
        "date": comanda.date,
        "status": comanda.status,
        "order_number": comanda.order_number,
        "notes": comanda.notes,
        "sent_at": comanda.sent_at,
        "created_at": comanda.created_at,
        "lineas": [
            {
                "id": linea.id,
                "release_id": linea.release_id,
                "artista": linea.release.artista,
                "titulo": linea.release.title,
                "quantity": linea.quantity,
                "estimated_unit_price": linea.estimated_unit_price,
                "received_quantity": linea.received_quantity,
                "notes": linea.notes,
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


@router.post("/comandas/resolver-csv", dependencies=[Depends(require_discogs_enabled)])
async def resolver_comanda_csv(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Resol un CSV de discogs_release_id+cantidad+precio_unitario_estimado a línies
    de comanda (resolent o creant el release a partir de Discogs). No crea cap comanda:
    només retorna les línies per afegir-les al formulari que s'estigui editant."""
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    token = get_discogs_token_if_enabled(db, request.state.tenant.id)

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
            release = _resolve_release_by_discogs_id(db, discogs_release_id, token)
        except Exception as exc:
            errors.append({"fila": n, "discogs_release_id": discogs_release_id, "motiu": f"Error consultant Discogs: {exc}"})
            continue

        lineas.append({
            "release_id": str(release.id), "artista": release.artista, "titulo": release.title,
            "quantity": cantidad, "estimated_unit_price": precio_unitario_estimado,
            "existing": True,
        })

    db.commit()  # persisteix els releases creats encara que no es desi la comanda
    return {"lineas": lineas, "errors": errors}


def _next_num_comanda(db: Session, year: int) -> str:
    """Numeració automàtica per any: '2026-000001', '2026-000002'..."""
    prefix = f"{year}-"
    existentes = db.scalars(
        select(Comanda.order_number).where(Comanda.order_number.like(f"{prefix}%"))
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
            proveedor_id=payload.proveedor_id, date=payload.date,
            order_number=_next_num_comanda(db, payload.date.year), notes=payload.notes,
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
            comanda_id=comanda.id, release_id=linea.release_id, quantity=linea.quantity,
            estimated_unit_price=linea.estimated_unit_price, notes=linea.notes,
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
        .order_by(Comanda.date.desc())
    )
    if status:
        stmt = stmt.where(Comanda.status == EstadoComanda(status))
    if desde:
        stmt = stmt.where(Comanda.date >= desde)
    if hasta:
        stmt = stmt.where(Comanda.date <= hasta)
    comandas = db.scalars(stmt).all()

    if q:
        ql = q.lower()
        comandas = [
            c for c in comandas
            if (c.order_number and ql in c.order_number.lower())
            or ql in c.proveedor.name.lower()
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
    filename = f"comanda_{comanda.order_number or comanda.id}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/comandas/{comanda_id}/enviar", response_model=ComandaOut)
def enviar_comanda(comanda_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    """Envia la comanda per email al proveïdor (amb el PDF adjunt) i la marca com a enviada."""
    comanda = _get_comanda_or_404(db, comanda_id)
    if comanda.status not in (EstadoComanda.esborrany, EstadoComanda.enviada):
        raise HTTPException(409, "Aquesta comanda no es pot enviar en el seu estat actual")
    if not comanda.proveedor.email:
        raise HTTPException(422, "El proveïdor no té email configurat")

    pdf_bytes = generate_comanda_pdf(comanda, db)
    filename = f"comanda_{comanda.order_number or comanda.id}.pdf"
    send_email(
        to=comanda.proveedor.email,
        subject=f"Comanda {comanda.order_number or comanda.id}",
        body="Adjuntem la comanda. Gràcies!",
        tenant=request.state.tenant,
        db=db,
        attachment=(filename, pdf_bytes, "application/pdf"),
    )
    comanda.sent_at = datetime.now(timezone.utc)
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
    comanda.sent_at = datetime.now(timezone.utc)
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
def recibir_comanda(comanda_id: uuid.UUID, payload: RecepcionIn, request: Request, db: Session = Depends(get_db)):
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
        pendientes[item.comanda_linea_id] = pendientes.get(item.comanda_linea_id, 0) + item.quantity

    for linea_id, cantidad in pendientes.items():
        linea = lineas_por_id[linea_id]
        disponible = linea.quantity - linea.received_quantity
        if cantidad > disponible:
            raise HTTPException(
                422,
                f"La línia de '{linea.release.artista} - {linea.release.title}' només té "
                f"{disponible} unitats pendents de rebre (s'han enviat {cantidad})",
            )

    compra = Compra(
        type=TipoCompra.proveedor, proveedor_id=comanda.proveedor_id,
        date=payload.date, delivery_note_number=payload.delivery_note_number, notes=payload.notes,
        comanda_id=comanda.id,
        total_cost=sum((item.acquisition_cost or Decimal("0")) * item.quantity for item in payload.items),
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
                PeticionCliente.status == EstadoPeticionCliente.en_tramit,
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
        if item.condition != CondicionItem.nou.value:
            nuevo_item = Item(
                release_id=linea.release_id, price=item.price, condition=item.condition,
                acquisition_cost=item.acquisition_cost, estado_disco=item.estado_disco,
                estado_funda=item.estado_funda, compra_id=compra.id,
                entry_date=compra.date,
            )
            db.add(nuevo_item)
            items_creados.append(nuevo_item)
            continue

        agregado = lineas_nou_vistas.get(item.comanda_linea_id)
        if agregado is None:
            agregado = db.scalar(
                select(Item).where(Item.release_id == linea.release_id, Item.condition == CondicionItem.nou)
            )
        n = item.quantity
        if agregado is None:
            agregado = Item(
                release_id=linea.release_id, price=item.price, condition=CondicionItem.nou,
                quantity=n, acquisition_cost=item.acquisition_cost,
                compra_id=compra.id, entry_date=compra.date,
            )
            db.add(agregado)
        else:
            coste_anterior = agregado.acquisition_cost or Decimal("0")
            coste_nuevo = item.acquisition_cost if item.acquisition_cost is not None else coste_anterior
            agregado.acquisition_cost = (
                agregado.quantity * coste_anterior + n * coste_nuevo
            ) / (agregado.quantity + n)
            agregado.quantity += n
            agregado.price = item.price
            agregado.compra_id = compra.id
            agregado.entry_date = compra.date
        sync_stock_listing(db, agregado, get_discogs_token_if_enabled(db, request.state.tenant.id))
        lineas_nou_vistas[item.comanda_linea_id] = agregado
        items_creados.append(agregado)

    for linea_id, cantidad in pendientes.items():
        lineas_por_id[linea_id].received_quantity += cantidad

    comanda.status = (
        EstadoComanda.rebuda
        if all(l.received_quantity >= l.quantity for l in comanda.lineas)
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
        _enviar_email_item_arribat(db, peticion, request.state.tenant)

    return {"compra_id": str(compra.id), "items_creados": len(payload.items), "comanda_status": comanda.status}
