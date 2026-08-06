"""Allibera reserves de PeticionCliente caducades (recollida a botiga sense
pagar, 72h) i avisa el client per email. El propi flux de compra ja allibera
de forma mandrosa (veure services/reservations.py, release_expired es crida
abans de qualsevol operació d'estoc); aquesta tasca és el "backstop" perquè
no calgui esperar que algú faci un checkout o una venda per netejar-ho i
poder avisar el client encara que no passi res més a la botiga."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..celery_app import celery_app
from ..database import SessionLocal
from ..models import EstadoPeticionCliente, Item, PeticionCliente
from ..services.emailer import render_email_html, send_email
from ..services.i18n import frontend_url, translate
from ..services.reservations import release_expired
from ..services.security import create_magic_link_token

log = logging.getLogger(__name__)


@celery_app.task(name="peticiones.release_expired_reservations")
def release_expired_reservations() -> dict:
    db = SessionLocal()
    try:
        caducades = list(db.scalars(
            select(PeticionCliente)
            .join(Item, Item.id == PeticionCliente.item_id)
            .where(
                PeticionCliente.estado == EstadoPeticionCliente.reservada,
                Item.reserved_until.isnot(None),
                Item.reserved_until < datetime.now(timezone.utc),
            )
            .options(selectinload(PeticionCliente.release), selectinload(PeticionCliente.user))
        ))
        for peticion in caducades:
            disco = f"{peticion.release.artista} - {peticion.release.titulo}" if peticion.release else "el disc"
            lang = peticion.user.idioma
            motiu_key = (
                "email.peticion_reserva_alliberada.motiu_paga_botiga"
                if peticion.metodo_entrega_triat == "recollida_paga_botiga"
                else "email.peticion_reserva_alliberada.motiu_altres"
            )
            motiu = translate(db, motiu_key, lang, disco=disco)
            destinacio = f"/disc/{peticion.release_id}" if peticion.release_id else "/cataleg"
            raw = create_magic_link_token(db, peticion.user.email, timedelta(days=14))
            link = f"{frontend_url('/auth/magic', lang)}?token={raw}&next={destinacio}"
            nombre = peticion.user.nombre or ""
            send_email(
                to=peticion.user.email,
                subject=translate(db, "email.peticion_reserva_alliberada.subject", lang, disco=disco),
                body=translate(db, "email.peticion_reserva_alliberada.body_text", lang, nombre=nombre, motiu=motiu, link=link),
                html=render_email_html(
                    translate(db, "email.peticion_reserva_alliberada.heading", lang),
                    translate(db, "email.peticion_reserva_alliberada.body_html", lang, motiu=motiu),
                    cta=(translate(db, "email.peticion_reserva_alliberada.cta", lang), link),
                ),
            )

        released = release_expired(db)
        if caducades:
            log.info("peticiones: %d reserves caducades alliberades i notificades", len(caducades))
        return {"peticiones_caducadas": len(caducades), "items_alliberados": released}
    finally:
        db.close()
