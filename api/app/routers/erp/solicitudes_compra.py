import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ...database import get_db
from ...models import (
    Comanda, ComandaLinea, CondicionItem, DevolucionVenta, EstadoComanda, EstadoPeticionCliente,
    EstadoSolicitud, HistorialCompra, Item, ItemStatus, Order, OrderItem, OrderStatus, OrigenSolicitud,
    PeticionCliente, Proveedor, Release, SolicitudCompra, SolicitudCompraLinea, VentaExterna,
)
from ...schemas import (
    ComandaOut, RefillSugerenciaOut, ResoldreEstocIn, SolicitudCompraIn, SolicitudCompraLineaIn,
    SolicitudCompraLineaOut, SolicitudCompraOut, SolicitudResolverIn,
)
from ...services.security import require_admin
from ._peticiones_stock import (
    _enviar_email_item_arribat, _reservar_item_para_peticion, _tancar_linea_solicitud_desde_stock,
)
from .comandas import _comanda_out, _get_comanda_or_404, _next_num_comanda

router = APIRouter(prefix="/admin", tags=["erp"], dependencies=[Depends(require_admin)])


def _solicitud_linea_out(linea: SolicitudCompraLinea) -> SolicitudCompraLineaOut:
    return SolicitudCompraLineaOut(
        id=linea.id,
        release_id=linea.release_id,
        artist=linea.release.artista if linea.release else linea.artist,
        title=linea.release.title if linea.release else linea.title,
        label=linea.release.sello if linea.release else linea.label,
        format=linea.release.formato if linea.release else linea.format,
        quantity=linea.quantity,
        proveedor_sugerido_id=linea.proveedor_sugerido_id,
        proveedor_sugerido_nombre=linea.proveedor_sugerido.name if linea.proveedor_sugerido else None,
        comanda_linea_id=linea.comanda_linea_id,
        item_resuelto_id=linea.item_resuelto_id,
        resuelta=linea.comanda_linea_id is not None or linea.item_resuelto_id is not None,
        notes=linea.notes,
    )


