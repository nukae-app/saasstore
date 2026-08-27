from fastapi import HTTPException, Request
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()
engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    pool_size=_settings.db_pool_size,
    max_overflow=_settings.db_max_overflow,
    pool_timeout=_settings.db_pool_timeout,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db(request: Request):
    """Cada router ya depende de esta función (`Depends(get_db)`), así que
    resolver aquí el tenant de la request aplica el aislamiento multi-tenant
    a todos los routers sin tocarlos uno a uno — ver app/tenancy.py."""
    # Import diferido: tenancy.py importa app.models, que a su vez importa
    # `Base` de este módulo — un import a nivel de módulo aquí crearía un
    # ciclo (database -> tenancy -> models -> database).
    from .tenancy import apply_local_tenant, resolve_tenant_by_domain

    db: Session = SessionLocal()
    try:
        # Esta consulta ya abre la primera transacción de la request, con
        # tenant_id todavía sin resolver — por eso apply_local_tenant() hace
        # falta explícita después (ver su docstring), no basta con el
        # listener after_begin.
        # X-Forwarded-Host antes que Host: el propio contenedor `web` hace
        # fetch SSR directo contra `api` (API_INTERNAL_URL, sin pasar por
        # Caddy) — el Host de ESA conexión es el del contenedor, no el
        # dominio del tenant que pidió la página. `fetch()` de Node/undici
        # no permite fijar `Host` a mano (lo gestiona la propia conexión),
        # así que el front reenvía el Host original en X-Forwarded-Host en
        # su lugar (ver web/app/lib/api.js). El tráfico real de navegador
        # vía Caddy nunca manda este header, así que no cambia nada ahí.
        host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
        tenant = resolve_tenant_by_domain(db, host)
        if tenant is None:
            raise HTTPException(404, "Tienda no encontrada para este dominio")
        request.state.tenant = tenant
        db.info["tenant_id"] = tenant.id
        apply_local_tenant(db)
        yield db
    finally:
        db.close()


def get_db_unscoped(request: Request):
    """Variante sin resolución de tenant por Host, para las pocas rutas que
    lo reciben desde fuera (el webhook de Redsys: lo llama el servidor de
    Redsys, no el navegador de una tienda, así que el Host no sirve). El
    propio endpoint debe resolver el tenant a mano (buscar el `Payment` por
    `ds_order` sin filtrar) y entrar en `tenancy.scoped_to(...)` una vez lo
    sepa — ver routers/checkout.py."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
