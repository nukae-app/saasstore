"""Gestió del club del disc des del panell d'admin: configuració general,
tria de catàleg (la safata d'exemplars elegibles) i el cicle de proposta/
revisió/confirmació d'enviaments (veure services/subscripcions.py per a la
lògica de selecció i cobrament)."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import extract, func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import (
    Assignacio, CobramentSubscripcio, CondicionItem, ConfiguracioSubscripcio, EstatAssignacio,
    EstatCobrament, EstatSubscripcio, Item, ItemStatus, Release, Subscripcio,
)
from ..schemas import ConfiguracioSubscripcioOut, ConfiguracioSubscripcioUpdate, InformeSubscripcioMensualOut
from ..services.security import require_admin
from ..services.subscripcions import (
    cobraments_pendents_assignacio, confirmar_cobrament, ometre_assignacio,
    proposar_assignacio, reassignar_item, reintentar_sense_match,
)

router = APIRouter(prefix="/admin/subscripcions", tags=["admin-subscripcions"], dependencies=[Depends(require_admin)])


# ---------------------------------------------------------------------------
# Configuració general
# ---------------------------------------------------------------------------

def _get_or_create_config(db: Session) -> ConfiguracioSubscripcio:
    config = db.get(ConfiguracioSubscripcio, 1)
    if config is None:
        config = ConfiguracioSubscripcio(
            id=1, preu_per_disc=0, periodicitats_mesos_disponibles=[1], quantitats_disponibles=[1],
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


@router.get("/configuracio", response_model=ConfiguracioSubscripcioOut)
def get_configuracio(db: Session = Depends(get_db)):
    return _get_or_create_config(db)


@router.patch("/configuracio", response_model=ConfiguracioSubscripcioOut)
def update_configuracio(payload: ConfiguracioSubscripcioUpdate, db: Session = Depends(get_db)):
    config = _get_or_create_config(db)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(config, k, v)
    db.commit()
    db.refresh(config)
    return config


# ---------------------------------------------------------------------------
# Catàleg: la safata d'exemplars elegibles per subscripció
# ---------------------------------------------------------------------------
# Marge i antiguitat són només filtres/ordre per ajudar l'admin a decidir —
# l'algorisme d'assignació (services/subscripcions.py) mai els torna a
# comprovar, només mira `Item.subscripcio_pool`.

def _dies_estoc(item: Item) -> int | None:
    if item.fecha_entrada is None:
        return None
    ara = datetime.now(timezone.utc)
    entrada = item.fecha_entrada
    if entrada.tzinfo is None:
        entrada = entrada.replace(tzinfo=timezone.utc)
    return max(0, (ara - entrada).days)


def _catalog_stmt(
    config: ConfiguracioSubscripcio, *,
    nomes_pool: bool = False, seccio_id: int | None = None, genere: str | None = None,
    marge_min_pct: float | None = None, marge_max_pct: float | None = None,
):
    stmt = (
        select(Item)
        .join(Release, Item.release_id == Release.id)
        .where(
            Item.status == ItemStatus.disponible,
            # nou (stock agregado): solo cuenta si queda alguna unidad libre.
            or_(Item.condicion != CondicionItem.nou, Item.cantidad > Item.cantidad_reservada),
        )
        .options(selectinload(Item.release))
    )
    if nomes_pool:
        stmt = stmt.where(Item.subscripcio_pool.is_(True))
    if seccio_id is not None:
        stmt = stmt.where(Release.seccio_id == seccio_id)
    if genere:
        stmt = stmt.where(Release.genero.ilike(f"%{genere}%"))
    if config.preu_per_disc:
        if marge_min_pct is not None:
            stmt = stmt.where(Item.precio >= config.preu_per_disc * Decimal(str(marge_min_pct)) / 100)
        if marge_max_pct is not None:
            stmt = stmt.where(Item.precio <= config.preu_per_disc * Decimal(str(marge_max_pct)) / 100)
    return stmt


@router.get("/catalog")
def list_catalog(
    nomes_pool: bool = False,
    seccio_id: int | None = None,
    genere: str | None = None,
    marge_min_pct: float | None = None,
    marge_max_pct: float | None = None,
    ordre: str = "antiguitat",
    db: Session = Depends(get_db),
):
    config = _get_or_create_config(db)
    stmt = _catalog_stmt(
        config, nomes_pool=nomes_pool, seccio_id=seccio_id, genere=genere,
        marge_min_pct=marge_min_pct, marge_max_pct=marge_max_pct,
    )
    if ordre == "marge":
        stmt = stmt.order_by(Item.precio.asc())
    else:
        stmt = stmt.order_by(Item.fecha_entrada.asc().nulls_last())

    items = list(db.scalars(stmt))
    return [
        {
            "item_id": item.id,
            "release_id": item.release_id,
            "artista": item.release.artista,
            "titulo": item.release.titulo,
            "imagen_url": item.release.imagen_url,
            "genero": item.release.genero,
            "precio": item.precio,
            "marge_pct": round(float(item.precio) / float(config.preu_per_disc) * 100, 1) if config.preu_per_disc else None,
            "dies_estoc": _dies_estoc(item),
            "subscripcio_pool": item.subscripcio_pool,
            "condicion": item.condicion.value,
            "cantidad": item.cantidad,
            "cantidad_reservada": item.cantidad_reservada,
        }
        for item in items
    ]


class CatalogPoolPatchIn(BaseModel):
    subscripcio_pool: bool


class SeleccioAutomaticaIn(BaseModel):
    seccio_id: int | None = None
    genere: str | None = None
    marge_min_pct: float | None = None
    marge_max_pct: float | None = None
    limit: int = 50


@router.post("/catalog/seleccio-automatica")
def seleccio_automatica(payload: SeleccioAutomaticaIn, db: Session = Depends(get_db)):
    """Afegeix a la safata, en massa, els exemplars disponibles que compleixin
    els filtres donats (mateixos que la pantalla "Catàleg"), prioritzant
    l'estoc més antic — fins a `limit`. Purament un punt de partida ràpid:
    l'admin sempre pot afegir o treure exemplars individualment després."""
    config = _get_or_create_config(db)
    stmt = (
        _catalog_stmt(
            config, nomes_pool=False, seccio_id=payload.seccio_id, genere=payload.genere,
            marge_min_pct=payload.marge_min_pct, marge_max_pct=payload.marge_max_pct,
        )
        .where(Item.subscripcio_pool.is_(False))
        .order_by(Item.fecha_entrada.asc().nulls_last())
        .limit(max(0, payload.limit))
    )
    items = list(db.scalars(stmt))
    for item in items:
        item.subscripcio_pool = True
    db.commit()
    return {"afegits": len(items)}


