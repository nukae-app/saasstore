"""Alta pública al club del disc i captura del token de cobrament recurrent.

Mateix esquelet de 3 passos que `checkout.py`, però sense carret ni reserva
d'estoc (encara no se sap quin disc rebrà: això ho decideix l'admin al
primer cicle, veure services/subscripcions.py):

1. POST /subscripcions/alta -> crea la `Subscripcio` en `pendent_pagament`
   i un `CobramentSubscripcio` en `pendent`, i retorna els camps signats
   per redirigir a Redsys amb `DS_MERCHANT_IDENTIFIER=REQUIRED`.
2. POST /subscripcions/pay/redsys/notify -> notificació server-to-server.
   Si s'autoritza: guarda l'`Ds_Merchant_Identifier` reutilitzable, activa
   la subscripció i fixa `proxima_facturacio`. Si es denega: descarta
   l'alta (l'usuari pot tornar-ho a provar des de zero).
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..tenancy import tenant_frontend_url
from ..tenant_secrets import get_tenant_secrets
from ..models import (
    Address, CobramentSubscripcio, ConfiguracioBotiga, ConfiguracioSubscripcio, EstatCobrament,
    EstatSubscripcio, Subscripcio, User,
)
from ..schemas import ConfiguracioSubscripcioOut, SubscripcioAltaIn
from ..services import redsys
from ..services.subscripcions import GENERES_DISCOGS, proxima_facturacio_alta, proxima_facturacio_seguent
from ..services.security import get_current_user

router = APIRouter(prefix="/subscripcions", tags=["subscripcions"])


def _subscripcions_actives(db: Session) -> bool:
    config = db.scalar(select(ConfiguracioBotiga))
    return bool(config and config.subscripcions_actives)


@router.get("/generes", response_model=list[str])
def list_generes():
    """Llista tancada de gèneres (taxonomia de Discogs) que el client pot
    triar com a preferits — veure GENERES_DISCOGS."""
    return GENERES_DISCOGS


@router.get("/config", response_model=ConfiguracioSubscripcioOut)
def get_config_subscripcio(db: Session = Depends(get_db)):
    if not _subscripcions_actives(db):
        raise HTTPException(404, "El club del disc no està actiu")
    config = db.scalar(select(ConfiguracioSubscripcio))
    if config is None:
        raise HTTPException(404, "El club del disc no està actiu")
    return config


@router.post("/alta")
def alta_subscripcio(
    payload: SubscripcioAltaIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _subscripcions_actives(db):
        raise HTTPException(404, "El club del disc no està actiu")

    config = db.scalar(select(ConfiguracioSubscripcio))
    if config is None:
        raise HTTPException(404, "El club del disc no està actiu")
    if payload.periodicitat_mesos not in config.periodicitats_mesos_disponibles:
        raise HTTPException(422, "Periodicitat no disponible")
    if payload.quantitat not in config.quantitats_disponibles:
        raise HTTPException(422, "Quantitat no disponible")

    address = db.get(Address, payload.address_id)
    if address is None or address.user_id != user.id:
        raise HTTPException(404, "Adreça no trobada")

    ja_activa = db.scalar(
        select(Subscripcio).where(
            Subscripcio.user_id == user.id,
            Subscripcio.estat.in_([EstatSubscripcio.pendent_pagament, EstatSubscripcio.activa, EstatSubscripcio.pausada]),
        )
    )
    if ja_activa is not None:
        raise HTTPException(409, "Ja tens una subscripció activa")

    # Cicle a què pertany aquesta alta (data de tall = penúltim divendres
    # del mes): si la finestra d'aquest mes ja ha tancat, el primer
    # enviament serà el cicle següent, encara que el cobrament es faci avui
    # mateix (veure services/subscripcions.py::proxima_facturacio_alta).
    cicle = proxima_facturacio_alta(date.today())

    preu_periode = config.preu_per_disc * payload.quantitat
    subscripcio = Subscripcio(
        user_id=user.id,
        address_id=address.id,
        generes_preferits=payload.generes_preferits,
        periodicitat_mesos=payload.periodicitat_mesos,
        quantitat=payload.quantitat,
        preu_periode=preu_periode,
        estat=EstatSubscripcio.pendent_pagament,
        proxima_facturacio=cicle,
    )
    db.add(subscripcio)
    db.flush()

    ds_order = redsys.generate_ds_order()
    cobrament = CobramentSubscripcio(
        subscripcio_id=subscripcio.id,
        periode=cicle,
        import_=preu_periode,
        estat=EstatCobrament.pendent,
        ds_order=ds_order,
    )
    db.add(cobrament)
    db.commit()

    frontend_url = tenant_frontend_url(request.state.tenant)
    form = redsys.build_payment_form(
        ds_order=ds_order, importe=preu_periode, order_id_for_url=str(subscripcio.id), identifier="REQUIRED",
        tenant=request.state.tenant,
        secrets=get_tenant_secrets(request.state.tenant.id),
        environment=get_settings().redsys_environment,
        url_ok=f"{frontend_url}/subscripcio/alta-ok",
        url_ko=f"{frontend_url}/subscripcio/alta-ko",
        # Redsys ha de notificar aquest endpoint (que busca un
        # CobramentSubscripcio), no el de checkout (busca un Payment i no
        # el trobaria mai per a una alta de subscripció — el cobrament es
        # quedaria "pendent" per sempre).
        notify_url=f"{frontend_url}/api/subscripcions/pay/redsys/notify",
    )
    return {"subscripcio_id": str(subscripcio.id), **form}


@router.post("/pay/redsys/notify")
async def redsys_notify_alta(request: Request, db: Session = Depends(get_db)):
    """Notificació server-to-server de Redsys per a l'alta d'una subscripció
    (captura del token COF). Les renovacions periòdiques NO passen per aquí:
    són cobraments síncrons via `services/subscripcions.py::facturar_subscripcio`.

    NOTA (Fase 2): el club de suscripción sigue fuera de alcance — igual que
    `services/redsys.py::charge_recurring`, esto sigue leyendo
    `Settings.redsys_secret_key` global en vez de por tenant. Además, a
    diferencia del webhook de checkout, este usa `get_db` normal (resuelve
    tenant por Host), que en la práctica ya rechaza esta notificación porque
    el servidor de Redsys no manda un Host de ningún tenant — necesitaría el
    mismo tratamiento de `get_db_unscoped` + resolución en dos fases que
    checkout.py::redsys_notify, y CobramentSubscripcio/Subscripcio aún no
    tienen tenant_id (Fase 1 tampoco las tocó). No se arregla aquí porque
    reactivar el club de suscripción está fuera del alcance de esta fase."""
    form = await request.form()
    params_b64 = form.get("Ds_MerchantParameters")
    signature = form.get("Ds_Signature")
    if not params_b64 or not signature:
        raise HTTPException(400, "Notificació incompleta")

    params = redsys.verify_signature(params_b64, signature, get_settings().redsys_secret_key)
    if params is None:
        raise HTTPException(400, "Firma invàlida")

    ds_order = params.get("Ds_Order") or params.get("Ds_Merchant_Order")
    cobrament = db.scalar(select(CobramentSubscripcio).where(CobramentSubscripcio.ds_order == ds_order))
    if cobrament is None:
        raise HTTPException(404, "Cobrament no trobat")
    if cobrament.estat != EstatCobrament.pendent:
        return {"status": "ja processat"}  # idempotència: Redsys pot reintentar la notificació

    cobrament.raw_notification = params
    subscripcio = db.get(Subscripcio, cobrament.subscripcio_id)

    if redsys.is_authorised(params.get("Ds_Response")):
        cobrament.estat = EstatCobrament.cobrat
        subscripcio.redsys_identifier = params.get("Ds_Merchant_Identifier")
        subscripcio.redsys_cof_txnid = params.get("Ds_Merchant_Cof_Txnid")
        subscripcio.estat = EstatSubscripcio.activa
        subscripcio.proxima_facturacio = proxima_facturacio_seguent(cobrament.periode, subscripcio.periodicitat_mesos)
        db.commit()
    else:
        # Descartem l'intent sencer (no només marcar-lo "fallit"): és una
        # alta que mai ha arribat a existir de cara al client, que pot
        # tornar-ho a provar des de zero. `cobrament` apunta a `subscripcio`
        # amb NOT NULL, cal esborrar-lo primer.
        db.delete(cobrament)
        db.delete(subscripcio)
        db.commit()

    return {"status": "ok"}
