"""Sincronització nocturna del catàleg amb el Google Sheet (export CSV
públic de Discogs). Veure app/services/catalog_sync.py pel comportament
detallat (afegeix nous, retira els que ja no hi són, mai toca preus)."""

import logging

import httpx

from ..celery_app import celery_app
from ..config import get_settings
from ..database import SessionLocal
from ..services.catalog_sync import apply_sync, diff_catalog, parse_sheet_csv
from ..services.emailer import send_email

log = logging.getLogger(__name__)


@celery_app.task(name="catalog.sync_discogs_sheet")
def sync_discogs_sheet() -> dict:
    settings = get_settings()
    if not settings.catalog_sheet_csv_url:
        log.info("catalog sync: CATALOG_SHEET_CSV_URL no configurat, es salta")
        return {"skipped": True}

    resp = httpx.get(settings.catalog_sheet_csv_url, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    sheet_codis = parse_sheet_csv(resp.text)

    db = SessionLocal()
    try:
        diff = diff_catalog(db, sheet_codis)
        result = apply_sync(db, sheet_codis, diff)
    finally:
        db.close()

    log.info(
        "catalog sync: %s afegits, %s retirats, %s errors (sheet: %s files)",
        result["creados"], result["retirados"], result["errores"], len(sheet_codis),
    )

    if settings.catalog_sync_notify_email and (result["creados"] or result["retirados"] or result["errores"]):
        cos = (
            f"Sincronització nocturna del catàleg amb el Google Sheet:\n\n"
            f"- {result['creados']} discos nous afegits\n"
            f"- {result['retirados']} còpies marcades com a retirades (ja no són al sheet)\n"
            f"- {result['errores']} errors\n"
        )
        try:
            send_email(
                to=settings.catalog_sync_notify_email,
                subject="Sync catàleg Discogs — resum nocturn",
                body=cos,
                html=f"<pre>{cos}</pre>",
            )
        except Exception:
            log.warning("catalog sync: no s'ha pogut enviar l'email de resum", exc_info=True)

    return result