@router.patch("/catalog/{item_id}")
def patch_catalog_item(item_id: uuid.UUID, payload: CatalogPoolPatchIn, db: Session = Depends(get_db)):
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "Exemplar no trobat")
    item.subscripcio_pool = payload.subscripcio_pool
    db.commit()
    return {"item_id": item.id, "subscripcio_pool": item.subscripcio_pool}


# ---------------------------------------------------------------------------
# Subscriptors
# ---------------------------------------------------------------------------

@router.get("")
def list_subscripcions(db: Session = Depends(get_db)):
    subscripcions = list(db.scalars(
        select(Subscripcio).options(selectinload(Subscripcio.user)).order_by(Subscripcio.created_at.desc())
    ))
    # "primer guanya": iterem ja ordenat per confirmada_at desc, així que el
    # primer cop que vegem cada subscripció és el seu disc més recent.
    ultim_disc: dict[uuid.UUID, str] = {}
    for sub_id, artista, titulo, _confirmada_at in db.execute(
        select(Assignacio.subscripcio_id, Release.artista, Release.titulo, Assignacio.confirmada_at)
        .join(Release, Release.id == Assignacio.release_id)
        .where(Assignacio.estat == EstatAssignacio.confirmada)
        .order_by(Assignacio.confirmada_at.desc())
    ).all():
        ultim_disc.setdefault(sub_id, f"{artista} — {titulo}")

    return [
        {
            "id": s.id,
            "email": s.user.email,
            "nom": s.user.nombre,
            "periodicitat_mesos": s.periodicitat_mesos,
            "quantitat": s.quantitat,
            "preu_periode": s.preu_periode,
            "estat": s.estat,
            "generes_preferits": s.generes_preferits,
            "proxima_facturacio": s.proxima_facturacio,
            "ultim_disc_rebut": ultim_disc.get(s.id),
            "created_at": s.created_at,
        }
        for s in subscripcions
    ]


