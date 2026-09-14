import os

# Debe fijarse ANTES de importar nada de app (get_settings está cacheado)
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["REFRESH_COOKIE_PATH"] = "/auth"  # sin Caddy delante no hay prefijo /api
# Clave pública de pruebas de Redsys (la misma que usa su documentación de
# integración/sandbox): sirve para firmar y verificar en los tests sin
# depender de credenciales reales del banco.
os.environ["REDSYS_MERCHANT_CODE"] = "999008881"
os.environ["REDSYS_SECRET_KEY"] = "sq7HjrUOBfKmC576ILgskD5srU870gJ7"
os.environ["REDSYS_NOTIFY_URL"] = "https://testserver/api/checkout/pay/redsys/notify"
# TestClient reutiliza la misma IP sintética en todas las peticiones: sin esto
# el rate limiting de /auth/* agotaría el límite entre tests distintos.
os.environ["RATE_LIMIT_ENABLED"] = "false"

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from app import models  # noqa: F401  registra las tablas
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import AccountingJurisdiction, ConfiguracioBotiga, Tenant, Vertical
from app.services.comptabilitat_seed import seed_chart_of_accounts
from app.tenant_secrets import TenantSecrets


@pytest.fixture()
def db():
    Base.metadata.create_all(engine)
    session = SessionLocal()
    # get_db (ver app/database.py) resuelve tenant por el header Host de
    # cada request — TestClient(base_url="https://testserver") manda
    # "testserver", así que el dominio sembrado aquí tiene que coincidir
    # exactamente para que cualquier test resuelva tenant sin configurar
    # nada. Se fija en session.info (no en un ContextVar, ver el porqué en
    # el docstring de app/tenancy.py) también aquí y no solo en `client`,
    # porque este fixture se usa a menudo solo, sin pasar por get_db, para
    # sembrar datos directamente — sin esto, el filtro automático de tenant
    # no dejaría ver ni escribir nada.
    # Sembrado antes de cualquier Tenant: Tenant.vertical_id es FK a
    # verticals.id (ver docs/ARQUITECTURA_CORE_VERTICAL.md), y este fixture
    # es dependencia de todos los tests que siembran tenants adicionales
    # directamente (test_multi_tenant.py, test_fase4.py, ...), así que
    # sembrarlo aquí una vez cubre todos los casos.
    session.add_all([
        Vertical(id="records", name_ca="Discos", name_es="Discos", name_en="Records"),
        Vertical(id="floristry", name_ca="Floristeria", name_es="Floristería", name_en="Florist"),
        # Igual que Vertical arriba: create_tenant() valida contra esta
        # tabla (ver accounting_registry.py), no basta con el default "es"
        # de Tenant.accounting_jurisdiction_id.
        AccountingJurisdiction(id="es", name="España", tax_model="eu_vat", active=True),
    ])
    tenant = Tenant(slug="test-tenant", domain="testserver", nombre="Test Tenant", vertical_id="records")
    session.add(tenant)
    session.commit()
    session.info["tenant_id"] = tenant.id
    config = ConfiguracioBotiga(fiscal_name="Test Tenant", address="Test")
    session.add(config)
    # flush antes de fijar discogs_habilitat: ese campo pasó a vivir en
    # TenantFeature (ver models.py::ConfiguracioBotiga._set_feature), que
    # necesita config ya adjunto a la sesión y con tenant_id resuelto —
    # ninguna de las dos cosas existe todavía como kwarg del constructor.
    session.flush()
    # discogs_habilitat=True: el vertical por defecto de este test suite es
    # discos/Discogs (ver require_discogs_enabled, routers/admin.py) — sin
    # esto, cualquier test que pegue directo a una ruta /admin/discogs/*
    # sin pasar antes por /admin/configuracio vería 404 en vez del
    # comportamiento que prueba.
    config.discogs_habilitat = True
    # Sin esto, cualquier operación que dispare el motor de posting
    # (checkout, TPV, despeses, banc, caixa diaria — ver
    # services/comptabilitat_posting.py) fallaría con "compte no trobat":
    # el pla de comptes no es crea solo, lo siembra create_tenant() en el
    # flujo real (ver services/comptabilitat_seed.py).
    seed_chart_of_accounts(session, "es", "sl")
    session.commit()
    # Expira los objetos sembrados aquí (tenant, config...) antes de ceder la
    # sesión al test: sin esto, `config` sigue vivo como variable local de
    # este generador (suspendido en el `yield`) durante todo el test, así
    # que cualquier `db.get(ConfiguracioBotiga, ...)` en el test devolvería
    # el objeto cacheado de ANTES del setup en vez de re-consultar — visible
    # sobre todo cuando un endpoint escribe con otra sesión (la de
    # `client`/`get_db`) y el test relee con `db` esperando el valor nuevo.
    session.expire_all()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


