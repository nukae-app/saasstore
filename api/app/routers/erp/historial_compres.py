import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ...database import get_db
from ...models import Comanda, ComandaLinea, EstadoComanda, HistorialCompra, Proveedor, RecordProduct, Release
from ...schemas import HistorialCompraOut, HistorialResumProveedorOut
from ...services.security import require_admin

router = APIRouter(prefix="/admin", tags=["erp"], dependencies=[Depends(require_admin)])

# Estats d'una Comanda que compten com a "senyal real de compra" per al
# buscador de proveïdor: esborrany encara no s'ha enviat de veritat i
# cancelada mai va arribar a fer-se, així que no diuen res sobre qui
# subministra què.
_ESTATS_COMANDA_REALS = [EstadoComanda.enviada, EstadoComanda.rebuda_parcial, EstadoComanda.rebuda]


@router.get("/historial-compres/resum", response_model=list[HistorialResumProveedorOut])
def resum_historial_compres(request: Request, q: str | None = None, db: Session = Depends(get_db)):
    # Fase C (docs/ARQUITECTURA_CORE_VERTICAL.md §17.1): el buscador de
    # proveïdor per artista/segell és un heurístic propi de discos (fa JOIN
    # directe contra RecordProduct.artista/.sello més avall) — per a
    # qualsevol altre vertical no té sentit el criteri, no és que estigui
    # "trencat". S'exclou en comptes de forçar-lo a funcionar amb un criteri
    # que no li pertoca; buscar-lo per vertical, no per feature de tenant,
    # perquè depèn de l'existència de RecordProduct, no d'una preferència.
    if request.state.tenant.vertical_id != "records":
        return []
    """Llistat de proveïdors amb quantes línies de l'històric hi ha i quan
    va ser l'última, per mostrar-ho com a llista desplegable per defecte
    (sense necessitat de cercar). Si es passa `q`, filtra igual que la cerca.

    Combina dues fonts perquè el buscador vagi "aprenent" amb el temps, no
    només amb la importació inicial dels fulls de càlcul (veure
    buscar_historial_compres per l'explicació completa)."""
    stmt = (
        select(
            Proveedor.id, Proveedor.name,
            func.count(HistorialCompra.id), func.max(HistorialCompra.date),
        )
        .join(HistorialCompra, HistorialCompra.proveedor_id == Proveedor.id)
    )
    if q is not None and len(q.strip()) >= 2:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            (HistorialCompra.artist.ilike(like))
            | (HistorialCompra.title.ilike(like))
            | (HistorialCompra.label.ilike(like))
            | (HistorialCompra.notes.ilike(like))
        )
    stmt = stmt.group_by(Proveedor.id, Proveedor.name)

    resum: dict[uuid.UUID, list] = {}
    for pid, nom, count, ultima in db.execute(stmt).all():
        resum[pid] = [nom, count, ultima]

    stmt2 = (
        select(
            Proveedor.id, Proveedor.name,
            func.count(ComandaLinea.id), func.max(Comanda.date),
        )
        .select_from(ComandaLinea)
        .join(Comanda, Comanda.id == ComandaLinea.comanda_id)
        .join(Proveedor, Proveedor.id == Comanda.proveedor_id)
        .join(Release, Release.id == ComandaLinea.release_id)
        .outerjoin(RecordProduct, RecordProduct.release_id == Release.id)
        .where(Comanda.status.in_(_ESTATS_COMANDA_REALS))
    )
    if q is not None and len(q.strip()) >= 2:
        like = f"%{q.strip()}%"
        stmt2 = stmt2.where(
            (RecordProduct.artista.ilike(like))
            | (Release.title.ilike(like))
            | (RecordProduct.sello.ilike(like))
            | (ComandaLinea.notes.ilike(like))
        )
    stmt2 = stmt2.group_by(Proveedor.id, Proveedor.name)
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
    request: Request, q: str | None = None, release_id: uuid.UUID | None = None,
    proveedor_id: uuid.UUID | None = None, db: Session = Depends(get_db),
):
    """Llistat/cerca de l'històric de compres per saber a quins proveïdors
    s'ha comprat abans un disc semblant. No és estoc en temps real, només
    senyal de l'històric. Sense cap filtre, retorna les més recents.

    `release_id`: coincidència exacta (senyal fort). `proveedor_id`: totes
    les línies d'un proveïdor concret. `q`: text lliure per artista/títol/
    segell/notes (mínim 2 caràcters). Combinables entre si.

    Exclòs fora del vertical discos (§17.1): tota la cerca depèn de
    `RecordProduct`/`HistorialCompra.artist`, un heurístic específic de
    discos, no un feature togglejable per tenant.

    Combina dues fonts: `HistorialCompra` (fulls de càlcul d'abans del
    sistema de Comanda/Compra, importació única i congelada) i les línies de
    `Comanda` reals fetes des d'aquí (enviada/rebuda_parcial/rebuda). Sense
    això, el buscador es quedaria congelat a la importació inicial i mai
    "aprendria" de les comandes noves — que és precisament el que ha de fer
    de motor de recomanació de proveïdor."""
    if request.state.tenant.vertical_id != "records":
        return []
    limit = 1000 if proveedor_id is not None else 200

    conditions = []
    if release_id is not None:
        conditions.append(HistorialCompra.release_id == release_id)
    if proveedor_id is not None:
        conditions.append(HistorialCompra.proveedor_id == proveedor_id)
    if q is not None and len(q.strip()) >= 2:
        like = f"%{q.strip()}%"
        conditions.append(
            (HistorialCompra.artist.ilike(like))
            | (HistorialCompra.title.ilike(like))
            | (HistorialCompra.label.ilike(like))
            | (HistorialCompra.notes.ilike(like))
        )

    stmt = (
        select(HistorialCompra)
        .options(selectinload(HistorialCompra.proveedor), selectinload(HistorialCompra.release))
        .order_by(HistorialCompra.date.desc())
        .limit(limit)
    )
    for cond in conditions:
        stmt = stmt.where(cond)
    resultados = [
        HistorialCompraOut(
            id=r.id, proveedor_id=r.proveedor_id, proveedor_nombre=r.proveedor.name,
            date=r.date, artist=r.artist, title=r.title, label=r.label,
            format=r.format, quantity=r.quantity, cost_price=r.cost_price, notes=r.notes,
            release_id=r.release_id, ean=r.release.ean if r.release else None,
        )
        for r in db.scalars(stmt).all()
    ]

    stmt2 = (
        select(
            ComandaLinea.id, Comanda.proveedor_id, Proveedor.name, Comanda.date,
            RecordProduct.artista, Release.title, RecordProduct.sello, RecordProduct.formato,
            ComandaLinea.quantity, ComandaLinea.estimated_unit_price, ComandaLinea.notes,
            ComandaLinea.release_id, Release.ean,
        )
        .join(Comanda, Comanda.id == ComandaLinea.comanda_id)
        .join(Proveedor, Proveedor.id == Comanda.proveedor_id)
        .join(Release, Release.id == ComandaLinea.release_id)
        .outerjoin(RecordProduct, RecordProduct.release_id == Release.id)
        .where(Comanda.status.in_(_ESTATS_COMANDA_REALS))
        .order_by(Comanda.date.desc())
        .limit(limit)
    )
    if release_id is not None:
        stmt2 = stmt2.where(ComandaLinea.release_id == release_id)
    if proveedor_id is not None:
        stmt2 = stmt2.where(Comanda.proveedor_id == proveedor_id)
    if q is not None and len(q.strip()) >= 2:
        like = f"%{q.strip()}%"
        stmt2 = stmt2.where(
            (RecordProduct.artista.ilike(like))
            | (Release.title.ilike(like))
            | (RecordProduct.sello.ilike(like))
            | (ComandaLinea.notes.ilike(like))
        )
    for lid, pid, pnom, fecha, artista, titulo, sello, formato, cantidad, precio, notas, rel_id, ean in db.execute(stmt2).all():
        resultados.append(HistorialCompraOut(
            id=lid, proveedor_id=pid, proveedor_nombre=pnom, date=fecha.date(),
            artist=artista, title=titulo, label=sello, format=formato,
            quantity=cantidad, cost_price=precio, notes=notas, release_id=rel_id, ean=ean,
        ))

    resultados.sort(key=lambda r: r.date, reverse=True)
    return resultados[:limit]