# ---------------------------------------------------------------------------
# Cicle: cobraments pendents -> propostes -> revisió -> confirmació
# ---------------------------------------------------------------------------

@router.get("/cobraments-pendents")
def list_cobraments_pendents(db: Session = Depends(get_db)):
    """Cobraments (enviaments) ja fets sense cap disc assignat encara: la
    cua de feina."""
    cobraments = cobraments_pendents_assignacio(db)
    return [
        {
            "id": c.id,
            "subscripcio_id": c.subscripcio_id,
            "email": c.subscripcio.user.email,
            "periode": c.periode,
            "import_": c.import_,
            "quantitat": c.subscripcio.quantitat,
        }
        for c in cobraments
    ]


@router.post("/proposar")
def proposar(db: Session = Depends(get_db)):
    """Genera la proposta automàtica per a tots els cobraments pendents
    (veure services/subscripcions.py::seleccionar_items_candidats), triant
    només entre els exemplars que l'admin ha posat a la safata. Cada
    cobrament es processa (i es guarda) per separat: si un falla, no bloqueja
    la resta del lot."""
    cobraments = cobraments_pendents_assignacio(db)
    processats, errors = 0, []
    for cobrament in cobraments:
        try:
            proposar_assignacio(db, cobrament)
            db.commit()
            processats += 1
        except Exception as exc:  # noqa: BLE001 — no volem que un cobrament espatllat aturi la resta
            db.rollback()
            errors.append({"cobrament_id": str(cobrament.id), "error": str(exc)})
    return {"enviaments_proposats": processats, "errors": errors}


def _enviament_dict(cobrament: CobramentSubscripcio, config: ConfiguracioSubscripcio) -> dict:
    discos = []
    for a in cobrament.assignacions:
        item = a.item
        marge_pct = None
        dies_estoc = None
        if item is not None and config.preu_per_disc:
            marge_pct = round(float(item.precio) / float(config.preu_per_disc) * 100, 1)
            dies_estoc = _dies_estoc(item)
        discos.append({
            "assignacio_id": a.id,
            "estat": a.estat,
            "item": None if item is None else {
                "id": item.id,
                "artista": item.release.artista,
                "titulo": item.release.titulo,
                "imagen_url": item.release.imagen_url,
                "precio": item.precio,
                "marge_pct": marge_pct,
                "dies_estoc": dies_estoc,
                "condicion": item.condicion.value,
            },
        })
    return {
        "cobrament_id": cobrament.id,
        "subscripcio_id": cobrament.subscripcio_id,
        "email": cobrament.subscripcio.user.email,
        "import_cobrat": cobrament.import_,
        "discos": discos,
    }


@router.get("/assignacions")
def list_assignacions(estat: str | None = None, db: Session = Depends(get_db)):
    """Enviaments agrupats (un `cobrament` = un enviament amb N discs a
    dins) amb almenys un disc encara "en joc": `proposada` (a l'espera de
    revisió) o `sense_match` (la safata no en tenia prou — es pot reintentar
    o triar a mà, veure `/cobraments/{id}/reintentar`). Passa `estat` per
    filtrar a un dels dos únicament."""
    config = _get_or_create_config(db)
    estats = [estat] if estat else [EstatAssignacio.proposada.value, EstatAssignacio.sense_match.value]
    cobrament_ids = db.scalars(
        select(Assignacio.cobrament_id).where(Assignacio.estat.in_(estats)).distinct()
    ).all()
    cobraments = list(db.scalars(
        select(CobramentSubscripcio)
        .where(CobramentSubscripcio.id.in_(cobrament_ids))
        .options(
            selectinload(CobramentSubscripcio.subscripcio).selectinload(Subscripcio.user),
            selectinload(CobramentSubscripcio.assignacions).selectinload(Assignacio.item).selectinload(Item.release),
        )
        .order_by(CobramentSubscripcio.created_at)
    ))
    return [_enviament_dict(c, config) for c in cobraments]