def _solicitud_out(solicitud: SolicitudCompra) -> SolicitudCompraOut:
    return SolicitudCompraOut(
        id=solicitud.id,
        estado=solicitud.estado,
        origen=solicitud.origen,
        user_id=solicitud.user_id,
        user_nom=solicitud.user.name if solicitud.user else None,
        notes=solicitud.notes,
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
            .where(HistorialCompra.artist.ilike(f"%{artista}%"))
            .group_by(HistorialCompra.proveedor_id)
        ).all()
    if not rows:
        return None, None
    top_id = sorted(rows, key=lambda r: -r[1])[0][0]
    prov = db.get(Proveedor, top_id)
    return (prov.id, prov.name) if prov else (None, None)


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
        select(Item.release_id, func.sum(Item.quantity - Item.reserved_quantity))
        .where(Item.status == ItemStatus.disponible, Item.condition == CondicionItem.nou)
        .group_by(Item.release_id)
    ).all())

    def _ventas_periode(desde: datetime, fins: datetime) -> dict[uuid.UUID, int]:
        web = dict(db.execute(
            select(Item.release_id, func.count())
            .select_from(OrderItem)
            .join(Order, Order.id == OrderItem.order_id)
            .join(Item, Item.id == OrderItem.item_id)
            .where(
                Order.status.in_(ORDER_STATUS_VENUT), Item.condition == CondicionItem.nou,
                Order.created_at >= desde, Order.created_at < fins,
            )
            .group_by(Item.release_id)
        ).all())
        externa = dict(db.execute(
            select(Item.release_id, func.count())
            .select_from(VentaExterna)
            .join(Item, Item.id == VentaExterna.item_id)
            .where(Item.condition == CondicionItem.nou, VentaExterna.date >= desde, VentaExterna.date < fins)
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
        select(Item.release_id, func.avg(OrderItem.price - Item.acquisition_cost))
        .select_from(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .join(Item, Item.id == OrderItem.item_id)
        .where(
            Order.status.in_(ORDER_STATUS_VENUT), Item.acquisition_cost.isnot(None),
            Order.created_at >= inici_periode,
        )
        .group_by(Item.release_id)
    ).all()
    marge_externa = db.execute(
        select(Item.release_id, func.avg(VentaExterna.sale_price - Item.acquisition_cost))
        .select_from(VentaExterna)
        .join(Item, Item.id == VentaExterna.item_id)
        .where(Item.acquisition_cost.isnot(None), VentaExterna.date >= inici_periode)
        .group_by(Item.release_id)
    ).all()
    marge_por_release: dict[uuid.UUID, Decimal] = {}
    contador_marge: dict[uuid.UUID, int] = {}
    for rid, avg_marge in [*marge_web, *marge_externa]:
        if avg_marge is None:
            continue
        # func.avg() no garanteix Decimal en tots els backends (SQLite el
        # retorna com a float, Postgres com a Decimal) — normalitzem abans
        # de sumar per evitar un TypeError en barrejar tipus.
        if not isinstance(avg_marge, Decimal):
            avg_marge = Decimal(str(avg_marge))
        marge_por_release[rid] = marge_por_release.get(rid, Decimal("0")) + avg_marge
        contador_marge[rid] = contador_marge.get(rid, 0) + 1
    for rid in marge_por_release:
        marge_por_release[rid] = marge_por_release[rid] / contador_marge[rid]

    # Devolucions recents (senyal negatiu, es mostra però no exclou automàticament).
    devolucions_por_release: dict[uuid.UUID, int] = dict(db.execute(
        select(Item.release_id, func.count())
        .select_from(DevolucionVenta)
        .join(Item, Item.id == DevolucionVenta.item_id)
        .where(DevolucionVenta.date >= inici_periode)
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
            release_id=release_id, artista=release.artista, titulo=release.title, formato=release.formato,
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
        origen=OrigenSolicitud(payload.origen), user_id=payload.user_id, notes=payload.notes,
    )
    db.add(solicitud)
    db.flush()
    for linea in payload.lineas:
        db.add(SolicitudCompraLinea(
            solicitud_id=solicitud.id, release_id=linea.release_id,
            artist=linea.artist, title=linea.title, label=linea.label, format=linea.format,
            quantity=linea.quantity, proveedor_sugerido_id=linea.proveedor_sugerido_id, notes=linea.notes,
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
        artist=payload.artist, title=payload.title, label=payload.label, format=payload.format,
        quantity=payload.quantity, proveedor_sugerido_id=payload.proveedor_sugerido_id, notes=payload.notes,
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
                f"La línia '{linea.artist} - {linea.title}' no té release_id: "
                "cal donar d'alta el disc al catàleg abans de resoldre-la",
            )
        solicitud_lineas.append(linea)

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

    lineas_por_solicitud: dict[uuid.UUID, list[SolicitudCompraLinea]] = {}
    for item, linea in zip(payload.lineas, solicitud_lineas):
        cantidad = item.quantity if item.quantity is not None else linea.quantity
        comanda_linea = ComandaLinea(
            comanda_id=comanda.id, release_id=linea.release_id, quantity=cantidad,
            estimated_unit_price=item.estimated_unit_price, notes=linea.notes,
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


@router.post("/solicitudes-compra/lineas/{linea_id}/resoldre-estoc", response_model=SolicitudCompraOut)
def resolver_linea_desde_stock(linea_id: uuid.UUID, payload: ResoldreEstocIn, request: Request, db: Session = Depends(get_db)):
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
                PeticionCliente.status == EstadoPeticionCliente.en_tramit,
            )
            .options(selectinload(PeticionCliente.release), selectinload(PeticionCliente.user))
        )
        if peticion is None:
            raise HTTPException(422, "No s'ha trobat la petició de client associada a aquesta línia")
        _reservar_item_para_peticion(db, peticion, item)
    elif item.condition != CondicionItem.nou:
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
        _enviar_email_item_arribat(db, peticion, request.state.tenant)

    return _solicitud_out(_get_solicitud_or_404(db, solicitud.id))