class _FakeSecretsManagerClient:
    """Sustituto en memoria del cliente boto3 de Secrets Manager para tests.
    Implementa solo lo que usa app/tenant_secrets.py (get/put_secret_value,
    create_secret) con los mismos códigos de error que la API real, para que
    _is_not_found() y el fallback de create_secret en set_tenant_secret()
    sigan funcionando igual."""

    def __init__(self):
        self._store: dict[str, str] = {}

    @staticmethod
    def _error(code: str, op: str, secret_id: str) -> ClientError:
        return ClientError({"Error": {"Code": code, "Message": secret_id}}, op)

    def get_secret_value(self, SecretId):
        if SecretId not in self._store:
            raise self._error("ResourceNotFoundException", "GetSecretValue", SecretId)
        return {"SecretString": self._store[SecretId]}

    def put_secret_value(self, SecretId, SecretString):
        if SecretId not in self._store:
            raise self._error("ResourceNotFoundException", "PutSecretValue", SecretId)
        self._store[SecretId] = SecretString
        return {}

    def create_secret(self, Name, SecretString):
        if Name in self._store:
            raise self._error("ResourceExistsException", "CreateSecret", Name)
        self._store[Name] = SecretString
        return {}


@pytest.fixture(autouse=True)
def _no_real_aws_secrets(monkeypatch):
    """Red de seguridad: ningún test debe llegar jamás al AWS Secrets Manager
    real. `_fake_tenant_secrets` de abajo solo mockea `get_tenant_secrets` en
    los routers que lo importan explícitamente — no cubre
    `provision_tenant_secret` (alta de tenant, routers/superadmin.py) ni
    `set_tenant_secret` (routers/configuracio.py). Sin esto, cada
    `POST /superadmin/tenants` en test_superadmin_roles.py creaba un secreto
    real en la cuenta de AWS de quien corriera los tests (encontrados 85
    secretos huérfanos `saaswebstore/tenants/<uuid>` acumulados en
    producción, nunca borrados, ~34€/mes de coste). Mockear aquí a nivel de
    `_sm_client` cubre TODO el módulo de una vez, para que ningún test futuro
    dependa de acordarse de mockear la función concreta que le toque."""
    fake_client = _FakeSecretsManagerClient()
    monkeypatch.setattr("app.tenant_secrets._sm_client", lambda: fake_client)


@pytest.fixture(autouse=True)
def _fake_tenant_secrets(monkeypatch):
    """Los tests corren sin Redis/AWS reales (eso se prueba aparte contra
    LocalStack, ver plan de la Fase 2) — así que `get_tenant_secrets` se
    sustituye por uno que devuelve directamente las variables de entorno
    de prueba de arriba (REDSYS_MERCHANT_CODE/SECRET_KEY), para que firmar
    y verificar Redsys en los tests siga funcionando igual que antes de que
    las credenciales pasaran a ser por tenant. `get_tenant_secrets` se
    importa con `from ..tenant_secrets import get_tenant_secrets` en cada
    router que lo usa — monkeypatchear solo `app.tenant_secrets.get_tenant_secrets`
    NO afectaría a esas referencias ya vinculadas, hay que parchear cada
    módulo importador por su nombre."""
    secrets = TenantSecrets(
        redsys_merchant_code=os.environ.get("REDSYS_MERCHANT_CODE"),
        redsys_terminal=os.environ.get("REDSYS_TERMINAL", "1"),
        redsys_secret_key=os.environ.get("REDSYS_SECRET_KEY"),
        discogs_token=os.environ.get("DISCOGS_TOKEN"),
        spotify_client_id=os.environ.get("SPOTIFY_CLIENT_ID"),
        spotify_client_secret=os.environ.get("SPOTIFY_CLIENT_SECRET"),
        holded_api_key="test-holded-key",
    )
    fake = lambda tenant_id: secrets  # noqa: E731
    for module in (
        "app.routers.checkout", "app.routers.subscripcions_public", "app.routers.spotify",
        "app.routers.comptabilitat.holded",
    ):
        monkeypatch.setattr(f"{module}.get_tenant_secrets", fake, raising=False)


@pytest.fixture()
def client(db):
    # Depende de `db` (aunque no se use el nombre): garantiza que las tablas
    # y el tenant de pruebas existen incluso en los tests que solo piden
    # `client`, porque cualquier endpoint que pase por get_db necesita
    # resolver un tenant o devuelve 404 antes de llegar al router.
    # https: la cookie de refresh lleva Secure y no viajaría por http
    return TestClient(app, base_url="https://testserver")
