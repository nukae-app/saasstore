import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ...database import get_db
from ...models import (
    CondicionItem, EstadoPeticionCliente, Item, ItemStatus, OrigenSolicitud, PeticionCliente,
    Release, SolicitudCompraLinea, User,
)
from ...schemas import (
    PeticionCatalogarIn, PeticionClienteAdminOut, PeticionPrecioIn, PeticionTiendaIn,
    PeticionVincularIn, PeticionVincularItemIn, ReservaRecollidaOut, SolicitudCompraLineaOut,
)
from ...services.emailer import render_email_html, send_email
from ...services.i18n import translate
from ...services.reservations import release_expired
from ...services.security import require_admin
from ._peticiones_stock import (
    _enviar_email_item_arribat, _get_peticion_or_404, _link_un_clic_a_peticions,
    _peticion_admin_out, _reservar_item_para_peticion, _tancar_linea_solicitud_desde_stock,
)
from .solicitudes_compra import _solicitud_linea_out

router = APIRouter(prefix="/admin", tags=["erp"], dependencies=[Depends(require_admin)])


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
        stmt = stmt.where(PeticionCliente.status == EstadoPeticionCliente(estado))
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
                Item.condition == CondicionItem.nou, Item.quantity > Item.reserved_quantity,
            )
        )
        if stock:
            raise HTTPException(409, "Aquest disc ja té estoc disponible: es pot vendre directament")

    peticion = PeticionCliente(
        user_id=payload.user_id, channel="tienda", release_id=payload.release_id,
        free_artist=payload.free_artist, free_title=payload.free_title,
        client_notes=payload.client_notes,
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
            PeticionCliente.status == EstadoPeticionCliente.reservada,
            PeticionCliente.chosen_delivery_method == "recollida_paga_botiga",
        )
        .options(
            selectinload(PeticionCliente.release), selectinload(PeticionCliente.user),
            selectinload(PeticionCliente.item),
        )
        .order_by(PeticionCliente.updated_at)
    ).all()
    return [
        ReservaRecollidaOut(
            peticion_id=p.id, item_id=p.item.id, artista=p.release.artista, titulo=p.release.title,
            imagen_url=p.release.image_url, precio=p.item.price, condicion=p.item.condition,
            estado_disco=p.item.estado_disco, user_id=p.user.id, user_nombre=p.user.name,
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
    if peticion.status not in (EstadoPeticionCliente.pendent, EstadoPeticionCliente.pendent_acceptacio):
        raise HTTPException(409, "Només es pot modificar el disc abans que el client accepti la petició")
    if db.get(Release, payload.release_id) is None:
        raise HTTPException(404, "Release no trobat")

    canvia_disc = peticion.release_id != payload.release_id
    peticion.release_id = payload.release_id
    if canvia_disc and peticion.status == EstadoPeticionCliente.pendent_acceptacio:
        peticion.estimated_price = None
        peticion.status = EstadoPeticionCliente.pendent
    db.commit()
    return _peticion_admin_out(_get_peticion_or_404(db, peticion.id))


@router.patch("/peticiones/{peticion_id}/precio", response_model=PeticionClienteAdminOut)
def fijar_precio_peticion(peticion_id: uuid.UUID, payload: PeticionPrecioIn, request: Request, db: Session = Depends(get_db)):
    """Fixa el preu estimat. Petició web: notifica el client per email
    perquè l'accepti o el rebutgi des del seu compte, abans de comprar res
    al proveïdor. Petició de tienda (trucada o mostrador): el client ja ha
    acceptat el preu de paraula, així que es salta aquest pas — passa
    directament a 'acceptada' amb recollida i pagament a botiga."""
    peticion = _get_peticion_or_404(db, peticion_id)
    if peticion.status != EstadoPeticionCliente.pendent:
        raise HTTPException(409, "Aquesta petició no està en estat pendent")
    if peticion.release_id is None:
        raise HTTPException(422, "Cal catalogar el disc (release_id) abans de fixar preu")

    peticion.estimated_price = payload.estimated_price

    if peticion.channel == "tienda":
        peticion.status = EstadoPeticionCliente.acceptada
        peticion.chosen_delivery_method = "recollida_paga_botiga"
        db.commit()
        return _peticion_admin_out(_get_peticion_or_404(db, peticion.id))

    peticion.status = EstadoPeticionCliente.pendent_acceptacio
    db.commit()
    db.refresh(peticion)

    disco = f"{peticion.release.artista} - {peticion.release.title}"
    lang = peticion.user.language
    link = _link_un_clic_a_peticions(db, peticion.user.email, lang, request.state.tenant)
    nombre = peticion.user.name or ""
    precio = payload.estimated_price
    send_email(
        to=peticion.user.email,
        subject=translate(db, "email.peticion_price_ready.subject", lang, disco=disco),
        body=translate(
            db, "email.peticion_price_ready.body_text", lang,
            nombre=nombre, disco=disco, precio=precio, link=link, nom=request.state.tenant.nombre,
        ),
        tenant=request.state.tenant,
        db=db,
        html=render_email_html(
            translate(db, "email.peticion_price_ready.heading", lang),
            translate(db, "email.peticion_price_ready.body_html", lang, disco=disco, precio=precio),
            request.state.tenant, db,
            cta=(translate(db, "email.peticion_price_ready.cta", lang), link),
        ),
    )
    return _peticion_admin_out(_get_peticion_or_404(db, peticion.id))


@router.post("/peticiones/{peticion_id}/vincular-solicitud", status_code=201, response_model=SolicitudCompraLineaOut)
def vincular_peticion_a_solicitud(peticion_id: uuid.UUID, payload: PeticionVincularIn, db: Session = Depends(get_db)):
    """Un cop el client ha acceptat el preu: afegeix una línia al pool
    (`origen='peticion_cliente'`, encara sense sol·licitud) per aquest
    release. Es consolidarà en una sol·licitud numerada més endavant, junt
    amb altres línies si convé (veure `generar_solicitud`)."""
    peticion = _get_peticion_or_404(db, peticion_id)
    if peticion.status != EstadoPeticionCliente.acceptada:
        raise HTTPException(409, "Només es pot vincular una petició ja acceptada pel client")
    if peticion.release_id is None:
        raise HTTPException(422, "La petició no té un disc catalogat")

    linea = SolicitudCompraLinea(
        solicitud_id=None, origen=OrigenSolicitud.peticion_cliente, release_id=peticion.release_id,
        quantity=payload.cantidad, proveedor_sugerido_id=payload.proveedor_sugerido_id,
    )
    db.add(linea)
    db.flush()

    peticion.solicitud_compra_linea_id = linea.id
    peticion.status = EstadoPeticionCliente.en_tramit
    db.commit()
    db.refresh(linea)
    return _solicitud_linea_out(linea)


@router.post("/peticiones/{peticion_id}/vincular-item", response_model=PeticionClienteAdminOut)
def vincular_item_peticion(
    peticion_id: uuid.UUID, payload: PeticionVincularItemIn, request: Request, db: Session = Depends(get_db),
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
    _enviar_email_item_arribat(db, peticion, request.state.tenant)

    return _peticion_admin_out(_get_peticion_or_404(db, peticion.id))


@router.patch("/peticiones/{peticion_id}/cancelar", response_model=PeticionClienteAdminOut)
def cancelar_peticion_admin(peticion_id: uuid.UUID, db: Session = Depends(get_db)):
    peticion = _get_peticion_or_404(db, peticion_id)
    if peticion.status in (EstadoPeticionCliente.recollida, EstadoPeticionCliente.cancelada):
        raise HTTPException(409, "Aquesta petició no es pot cancel·lar en el seu estat actual")
    peticion.status = EstadoPeticionCliente.cancelada
    db.commit()
    return _peticion_admin_out(_get_peticion_or_404(db, peticion.id))
