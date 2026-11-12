"""Enviament massiu d'una campanya de newsletter, en segon pla."""

import secrets
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from ..celery_app import celery_app
from ..database import SessionLocal
from ..models import NewsletterCampaign, NewsletterCampaignStatus, NewsletterSend, NewsletterSendStatus, Tenant, User
from ..services.emailer import absolutize_upload_urls, newsletter_footer, send_email
from ..services.metrics import newsletter_send_result_total
from ..services.security import _hash
from ..tenancy import scoped_to, tenant_frontend_url

PAUSA_ENTRE_ENVIAMENTS_SEGONS = 0.5


@celery_app.task(name="newsletter.send_campaign")
def send_campaign(campaign_id: str, tenant_id: str) -> None:
    db = SessionLocal()
    try:
        tenant = db.get(Tenant, uuid.UUID(tenant_id))
        if tenant is None:
            return

        with scoped_to(db, tenant.id):
            # `NewsletterCampaign` es TenantScoped desde la Fase 3 — la
            # búsqueda tiene que ir DENTRO de scoped_to, o con RLS activado
            # no encontraría nada (bug real que llegó a estar en producción:
            # este db.get() se hacía antes de entrar en scoped_to).
            campaign = db.get(NewsletterCampaign, campaign_id)
            if campaign is None or campaign.status != NewsletterCampaignStatus.enviant:
                return

            # Només excloem els que ja s'han enviat amb èxit: si el worker va caure a mig
            # lot, les files 'pendent'/'error' anteriors es reutilitzen (amb token nou).
            ja_enviats = {
                s.user_id for s in campaign.sends if s.status == NewsletterSendStatus.enviat
            }
            existents_no_enviats = {
                s.user_id: s for s in campaign.sends if s.status != NewsletterSendStatus.enviat
            }
            destinataris = db.scalars(
                select(User).where(User.active == True, User.consent_newsletter == True)
            ).all()

            idiomes = {u.id: u.language for u in destinataris}

            # Genera el token d'un cop (només tenim el valor en clar aquí, abans de hashejar-lo).
            pendents = []
            for user in destinataris:
                if user.id in ja_enviats:
                    continue
                raw_token = secrets.token_urlsafe(32)
                enviament = existents_no_enviats.get(user.id)
                if enviament is None:
                    enviament = NewsletterSend(campaign_id=campaign.id, user_id=user.id, email=user.email)
                    db.add(enviament)
                enviament.unsubscribe_token_hash = _hash(raw_token)
                enviament.status = NewsletterSendStatus.pendent
                enviament.error_msg = None
                pendents.append((enviament, raw_token))
            db.commit()

            for enviament, raw_token in pendents:
                try:
                    base = tenant_frontend_url(tenant)
                    lang = idiomes.get(enviament.user_id, "ca")
                    # Pàgina de confirmació (el GET no dona de baixa: els
                    # escàners d'enllaços dels correus el visiten) i URL d'API
                    # per a la baixa en un clic (RFC 8058, Gmail/Yahoo).
                    unsubscribe_url = f"{base}/{lang}/newsletter/baixa?token={raw_token}"
                    one_click_url = f"{base}/api/newsletter/baixa?token={raw_token}"
                    footer_html, footer_text = newsletter_footer(tenant, db, unsubscribe_url, lang)
                    html = f"{absolutize_upload_urls(campaign.content_html, tenant)}{footer_html}"
                    send_email(
                        to=enviament.email,
                        subject=campaign.subject,
                        body=f"{campaign.subject}{footer_text}",
                        tenant=tenant,
                        db=db,
                        html=html,
                        headers={
                            "List-Unsubscribe": f"<{one_click_url}>",
                            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
                        },
                    )
                    enviament.status = NewsletterSendStatus.enviat
                    enviament.sent_at = datetime.now(timezone.utc)
                    newsletter_send_result_total.labels(result="enviat").inc()
                except Exception as exc:
                    enviament.status = NewsletterSendStatus.error
                    enviament.error_msg = str(exc)
                    newsletter_send_result_total.labels(result="error").inc()
                db.commit()
                time.sleep(PAUSA_ENTRE_ENVIAMENTS_SEGONS)

            campaign.status = NewsletterCampaignStatus.enviada
            campaign.sending_finished_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