class AssignacioPatchIn(BaseModel):
    item_id: uuid.UUID | None = None
    ometre: bool = False


@router.patch("/assignacions/{assignacio_id}")
def patch_assignacio(assignacio_id: uuid.UUID, payload: AssignacioPatchIn, db: Session = Depends(get_db)):
    assignacio = db.get(Assignacio, assignacio_id)
    if assignacio is None:
        raise HTTPException(404, "Assignació no trobada")

    if payload.ometre:
        ometre_assignacio(db, assignacio)
    elif payload.item_id is not None:
        nou_item = db.get(Item, payload.item_id)
        if nou_item is None:
            raise HTTPException(404, "Exemplar no trobat")
        try:
            reassignar_item(db, assignacio, nou_item)
        except ValueError as exc:
            raise HTTPException(409, str(exc))
    db.commit()

    config = _get_or_create_config(db)
    return _enviament_dict(assignacio.cobrament, config)


@router.post("/cobraments/{cobrament_id}/reintentar")
def reintentar(cobrament_id: uuid.UUID, db: Session = Depends(get_db)):
    """Torna a buscar exemplar per als discos `sense_match` d'aquest
    enviament (típicament després d'afegir-ne més a la safata). No fa res
    amb els discos ja `proposada`/`confirmada`/`omesa`."""
    cobrament = db.get(CobramentSubscripcio, cobrament_id)
    if cobrament is None:
        raise HTTPException(404, "Cobrament no trobat")
    trobats = reintentar_sense_match(db, cobrament)
    db.commit()

    config = _get_or_create_config(db)
    return {"trobats": len(trobats), "enviament": _enviament_dict(cobrament, config)}


@router.post("/cobraments/{cobrament_id}/confirmar")
def confirmar(cobrament_id: uuid.UUID, db: Session = Depends(get_db)):
    cobrament = db.get(CobramentSubscripcio, cobrament_id)
    if cobrament is None:
        raise HTTPException(404, "Cobrament no trobat")
    try:
        order = confirmar_cobrament(db, cobrament)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(409, str(exc))
    return {"order_id": order.id}


@router.post("/cobraments/confirmar-totes")
def confirmar_totes(db: Session = Depends(get_db)):
    cobrament_ids = db.scalars(
        select(Assignacio.cobrament_id).where(Assignacio.estat == EstatAssignacio.proposada).distinct()
    ).all()
    confirmades, errors = 0, []
    for cobrament_id in cobrament_ids:
        cobrament = db.get(CobramentSubscripcio, cobrament_id)
        try:
            confirmar_cobrament(db, cobrament)
            confirmades += 1
        except (ValueError, RuntimeError) as exc:
            errors.append({"cobrament_id": str(cobrament_id), "error": str(exc)})
    return {"confirmades": confirmades, "errors": errors}


# ---------------------------------------------------------------------------
# Informe mensual
# ---------------------------------------------------------------------------

