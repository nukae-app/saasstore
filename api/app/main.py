from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

from .config import get_settings
from .rate_limit import limiter
from .routers import (
    admin, admin_newsletter, admin_subscripcions, admin_users, auth, blog, cart, catalog, checkout,
    comptabilitat, configuracio, erp, health, i18n, me, newsletter_public, spotify,
    subscripcions_public,
)

app = FastAPI(
    title="Ultra-Local Records API",
    description="Tienda de discos + comunidad. El front (Next.js) consume esta API; nada más toca la base de datos.",
    version="0.1.0",
    root_path="/api",
)

# Rate limiting por IP (usado sobre todo en los endpoints de auth, ver auth.py)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Necesario para el flujo OAuth de authlib (guarda el state en una cookie firmada)
app.add_middleware(SessionMiddleware, secret_key=get_settings().secret_key, https_only=True)

app.include_router(catalog.router)
app.include_router(auth.router)
app.include_router(cart.router)
app.include_router(checkout.router)
app.include_router(admin.router)
app.include_router(blog.router)
app.include_router(erp.router)
app.include_router(comptabilitat.router)
app.include_router(configuracio.router)
app.include_router(configuracio.public_router)
app.include_router(admin_users.router)
app.include_router(admin_newsletter.router)
app.include_router(admin_subscripcions.router)
app.include_router(newsletter_public.router)
app.include_router(i18n.router)
app.include_router(me.router)
app.include_router(spotify.router)
app.include_router(spotify.public_router)
app.include_router(subscripcions_public.router)
app.include_router(health.router)

# /metrics (Prometheus): bloquejat a Caddy perquè no sigui públic (veure
# infra/Caddyfile), Alloy hi accedeix directament dins la xarxa Docker.
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
