import json
import os
from functools import lru_cache

from pydantic_settings import BaseSettings


def _load_secrets_from_aws(env_var_name: str) -> None:
    """Si la variable `env_var_name` està definida, carrega el secret
    d'AWS Secrets Manager que apunta cap a variables d'entorn, abans que
    pydantic-settings les llegeixi. En local, sense aquesta variable, es
    continua fent servir el .env de sempre.

    Es crida dues vegades amb noms diferents: `AWS_SECRETS_NAME` (secret de
    plataforma — DB, JWT dels usuaris de cada tenant, APIs externes
    compartides) i `AWS_SUPERADMIN_SECRETS_NAME` (secret separat del
    superadmin — Fase 2, ver `SuperAdminSettings` — a propòsit un secret
    diferent, no el mateix, perquè una fuga d'un mai serveixi per falsificar
    tokens de l'altre)."""
    secret_name = os.environ.get(env_var_name)
    if not secret_name:
        return
    import boto3

    client = boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION", "eu-west-1"))
    payload = json.loads(client.get_secret_value(SecretId=secret_name)["SecretString"])
    for key, value in payload.items():
        # setdefault, no assignació directa: una variable ja present a l'entorn
        # (p. ex. injectada amb `docker compose exec -e` per a un script puntual)
        # ha de guanyar sobre el que digui el secret, no ser trepitjada.
        os.environ.setdefault(key, value)


_load_secrets_from_aws("AWS_SECRETS_NAME")
_load_secrets_from_aws("AWS_SUPERADMIN_SECRETS_NAME")


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://ultralocal:ultralocal@localhost:5432/ultralocal"
    # Per defecte de SQLAlchemy (5+10=15 connexions) és massa poc: amb ~30-50
    # peticions concurrents al catàleg s'exhaureix i les peticions es queden
    # esperant fins pool_timeout, la qual cosa pot arrossegar Caddy a un estat
    # penjat riu amunt (vist en un test de càrrega real). Els valors per
    # defecte d'aquí estan pensats per db.t4g.micro (RDS_MAX_CONNECTIONS=79,
    # veure `SHOW max_connections`).
    #
    # IMPORTANT: cada procés Uvicorn (veure UVICORN_WORKERS al Dockerfile) i
    # cada procés Celery (concurrency) crea el seu propi engine/pool — aquest
    # valor és PER PROCÉS, no total. Amb UVICORN_WORKERS=2, l'api ja gasta
    # fins a 2×(20+20)=80 en el pitjor cas, per si sol per damunt del límit
    # de 79. Es reparteix el mateix pressupost total ja validat (40) entre
    # els 2 processos: 20 → 10 cadascun. Deixa marge per al worker de Celery
    # (concurrency=2, pool propi amb els mateixos defaults) + beat + marge
    # per a migracions/psql manual. Si es puja UVICORN_WORKERS o la instància
    # RDS, recalcular: (uvicorn_workers × (pool+overflow)) + (celery_concurrency
    # × (pool+overflow)) + marge, ha d'entrar còmode sota max_connections.
    db_pool_size: int = 10
    db_max_overflow: int = 10
    # Més curt que el per defecte (30s): sota sobrecàrrega és millor fallar
    # ràpid (error 500 al cap de pocs segons) que deixar peticions penjades
    # fins a 30s cadascuna, que és el que va acabar saturant Caddy.
    db_pool_timeout: int = 10
    redis_url: str = "redis://redis:6379/0"

    secret_key: str = "dev-secret-cambiame"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    # frontend_url ya NO es un campo de aquí (Fase 2): era global y estaba
    # roto de facto con más de un tenant — se calcula siempre desde
    # Tenant.domain, ver app/tenancy.py::tenant_frontend_url.
    # Path de la cookie de refresh TAL COMO LO VE EL NAVEGADOR (con el
    # prefijo /api que añade Caddy). Si cambias el enrutado, cambia esto.
    refresh_cookie_path: str = "/api/auth"

    google_client_id: str = ""
    google_client_secret: str = ""

    # discogs_token, spotify_client_id/secret: Fase 2 los movió a
    # app/tenant_secrets.py (uno por tenant en Secrets Manager) — ya NO son
    # campos de aquí. spotify_enabled se queda global a propósito (kill
    # switch de plataforma, no hay señal de que deba ser por tenant).
    spotify_enabled: bool = True

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    # email_from ya NO es un campo de aquí (Fase 2): pasó a
    # ConfiguracioBotiga.email_from, una fila por tenant.

    dev_admin_bypass: bool = False
    # Desactivado en tests (conftest.py): con TestClient todas las peticiones
    # comparten la misma IP sintética y agotarían el límite entre tests.
    rate_limit_enabled: bool = True

    # Minutos de validez de un magic link
    magic_link_minutes: int = 15
    # Horas de validez del enlace de verificación de email tras el registro con contraseña
    email_verification_hours: int = 48

    # Redsys (TPV Virtual, p. ej. vía Kutxabank). "test" usa sis-t.redsys.es;
    # "production" usa sis.redsys.es. La clave secreta la da el banco al
    # activar el TPV virtual (una para pruebas, otra para producción).
    redsys_merchant_code: str = ""
    redsys_terminal: str = "1"
    redsys_secret_key: str = ""
    redsys_environment: str = "test"  # test | production
    redsys_notify_url: str = ""  # p. ej. https://tudominio.com/api/checkout/pay/redsys/notify

    # Sincronització nocturna del catàleg amb el Google Sheet (export CSV
    # públic de Discogs). Si es deixa buit, la tasca no fa res.
    catalog_sheet_csv_url: str = ""
    # Si es defineix, s'envia un resum per email després de cada sincronització.
    catalog_sync_notify_email: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


class SuperAdminSettings(BaseSettings):
    """Settings del realm de superadmin (Fase 2) — separado por completo del
    `Settings` de arriba: clave de firma JWT propia (`superadmin_secret_key`),
    distinta de `Settings.secret_key` (la de los usuarios de cada tienda).
    Cargado una vez al arrancar, como `Settings` — a diferencia de
    `app/tenant_secrets.py`, aquí no hace falta resolución dinámica por
    request: solo hay un superadmin, no uno por tenant."""

    superadmin_secret_key: str = "dev-superadmin-secret-cambiame"
    # Dominio dedicado desde el que se sirve /superadmin/* — Caddy enruta
    # /api/* al contenedor api sin mirar el Host, así que sin esta
    # comprobación el panel sería alcanzable (y atacable por fuerza bruta en
    # el login) desde el dominio de CUALQUIER tenant. Ver routers/superadmin.py.
    superadmin_host: str = "superadmin.localhost"
    # Secreto de firma de los webhooks de Revolut Business (facturación de
    # plataforma a los tenants, NO el checkout de cada tienda) — vive aquí,
    # no en tenant_secrets.py, porque es la plataforma quien cobra, no cada
    # tenant por su cuenta. Vacío por defecto: sin él, el endpoint del
    # webhook rechaza cualquier payload (ver routers/billing_webhooks.py).
    revolut_webhook_signing_secret: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_superadmin_settings() -> SuperAdminSettings:
    return SuperAdminSettings()
