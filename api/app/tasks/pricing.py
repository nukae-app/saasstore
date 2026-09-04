"""Recalcula el pricing de ofertas de todos los tenants periódicamente.

Hace falta un ciclo periódico (además del recompute que ya se dispara al
crear/editar/(des)activar una `Offer` desde el panel, ver
`routers/admin/pricing.py`) porque criterios como `antiguedad_dias_min` o
`sin_venta_dias_min` cambian solos día a día sin que nadie toque nada —
un item puede empezar a matchear (o dejar de hacerlo) una oferta sin que
haya habido ninguna acción de admin, y lo mismo para `starts_at`/`ends_at`
de ofertas programadas."""

import logging

from sqlalchemy import select

from ..celery_app import celery_app
from ..database import SessionLocal
from ..models import Tenant
from ..services.pricing import recompute_tenant_pricing
from ..tenancy import scoped_to

log = logging.getLogger(__name__)


@celery_app.task(name="pricing.recompute_all_tenants")
def recompute_all_tenants() -> dict:
    """Misma estructura que `tasks/peticiones.py::release_expired_reservations`:
    sesión propia (no pasa por `get_db`, no hay request), itera los tenants
    activos y fija el tenant de la sesión en cada vuelta antes de tocar nada."""
    db = SessionLocal()
    total_applied = 0
    total_reverted = 0
    try:
        tenants = list(db.scalars(select(Tenant).where(Tenant.activo.is_(True))))
        for tenant in tenants:
            with scoped_to(db, tenant.id):
                try:
                    result = recompute_tenant_pricing(db)
                except Exception:
                    log.exception("pricing recompute: error en tenant %s", tenant.id)
                    db.rollback()
                    continue
                total_applied += result.applied
                total_reverted += result.reverted
    finally:
        db.close()
    log.info(
        "pricing recompute: %s tenants, %s items aplicados, %s revertidos",
        len(tenants), total_applied, total_reverted,
    )
    return {"tenants": len(tenants), "applied": total_applied, "reverted": total_reverted}