@router.get("/informe/{any_}/{mes}", response_model=InformeSubscripcioMensualOut)
def informe_mensual(any_: int, mes: int, db: Session = Depends(get_db)):
    """Resum d'un mes del club del disc: subscriptors actius, altes i
    baixes d'aquell mes, cobraments (fets i fallits, per `periode` —
    el cicle a què pertanyen, no la data en què es van processar) i discos
    enviats. Mateix patró que `comptabilitat.py::resultat_mensual`."""
    if not (1 <= mes <= 12):
        raise HTTPException(422, "Mes ha de ser entre 1 i 12")

    def _mes_filter(col):
        return (extract("year", col) == any_) & (extract("month", col) == mes)

    subscriptors_actius = db.scalar(
        select(func.count(Subscripcio.id)).where(Subscripcio.estat == EstatSubscripcio.activa)
    ) or 0

    # Noves subscripcions: el primer cobrament (per periode) de la subscripció cau aquest mes.
    primer_cobrament = (
        select(
            CobramentSubscripcio.subscripcio_id,
            func.min(CobramentSubscripcio.periode).label("primer_periode"),
        )
        .group_by(CobramentSubscripcio.subscripcio_id)
        .subquery()
    )
    noves_subscripcions = db.scalar(
        select(func.count()).select_from(primer_cobrament).where(_mes_filter(primer_cobrament.c.primer_periode))
    ) or 0

    baixes = db.scalar(
        select(func.count(Subscripcio.id))
        .where(Subscripcio.estat == EstatSubscripcio.cancel_lada)
        .where(_mes_filter(Subscripcio.cancel_lada_at))
    ) or 0

    cobraments_ok, import_total = db.execute(
        select(func.count(CobramentSubscripcio.id), func.coalesce(func.sum(CobramentSubscripcio.import_), Decimal("0")))
        .where(CobramentSubscripcio.estat == EstatCobrament.cobrat)
        .where(_mes_filter(CobramentSubscripcio.periode))
    ).one()

    cobraments_fallits = db.scalar(
        select(func.count(CobramentSubscripcio.id))
        .where(CobramentSubscripcio.estat == EstatCobrament.fallit)
        .where(_mes_filter(CobramentSubscripcio.periode))
    ) or 0

    discos_enviats = db.scalar(
        select(func.count(Assignacio.id))
        .where(Assignacio.estat == EstatAssignacio.confirmada)
        .where(_mes_filter(Assignacio.confirmada_at))
    ) or 0

    return {
        "any_": any_,
        "mes": mes,
        "subscriptors_actius": subscriptors_actius,
        "noves_subscripcions": noves_subscripcions,
        "baixes": baixes,
        "cobraments_ok": cobraments_ok,
        "import_total": import_total,
        "cobraments_fallits": cobraments_fallits,
        "discos_enviats": discos_enviats,
    }


# ---------------------------------------------------------------------------
# Fitxa de subscriptor (registrada al final: és una ruta d'un sol segment
# `/{subscripcio_id}` i FastAPI fa el matching per ordre de registre — si
# anés abans, interceptaria "/cobraments-pendents", "/proposar" o
# "/assignacions" com si fossin un id).
# ---------------------------------------------------------------------------

@router.get("/{subscripcio_id}")
def get_subscripcio_detail(subscripcio_id: uuid.UUID, db: Session = Depends(get_db)):
    """Fitxa completa d'un subscriptor: gustos, adreça i l'històric sencer
    de discos enviats (no només l'últim, com a la llista)."""
    subscripcio = db.get(
        Subscripcio, subscripcio_id,
        options=[selectinload(Subscripcio.user), selectinload(Subscripcio.address)],
    )
    if subscripcio is None:
        raise HTTPException(404, "Subscripció no trobada")

    discos_rebuts = list(db.execute(
        select(Release.id, Release.artista, Release.titulo, Release.imagen_url, Assignacio.confirmada_at)
        .join(Assignacio, Assignacio.release_id == Release.id)
        .where(Assignacio.subscripcio_id == subscripcio.id, Assignacio.estat == EstatAssignacio.confirmada)
        .order_by(Assignacio.confirmada_at.desc())
    ).all())

    address = subscripcio.address
    return {
        "id": subscripcio.id,
        "email": subscripcio.user.email,
        "nom": subscripcio.user.nombre,
        "estat": subscripcio.estat,
        "periodicitat_mesos": subscripcio.periodicitat_mesos,
        "quantitat": subscripcio.quantitat,
        "preu_periode": subscripcio.preu_periode,
        "proxima_facturacio": subscripcio.proxima_facturacio,
        "created_at": subscripcio.created_at,
        "generes_preferits": subscripcio.generes_preferits or [],
        "adreca": None if address is None else {
            "nombre_destinatario": address.nombre_destinatario,
            "linea1": address.linea1,
            "linea2": address.linea2,
            "ciudad": address.ciudad,
            "cp": address.cp,
            "provincia": address.provincia,
            "pais": address.pais,
        },
        "discos_rebuts": [
            {"release_id": r[0], "artista": r[1], "titulo": r[2], "imagen_url": r[3], "confirmada_at": r[4]}
            for r in discos_rebuts
        ],
    }
