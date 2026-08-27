"""Secretos por tenant: Redsys, Discogs, Spotify. Un secreto de AWS Secrets
Manager por tenant (`saaswebstore/tenants/{tenant_id}`), resuelto por
request con caché en Redis — a diferencia del `Settings` de plataforma
(`config.py`), no se pueden precargar al arrancar el proceso, porque no se
conocen todos los tenants de antemano.

Local (`AWS_ENDPOINT_URL=http://localstack:4566`, ver docker-compose.yml):
mismo código, apunta a LocalStack en vez de AWS real.
"""

import json
import logging
import os
import time
import uuid
from functools import lru_cache

import boto3
import redis
from botocore.exceptions import ClientError
from pydantic import BaseModel

from .config import get_settings

log = logging.getLogger(__name__)

SECRET_PREFIX = "saaswebstore/tenants"
CACHE_TTL_SECONDS = 300
LOCK_TTL_SECONDS = 5
LOCK_WAIT_SECONDS = 2.0


class TenantSecrets(BaseModel):
    redsys_merchant_code: str | None = None
    redsys_terminal: str | None = None
    redsys_secret_key: str | None = None
    discogs_token: str | None = None
    spotify_client_id: str | None = None
    spotify_client_secret: str | None = None


def _secret_id(tenant_id: uuid.UUID) -> str:
    return f"{SECRET_PREFIX}/{tenant_id}"


def _cache_key(tenant_id: uuid.UUID) -> str:
    return f"tenant_secret:{tenant_id}"


@lru_cache
def _sm_client():
    endpoint_url = os.environ.get("AWS_ENDPOINT_URL") or None
    return boto3.client(
        "secretsmanager",
        region_name=os.environ.get("AWS_REGION", "eu-west-1"),
        endpoint_url=endpoint_url,
    )


@lru_cache
def _redis_pool() -> redis.ConnectionPool:
    # Pool propio, no app/redis_client.py::get_redis_client() — ese está
    # pensado para pings de healthcheck (timeout de 2s, conexión nueva cada
    # vez). Este módulo vive en el camino caliente de cada checkout/sync,
    # necesita una conexión reutilizada del pool, no una por llamada.
    return redis.ConnectionPool.from_url(
        get_settings().redis_url, socket_connect_timeout=3, socket_timeout=3, max_connections=20
    )


def _redis() -> redis.Redis:
    return redis.Redis(connection_pool=_redis_pool())


def _is_not_found(exc: ClientError) -> bool:
    return exc.response.get("Error", {}).get("Code") == "ResourceNotFoundException"


def get_tenant_secrets(tenant_id: uuid.UUID) -> TenantSecrets:
    r = _redis()
    cache_key = _cache_key(tenant_id)
    try:
        cached = r.get(cache_key)
        if cached is not None:
            return TenantSecrets.model_validate_json(cached)
    except redis.RedisError:
        log.warning("tenant_secrets: Redis no disponible, se salta la caché (tenant=%s)", tenant_id)

    try:
        payload = _sm_client().get_secret_value(SecretId=_secret_id(tenant_id))["SecretString"]
    except ClientError as exc:
        # Solo "el secreto no existe todavía" se trata como "tenant sin
        # configurar". Cualquier otro fallo (throttling, permisos IAM, un
        # apagón de AWS) debe propagar como error — nunca cachearse como
        # "sin configurar", o un apagón de Secrets Manager se traduciría en
        # checkouts silenciosos con credenciales vacías durante el TTL.
        if not _is_not_found(exc):
            raise
        secrets = TenantSecrets()
    else:
        secrets = TenantSecrets.model_validate_json(payload)

    try:
        r.setex(cache_key, CACHE_TTL_SECONDS, secrets.model_dump_json())
    except redis.RedisError:
        pass  # el valor ya se ha resuelto bien; no tener caché no es motivo para fallar la request

    return secrets


def set_tenant_secret(tenant_id: uuid.UUID, **fields: str | None) -> TenantSecrets:
    """get-merge-put contra el secreto del tenant. Lock corto en Redis
    alrededor del ciclo lectura-escritura para que dos guardados
    concurrentes (dos pestañas del panel de admin, por ejemplo) no se pisen
    en silencio — si no se consigue el lock a tiempo, se guarda igualmente
    (mejor un guardado sin lock que uno que nunca se aplica), pero avisando
    en el log."""
    r = _redis()
    lock_key = f"tenant_secret_lock:{tenant_id}"
    got_lock = False
    deadline = time.monotonic() + LOCK_WAIT_SECONDS
    try:
        while time.monotonic() < deadline:
            try:
                got_lock = bool(r.set(lock_key, "1", nx=True, ex=LOCK_TTL_SECONDS))
            except redis.RedisError:
                log.warning("tenant_secrets: Redis no disponible, se guarda sin lock (tenant=%s)", tenant_id)
                break
            if got_lock:
                break
            time.sleep(0.1)
        else:
            log.warning("tenant_secrets: no se consiguió el lock a tiempo, se guarda igualmente (tenant=%s)", tenant_id)

        secret_id = _secret_id(tenant_id)
        try:
            current = json.loads(_sm_client().get_secret_value(SecretId=secret_id)["SecretString"])
        except ClientError as exc:
            if not _is_not_found(exc):
                raise
            current = {}
        current.update({k: v for k, v in fields.items() if v is not None})
        try:
            _sm_client().put_secret_value(SecretId=secret_id, SecretString=json.dumps(current))
        except ClientError as exc:
            # put_secret_value (a diferencia de get_secret_value) exige que el
            # secreto exista de antes — a diferencia de create_secret. Si
            # provision_tenant_secret nunca llegó a crearlo (fallo parcial en
            # el alta del tenant, o un tenant de antes de esta fase), hay que
            # crearlo aquí en vez de asumir que el PUT basta. Encontrado
            # verificando contra LocalStack real, no algo que un mock hubiera cazado.
            if not _is_not_found(exc):
                raise
            _sm_client().create_secret(Name=secret_id, SecretString=json.dumps(current))
        secrets = TenantSecrets.model_validate(current)
    finally:
        if got_lock:
            try:
                r.delete(lock_key)
            except redis.RedisError:
                pass

    try:
        r.setex(_cache_key(tenant_id), CACHE_TTL_SECONDS, secrets.model_dump_json())
    except redis.RedisError:
        log.warning(
            "tenant_secrets: no se pudo refrescar la caché tras guardar (tenant=%s) — "
            "el guardado en Secrets Manager sí tuvo éxito, no se debe reportar como fallo",
            tenant_id,
        )

    return secrets


def provision_tenant_secret(tenant_id: uuid.UUID) -> None:
    """Crea el secreto vacío para un tenant nuevo — ver alta de tenant en
    routers/superadmin.py. Idempotente: si ya existe, no hace nada."""
    try:
        # create_secret usa `Name`, no `SecretId` (a diferencia de
        # get/put_secret_value) — error real encontrado al verificar contra
        # LocalStack, no algo que ningún test unitario con mocks hubiera cazado.
        _sm_client().create_secret(Name=_secret_id(tenant_id), SecretString="{}")
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ResourceExistsException":
            return
        raise
