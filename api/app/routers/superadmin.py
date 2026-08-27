"""Panel de superadmin de plataforma (Fase 2) — ve y gestiona todos los
tenants, identidad de autenticación separada de la de cada tienda (ver
services/superadmin_security.py).

Reglas de aislamiento de este router, no negociables:
- Alcanzable SOLO por el dominio dedicado `SuperAdminSettings.superadmin_host`
  (ver `_require_superadmin_host`) — Caddy enruta /api/* sin mirar el Host,
  así que sin esto el panel sería atacable desde el dominio de cualquier
  tenant.
- `/login` lleva límite de tasa estricto — es el único punto de entrada de
  credenciales de todo el panel.
- Solo los endpoints genuinamente cross-tenant (listar todos) usan
  `get_db_unscoped` sin más. Cualquier endpoint que actúe SOBRE un tenant
  concreto entra en `scoped_to(db, tenant_id)` — dejar todo el router sin
  filtrar de principio a fin es el mismo tipo de descuido que en la Fase 1
  causó el bug de StockHold (una consulta sin acotar por tenant no falla ni
  avisa, solo toca filas de todos a la vez).
"""

import re
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_superadmin_settings
from ..database import get_db_unscoped
from ..models import (
    BillingPeriod, ConfiguracioBotiga, Order, PlatformAdmin, PlatformAdminAuditLog, PlatformAdminRole,
    PlatformInvoice, PlatformInvoiceStatus, PlatformPlan, Tenant, TenantBilling, TenantBillingStatus,
    TenantFeature, TipusIva, TramEnviament, Vertical,
)
from ..rate_limit import limiter
from ..schemas import TenantSecretsStatusOut
from ..services.security import hash_password, verify_password
from ..services.superadmin_security import (
    create_superadmin_token, record_audit, require_superadmin, require_superadmin_role,
)
from ..tenancy import scoped_to
from ..tenant_secrets import TenantSecrets, get_tenant_secrets, provision_tenant_secret
from scripts.seed_legal_pages import seed as seed_legal_pages
from scripts.seed_translations import seed as seed_translations

router = APIRouter(prefix="/superadmin", tags=["superadmin"])


def _require_superadmin_host(request: Request) -> None:
    host = request.headers.get("host", "").split(":")[0]
    if host != get_superadmin_settings().superadmin_host:
        # 404, no 401/403: no revelar ni que este router existe a quien
        # llegue por el dominio de un tenant cualquiera.
        raise HTTPException(404)


class SuperAdminLoginIn(BaseModel):
    email: str
    password: str


class SuperAdminLoginOut(BaseModel):
    access_token: str


TENANT_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,28}[a-z0-9])?$")


class TenantCreateIn(BaseModel):
    slug: str
    # Opcional: si no se da, create_tenant() lo calcula como
    # "<slug>.platform_domain" (ver SuperAdminSettings.platform_domain) — el
    # tenant "nace" en un subdominio de la plataforma y puede pasarse a su
    # propio dominio después con PATCH /tenants/{id}, sin tocar esto.
    domain: str | None = None
    nombre: str
    fiscal_name: str
    address: str
    vertical_id: str = "records"

    @field_validator("slug")
    @classmethod
    def _valid_slug(cls, v: str) -> str:
        # El slug se usa tal cual como etiqueta DNS cuando no se da domain
        # (ver arriba) — minúsculas/dígitos/guión, sin guión al principio o
        # final, para que "<slug>.platform_domain" sea siempre un hostname
        # válido (RFC 1035), no solo un identificador interno.
        if not TENANT_SLUG_RE.match(v):
            raise ValueError(
                "El slug ha de ser minúscules/dígits/guions (sense guió al principi o final), "
                "p. ex. 'florqa' — s'utilitza tal qual com a subdomini"
            )
        return v


class TenantOut(BaseModel):
    id: uuid.UUID
    slug: str
    domain: str
    nombre: str
    vertical_id: str
    activo: bool


class TenantUpdateIn(BaseModel):
    # slug fuera a propósito: es el identificador técnico estable, editarlo
    # no aporta nada que no dé ya crear un tenant nuevo y no vale la pena el
    # riesgo de que algo lo tenga cacheado/hardcodeado en otro sitio.
    nombre: str | None = None
    domain: str | None = None
    vertical_id: str | None = None
    activo: bool | None = None


class VerticalOut(BaseModel):
    id: str
    name_ca: str
    name_es: str
    name_en: str
    active: bool

    model_config = {"from_attributes": True}


VERTICAL_ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,29}$")


class VerticalCreateIn(BaseModel):
    id: str
    name_ca: str
    name_es: str
    name_en: str
    active: bool = True

    @field_validator("id")
    @classmethod
    def _valid_slug(cls, v: str) -> str:
        # Mismo criterio que Tenant.slug: minúsculas/dígitos/guión bajo,
        # empieza por letra — evita un id con espacios/mayúsculas que luego
        # aparecería tal cual en URLs (`Tenant.vertical_id`) y en el <select>
        # del superadmin.
        if not VERTICAL_ID_RE.match(v):
            raise ValueError("L'id ha de ser minúscules/dígits/guió baix, començant per una lletra (p. ex. 'floristry')")
        return v


class VerticalUpdateIn(BaseModel):
    # id fora a propòsit, mateix criteri que Tenant.slug a TenantUpdateIn:
    # és l'identificador tècnic estable (viu com a FK a tenants.vertical_id).
    name_ca: str | None = None
    name_es: str | None = None
    name_en: str | None = None
    active: bool | None = None


class PlatformAdminOut(BaseModel):
    id: uuid.UUID
    email: str
    nombre: str | None
    role: PlatformAdminRole
    activo: bool

    model_config = {"from_attributes": True}


class PlatformAdminCreateIn(BaseModel):
    email: str
    password: str
    nombre: str | None = None
    role: PlatformAdminRole

    @field_validator("password")
    @classmethod
    def _password_min_length(cls, v: str) -> str:
        # Mismo mínimo que scripts/create_superadmin.py, para no tener dos
        # criterios de fortaleza distintos según por dónde se cree el admin.
        if len(v) < 8:
            raise ValueError("La contrasenya ha de tenir mínim 8 caràcters")
        return v


class PlatformAdminUpdateIn(BaseModel):
    # email/nombre/password fora a propòsit d'aquesta primera versió: només
    # role i activo, que és el que calia per "convidar/desactivar" (canviar
    # contrasenya d'un altre operador és una funcionalitat a part, no
    # demanada encara).
    role: PlatformAdminRole | None = None
    activo: bool | None = None


# Único vocabulario de feature_key que existe hoy en el código (ver
# models/configuracio.py::ConfiguracioBotiga.discogs_habilitat/.subscripcions_actives)
# — no hay tabla de registro para esto (a diferencia de `Vertical`), sería
# sobre-ingeniería para 2 valores. Si esto crece, se revisita con el mismo
# criterio que ya se aplicó al registro de verticals en su momento.
KNOWN_FEATURES: list[tuple[str, str]] = [
    ("discogs_sync", "Discogs sync"),
    ("subscriptions", "Club de subscripció"),
]


class TenantFeatureOut(BaseModel):
    feature_key: str
    label: str
    enabled: bool


class TenantFeatureUpdateIn(BaseModel):
    enabled: bool


class AuditLogOut(BaseModel):
    id: int
    platform_admin_id: uuid.UUID | None
    action: str
    target_tenant_id: uuid.UUID | None
    details: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FeatureAdoptionOut(BaseModel):
    feature_key: str
    label: str
    enabled_count: int
    total_tenants: int


class TenantHealthOut(BaseModel):
    tenant_id: uuid.UUID
    nombre: str
    slug: str
    vertical_id: str
    total_orders: int
    orders_last_7d: int
    last_order_at: datetime | None


def _json_safe(value):
    # Els `details` de l'audit log es guarden com a JSON — Decimal/UUID/
    # datetime no ho són nativament, a diferència dels canvis de tenant/
    # vertical/admin que fins ara només movien str/bool/enum(str).
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (uuid.UUID, datetime)):
        return str(value)
    return value


class PlatformPlanOut(BaseModel):
    id: uuid.UUID
    name: str
    price: Decimal
    currency: str
    billing_period: BillingPeriod
    revolut_plan_id: str | None
    revolut_variation_id: str | None
    active: bool

    model_config = {"from_attributes": True}


class PlatformPlanCreateIn(BaseModel):
    name: str
    price: Decimal
    currency: str = "EUR"
    billing_period: BillingPeriod = BillingPeriod.monthly
    # Enganxats a mà des del dashboard de Revolut mentre no hi ha
    # credencials de sandbox per crear-los via API (ver models/platform.py).
    revolut_plan_id: str | None = None
    revolut_variation_id: str | None = None
    active: bool = True


class PlatformPlanUpdateIn(BaseModel):
    name: str | None = None
    price: Decimal | None = None
    currency: str | None = None
    billing_period: BillingPeriod | None = None
    revolut_plan_id: str | None = None
    revolut_variation_id: str | None = None
    active: bool | None = None


class TenantBillingOut(BaseModel):
    tenant_id: uuid.UUID
    plan_id: uuid.UUID | None
    plan_name: str | None
    revolut_customer_id: str | None
    revolut_subscription_id: str | None
    status: TenantBillingStatus
    current_period_end: datetime | None


class TenantBillingUpdateIn(BaseModel):
    # Tot opcional i editable a mà: mentre no hi ha integració amb l'API de
    # Revolut provada, l'operador reflecteix aquí el que ja ha fet des del
    # seu dashboard (crear customer, desar targeta, crear subscripció).
    plan_id: uuid.UUID | None = None
    revolut_customer_id: str | None = None
    revolut_subscription_id: str | None = None
    status: TenantBillingStatus | None = None
    current_period_end: datetime | None = None


class PlatformInvoiceOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    amount: Decimal
    currency: str
    status: PlatformInvoiceStatus
    period_start: datetime | None
    period_end: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BancStatusOut(BaseModel):
    # Estat de la integració de Revolut en si (no d'un tenant concret) —
    # apartat separat de "Plans": aquí és on es respon "està connectat el
    # banc?", no "quant costa cada pla".
    webhook_configured: bool
    invoices_count: int
    last_invoice_at: datetime | None


class TenantBillingSummaryOut(BaseModel):
    # Una fila per tenant actiu — la vista "qui paga, quant i com" que
    # abans només es veia entrant al detall de cada tenant un per un.
    tenant_id: uuid.UUID
    nombre: str
    slug: str
    plan_id: uuid.UUID | None
    plan_name: str | None
    status: TenantBillingStatus
    last_invoice_at: datetime | None


class PlatformInvoiceWithTenantOut(PlatformInvoiceOut):
    tenant_nombre: str


@router.post("/login", response_model=SuperAdminLoginOut)
@limiter.limit("5/hour")
def login(
    request: Request, payload: SuperAdminLoginIn, db=Depends(get_db_unscoped),
    _host=Depends(_require_superadmin_host),
):
    admin = db.scalar(select(PlatformAdmin).where(PlatformAdmin.email == payload.email.lower()))
    if admin is None or not admin.activo or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(401, "Credenciales inválidas")
    return SuperAdminLoginOut(access_token=create_superadmin_token(admin))


@router.get("/me", response_model=PlatformAdminOut, dependencies=[Depends(_require_superadmin_host)])
def get_me(admin: PlatformAdmin = Depends(require_superadmin)):
    # Para que el frontend sepa qué rol tiene el admin logueado (mostrar el
    # badge, ocultar acciones que igualmente el backend rechazaría) sin
    # tener que decodificar el JWT en el cliente.
    return admin


@router.get("/verticals", response_model=list[VerticalOut], dependencies=[Depends(_require_superadmin_host)])
def list_verticals(
    include_inactive: bool = False,
    db=Depends(get_db_unscoped), _admin: PlatformAdmin = Depends(require_superadmin),
):
    # Fuente única para el <select> de alta de tenant del frontend (que
    # vol només els actius, comportament per defecte que no toquem) i,
    # amb include_inactive, per a la pantalla de gestió de verticals — antes
    # era un array duplicado a mano en web/app/superadmin/page.jsx.
    query = select(Vertical).order_by(Vertical.id)
    if not include_inactive:
        query = query.where(Vertical.active)
    return db.scalars(query).all()


@router.post(
    "/verticals", response_model=VerticalOut, status_code=201,
    dependencies=[Depends(_require_superadmin_host)],
)
def create_vertical(
    payload: VerticalCreateIn, db=Depends(get_db_unscoped),
    admin: PlatformAdmin = Depends(require_superadmin_role(PlatformAdminRole.owner)),
):
    if db.get(Vertical, payload.id):
        raise HTTPException(409, f"Ja existeix un vertical amb id '{payload.id}'")
    vertical = Vertical(**payload.model_dump())
    db.add(vertical)
    db.commit()
    record_audit(db, admin, "vertical.create", details={"id": vertical.id})
    return vertical


@router.patch(
    "/verticals/{vertical_id}", response_model=VerticalOut,
    dependencies=[Depends(_require_superadmin_host)],
)
def update_vertical(
    vertical_id: str, payload: VerticalUpdateIn, db=Depends(get_db_unscoped),
    admin: PlatformAdmin = Depends(require_superadmin_role(PlatformAdminRole.owner)),
):
    vertical = db.get(Vertical, vertical_id)
    if vertical is None:
        raise HTTPException(404, "Vertical no trobat")
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(vertical, key, value)
    db.commit()
    if changes:
        record_audit(db, admin, "vertical.update", details={"id": vertical_id, **changes})
    return vertical


@router.get("/tenants", response_model=list[TenantOut], dependencies=[Depends(_require_superadmin_host)])
def list_tenants(
    db=Depends(get_db_unscoped), _admin: PlatformAdmin = Depends(require_superadmin),
):
    # Genuinamente cross-tenant: listar todos. Único endpoint de este router
    # que se deja sin scoped_to a propósito.
    tenants = db.scalars(select(Tenant).order_by(Tenant.nombre)).all()
    return [_tenant_out(t) for t in tenants]


@router.post("/tenants", response_model=TenantOut, status_code=201, dependencies=[Depends(_require_superadmin_host)])
def create_tenant(
    payload: TenantCreateIn, db=Depends(get_db_unscoped),
    admin: PlatformAdmin = Depends(require_superadmin_role(PlatformAdminRole.owner)),
):
    if db.scalar(select(Tenant).where(Tenant.slug == payload.slug)):
        raise HTTPException(409, f"Ya existe un tenant con slug '{payload.slug}'")
    # Sin domain explícito, el tenant nace en su propio subdominio de la
    # plataforma (requiere un DNS wildcard *.platform_domain — ver
    # SuperAdminSettings.platform_domain) y puede pasarse a un dominio
    # propio más tarde con PATCH /tenants/{id}, sin migración de por medio.
    domain = payload.domain or f"{payload.slug}.{get_superadmin_settings().platform_domain}"
    if db.scalar(select(Tenant).where(Tenant.domain == domain)):
        raise HTTPException(409, f"Ya existe un tenant con domain '{domain}'")
    if not db.scalar(select(Vertical).where(Vertical.id == payload.vertical_id, Vertical.active)):
        raise HTTPException(422, f"Vertical '{payload.vertical_id}' no existe o no está activo")

    tenant = Tenant(slug=payload.slug, domain=domain, nombre=payload.nombre, vertical_id=payload.vertical_id)
    db.add(tenant)
    db.flush()

    # A partir de aquí ya existe tenant.id: entra en scoped_to para que las
    # filas sembradas se creen con su tenant_id correcto (el autofill de
    # app/tenancy.py lee el tenant activo de la sesión, que hasta este
    # punto no tenía ninguno puesto).
    with scoped_to(db, tenant.id):
        config = ConfiguracioBotiga(fiscal_name=payload.fiscal_name, address=payload.address, reservation_minutes=20)
        db.add(config)
        # flush antes de tocar discogs_habilitat: ese campo vive en
        # TenantFeature (ver models.py::ConfiguracioBotiga._set_feature), que
        # necesita config.tenant_id ya resuelto por el autofill de tenancy.py
        # y config adjunto a la sesión — ninguna de las dos cosas existe
        # todavía como kwarg del constructor de arriba.
        db.flush()
        # Deriva del vertical elegido — Discogs solo tiene sentido para
        # "records". subscripcions_actives se queda en su default (False)
        # sea cual sea el vertical, igual que ya pasa hoy para recordstore.
        config.discogs_habilitat = payload.vertical_id == "records"
        # Sin un tipo de IVA por defecto, el checkout no tendría ninguno que
        # aplicar — valor genérico razonable, editable después desde el
        # admin del tenant (ver routers/configuracio.py).
        db.add(TipusIva(
            name="IVA general", percentage=Decimal("21.00"),
            is_rebu=False, default_new=True, default_used=True, active=True,
        ))
        # Tramo placeholder DESACTIVADO a propósito: sin él el checkout no
        # tendría ningún tramo de envío, pero adivinar tarifas/pesos reales
        # en nombre del tenant sería peor que forzarlo a configurar los
        # suyos antes de activar envíos.
        db.add(TramEnviament(country="ES", max_weight_g=999999, price=Decimal("0.00"), active=False))
        db.flush()
        # Traducciones de UI + páginas legales: gestionadas por desarrollo/
        # superadmin, no por el tenant (ver scripts/seed_translations.py,
        # scripts/seed_legal_pages.py) — se siembran aquí para que un
        # tenant nuevo no arranque con el admin en crudo (claves sin
        # traducir) ni sin páginas de privacidad/términos.
        seed_translations(db, tenant.id)
        seed_legal_pages(db, tenant.id)
        db.commit()

    provision_tenant_secret(tenant.id)
    record_audit(
        db, admin, "tenant.create", target_tenant_id=tenant.id,
        details={"slug": tenant.slug, "domain": tenant.domain, "vertical_id": tenant.vertical_id},
    )

    return _tenant_out(tenant)


def _get_tenant_or_404(db, tenant_id: uuid.UUID) -> Tenant:
    # Tenant no hereda de TenantScoped: esta búsqueda es siempre válida, sea
    # cual sea (o ninguno) el tenant activo de la sesión en este momento.
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(404, "Tenant no encontrado")
    return tenant


def _tenant_out(tenant: Tenant) -> TenantOut:
    return TenantOut(
        id=tenant.id, slug=tenant.slug, domain=tenant.domain, nombre=tenant.nombre,
        vertical_id=tenant.vertical_id, activo=tenant.activo,
    )


@router.get("/tenants/{tenant_id}", response_model=TenantOut, dependencies=[Depends(_require_superadmin_host)])
def get_tenant(
    tenant_id: uuid.UUID, db=Depends(get_db_unscoped), _admin: PlatformAdmin = Depends(require_superadmin),
):
    return _tenant_out(_get_tenant_or_404(db, tenant_id))


@router.patch("/tenants/{tenant_id}", response_model=TenantOut, dependencies=[Depends(_require_superadmin_host)])
def update_tenant(
    tenant_id: uuid.UUID, payload: TenantUpdateIn, db=Depends(get_db_unscoped),
    admin: PlatformAdmin = Depends(require_superadmin_role(PlatformAdminRole.owner)),
):
    tenant = _get_tenant_or_404(db, tenant_id)
    changes = payload.model_dump(exclude_unset=True)

    if "domain" in changes and changes["domain"] != tenant.domain:
        if db.scalar(select(Tenant).where(Tenant.domain == changes["domain"], Tenant.id != tenant_id)):
            raise HTTPException(409, f"Ya existe un tenant con domain '{changes['domain']}'")
    if "vertical_id" in changes and changes["vertical_id"] != tenant.vertical_id:
        if not db.scalar(select(Vertical).where(Vertical.id == changes["vertical_id"], Vertical.active)):
            raise HTTPException(422, f"Vertical '{changes['vertical_id']}' no existe o no está activo")

    was_active = tenant.activo
    for key, value in changes.items():
        setattr(tenant, key, value)
    db.commit()
    db.refresh(tenant)

    # Auditar la suspensión/reactivación como una acción propia, distinta de
    # "tenant.update" — es la mutación con más impacto real de este endpoint
    # (corta storefront+admin+API del tenant, ver tenancy.py::resolve_tenant_by_domain),
    # merece ser buscable en el audit log por su propio nombre de acción.
    if "activo" in changes and changes["activo"] != was_active:
        record_audit(
            db, admin, "tenant.suspend" if not changes["activo"] else "tenant.reactivate",
            target_tenant_id=tenant.id,
        )
    other_changes = {k: v for k, v in changes.items() if k != "activo"}
    if other_changes:
        record_audit(db, admin, "tenant.update", target_tenant_id=tenant.id, details=other_changes)

    return _tenant_out(tenant)


@router.get(
    "/tenants/{tenant_id}/features", response_model=list[TenantFeatureOut],
    dependencies=[Depends(_require_superadmin_host)],
)
def list_tenant_features(
    tenant_id: uuid.UUID, db=Depends(get_db_unscoped), _admin: PlatformAdmin = Depends(require_superadmin),
):
    _get_tenant_or_404(db, tenant_id)
    # scoped_to en vez de filtrar a mano: TenantFeature hereda TenantScoped,
    # y get_db_unscoped no aplica ningún filtro automático (ver
    # app/tenancy.py) — sin esto se verían las filas de TODOS los tenants.
    with scoped_to(db, tenant_id):
        enabled_by_key = {f.feature_key: f.enabled for f in db.scalars(select(TenantFeature)).all()}
    return [
        TenantFeatureOut(feature_key=key, label=label, enabled=enabled_by_key.get(key, False))
        for key, label in KNOWN_FEATURES
    ]


@router.patch(
    "/tenants/{tenant_id}/features/{feature_key}", response_model=TenantFeatureOut,
    dependencies=[Depends(_require_superadmin_host)],
)
def update_tenant_feature(
    tenant_id: uuid.UUID, feature_key: str, payload: TenantFeatureUpdateIn, db=Depends(get_db_unscoped),
    admin: PlatformAdmin = Depends(require_superadmin_role(PlatformAdminRole.owner)),
):
    _get_tenant_or_404(db, tenant_id)
    known = dict(KNOWN_FEATURES)
    if feature_key not in known:
        raise HTTPException(404, f"Feature '{feature_key}' no reconeguda")

    with scoped_to(db, tenant_id):
        feature = db.scalar(select(TenantFeature).where(TenantFeature.feature_key == feature_key))
        if feature is None:
            db.add(TenantFeature(tenant_id=tenant_id, feature_key=feature_key, enabled=payload.enabled))
        else:
            feature.enabled = payload.enabled
        db.commit()

    record_audit(
        db, admin, "tenant_feature.toggle", target_tenant_id=tenant_id,
        details={"feature_key": feature_key, "enabled": payload.enabled},
    )
    return TenantFeatureOut(feature_key=feature_key, label=known[feature_key], enabled=payload.enabled)


@router.get(
    "/tenants/{tenant_id}/secrets", response_model=TenantSecretsStatusOut,
    dependencies=[Depends(_require_superadmin_host)],
)
def get_tenant_secrets_status(
    tenant_id: uuid.UUID, db=Depends(get_db_unscoped), _admin: PlatformAdmin = Depends(require_superadmin),
):
    """Solo lectura (Fase 5): el operador ve si cada tenant tiene sus
    secretos configurados, pero ya no puede escribirlos — eso es cosa
    exclusiva del propio tenant, ver POST /admin/secrets en
    routers/configuracio.py."""
    _get_tenant_or_404(db, tenant_id)
    secrets_: TenantSecrets = get_tenant_secrets(tenant_id)
    return TenantSecretsStatusOut(**{k: bool(v) for k, v in secrets_.model_dump().items()})


@router.get("/audit-log", response_model=list[AuditLogOut], dependencies=[Depends(_require_superadmin_host)])
def list_audit_log(
    tenant_id: uuid.UUID | None = None, limit: int = 100,
    db: Session = Depends(get_db_unscoped), _admin: PlatformAdmin = Depends(require_superadmin),
):
    # Lectura: cualquier rol autenticado puede consultarlo, no solo owner —
    # es precisamente lo que un rol `support` necesita poder ver.
    query = select(PlatformAdminAuditLog).order_by(PlatformAdminAuditLog.created_at.desc()).limit(min(limit, 500))
    if tenant_id is not None:
        query = query.where(PlatformAdminAuditLog.target_tenant_id == tenant_id)
    return db.scalars(query).all()


@router.get("/admins", response_model=list[PlatformAdminOut], dependencies=[Depends(_require_superadmin_host)])
def list_admins(
    db=Depends(get_db_unscoped), _admin: PlatformAdmin = Depends(require_superadmin),
):
    # Lectura: igual que /audit-log, disponible per a qualsevol rol
    # autenticat — un `support` també ha de poder veure qui més té accés.
    return db.scalars(select(PlatformAdmin).order_by(PlatformAdmin.email)).all()


@router.post(
    "/admins", response_model=PlatformAdminOut, status_code=201,
    dependencies=[Depends(_require_superadmin_host)],
)
def create_admin(
    payload: PlatformAdminCreateIn, db=Depends(get_db_unscoped),
    admin: PlatformAdmin = Depends(require_superadmin_role(PlatformAdminRole.owner)),
):
    # Substitueix scripts/create_superadmin.py per a l'ús habitual (queda
    # com a via de recuperació en fred si no hi ha cap owner actiu que
    # pugui fer servir aquest endpoint).
    email = payload.email.strip().lower()
    if db.scalar(select(PlatformAdmin).where(PlatformAdmin.email == email)):
        raise HTTPException(409, f"Ja existeix un operador amb email '{email}'")
    new_admin = PlatformAdmin(
        email=email, password_hash=hash_password(payload.password),
        nombre=payload.nombre, role=payload.role,
    )
    db.add(new_admin)
    db.commit()
    record_audit(db, admin, "admin.create", details={"email": email, "role": payload.role.value})
    return new_admin


def _active_owner_count(db: Session, exclude_id: uuid.UUID | None = None) -> int:
    query = select(func.count()).select_from(PlatformAdmin).where(
        PlatformAdmin.role == PlatformAdminRole.owner, PlatformAdmin.activo,
    )
    if exclude_id is not None:
        query = query.where(PlatformAdmin.id != exclude_id)
    return db.scalar(query)


@router.patch(
    "/admins/{admin_id}", response_model=PlatformAdminOut,
    dependencies=[Depends(_require_superadmin_host)],
)
def update_admin(
    admin_id: uuid.UUID, payload: PlatformAdminUpdateIn, db=Depends(get_db_unscoped),
    admin: PlatformAdmin = Depends(require_superadmin_role(PlatformAdminRole.owner)),
):
    target = db.get(PlatformAdmin, admin_id)
    if target is None:
        raise HTTPException(404, "Operador no trobat")
    changes = payload.model_dump(exclude_unset=True)

    # Guarda de seguretat: no permetre que la plataforma es quedi sense cap
    # owner actiu (ni tan sols si qui ho intenta és l'únic owner actuant
    # sobre si mateix) — seria un bloqueig sense recuperació des del propi
    # panell, només arreglable editant la BD a mà.
    stops_being_active_owner = (
        target.role == PlatformAdminRole.owner and target.activo
        and (
            ("role" in changes and changes["role"] != PlatformAdminRole.owner)
            or ("activo" in changes and changes["activo"] is False)
        )
    )
    if stops_being_active_owner and _active_owner_count(db, exclude_id=target.id) == 0:
        raise HTTPException(409, "No es pot deixar la plataforma sense cap operador 'owner' actiu")

    for key, value in changes.items():
        setattr(target, key, value)
    db.commit()
    if changes:
        record_audit(db, admin, "admin.update", details={"email": target.email, **changes})
    return target


@router.get(
    "/dashboard/features", response_model=list[FeatureAdoptionOut],
    dependencies=[Depends(_require_superadmin_host)],
)
def dashboard_features(
    db=Depends(get_db_unscoped), _admin: PlatformAdmin = Depends(require_superadmin),
):
    # Denominador = tenants actius (un tenant suspès no és "no ha adoptat la
    # feature", és fora de joc) — mateix criteri que la resta del dashboard.
    total_tenants = db.scalar(select(func.count()).select_from(Tenant).where(Tenant.activo)) or 0
    enabled_by_key = dict(db.execute(
        select(TenantFeature.feature_key, func.count())
        .join(Tenant, Tenant.id == TenantFeature.tenant_id)
        .where(TenantFeature.enabled, Tenant.activo)
        .group_by(TenantFeature.feature_key)
    ).all())
    return [
        FeatureAdoptionOut(
            feature_key=key, label=label,
            enabled_count=enabled_by_key.get(key, 0), total_tenants=total_tenants,
        )
        for key, label in KNOWN_FEATURES
    ]


@router.get(
    "/dashboard/tenant-health", response_model=list[TenantHealthOut],
    dependencies=[Depends(_require_superadmin_host)],
)
def dashboard_tenant_health(
    db=Depends(get_db_unscoped), _admin: PlatformAdmin = Depends(require_superadmin),
):
    # Tres consultes agrupades separades en lloc d'una amb FILTER (WHERE...):
    # més portable (funciona igual sobre el SQLite dels tests) i prou clar
    # per a un endpoint de baix trànsit com aquest.
    since = datetime.now(timezone.utc) - timedelta(days=7)
    totals = dict(db.execute(select(Order.tenant_id, func.count()).group_by(Order.tenant_id)).all())
    recent = dict(db.execute(
        select(Order.tenant_id, func.count())
        .where(Order.created_at >= since)
        .group_by(Order.tenant_id)
    ).all())
    last_order_at = dict(db.execute(
        select(Order.tenant_id, func.max(Order.created_at)).group_by(Order.tenant_id)
    ).all())

    tenants = db.scalars(select(Tenant).where(Tenant.activo).order_by(Tenant.nombre)).all()
    return [
        TenantHealthOut(
            tenant_id=t.id, nombre=t.nombre, slug=t.slug, vertical_id=t.vertical_id,
            total_orders=totals.get(t.id, 0), orders_last_7d=recent.get(t.id, 0),
            last_order_at=last_order_at.get(t.id),
        )
        for t in tenants
    ]


# ---------------------------------------------------------------------------
# Facturació de plataforma (Revolut) — ver models/platform.py per al context
# complet de per què `revolut_*` s'edita a mà en lloc de crear-se via API.
# ---------------------------------------------------------------------------

@router.get("/plans", response_model=list[PlatformPlanOut], dependencies=[Depends(_require_superadmin_host)])
def list_plans(
    db=Depends(get_db_unscoped), _admin: PlatformAdmin = Depends(require_superadmin),
):
    return db.scalars(select(PlatformPlan).order_by(PlatformPlan.price)).all()


@router.post(
    "/plans", response_model=PlatformPlanOut, status_code=201,
    dependencies=[Depends(_require_superadmin_host)],
)
def create_plan(
    payload: PlatformPlanCreateIn, db=Depends(get_db_unscoped),
    admin: PlatformAdmin = Depends(require_superadmin_role(PlatformAdminRole.owner)),
):
    plan = PlatformPlan(**payload.model_dump())
    db.add(plan)
    db.commit()
    record_audit(db, admin, "plan.create", details={"name": plan.name, "price": str(plan.price)})
    return plan


@router.patch(
    "/plans/{plan_id}", response_model=PlatformPlanOut,
    dependencies=[Depends(_require_superadmin_host)],
)
def update_plan(
    plan_id: uuid.UUID, payload: PlatformPlanUpdateIn, db=Depends(get_db_unscoped),
    admin: PlatformAdmin = Depends(require_superadmin_role(PlatformAdminRole.owner)),
):
    plan = db.get(PlatformPlan, plan_id)
    if plan is None:
        raise HTTPException(404, "Pla no trobat")
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(plan, key, value)
    db.commit()
    if changes:
        record_audit(
            db, admin, "plan.update",
            details={"id": str(plan_id), **{k: _json_safe(v) for k, v in changes.items()}},
        )
    return plan


def _tenant_billing_out(tb: TenantBilling, plan_name: str | None) -> TenantBillingOut:
    return TenantBillingOut(
        tenant_id=tb.tenant_id, plan_id=tb.plan_id, plan_name=plan_name,
        revolut_customer_id=tb.revolut_customer_id, revolut_subscription_id=tb.revolut_subscription_id,
        status=tb.status, current_period_end=tb.current_period_end,
    )


def _get_or_create_billing(db, tenant_id: uuid.UUID) -> TenantBilling:
    tb = db.get(TenantBilling, tenant_id)
    if tb is None:
        # La fila no existeix fins que algú la toca — un tenant nou comença
        # "sense_pla" sense necessitat de sembrar-la a create_tenant.
        tb = TenantBilling(tenant_id=tenant_id)
        db.add(tb)
        db.commit()
        db.refresh(tb)
    return tb


@router.get(
    "/tenants/{tenant_id}/billing", response_model=TenantBillingOut,
    dependencies=[Depends(_require_superadmin_host)],
)
def get_tenant_billing(
    tenant_id: uuid.UUID, db=Depends(get_db_unscoped), _admin: PlatformAdmin = Depends(require_superadmin),
):
    _get_tenant_or_404(db, tenant_id)
    tb = _get_or_create_billing(db, tenant_id)
    plan = db.get(PlatformPlan, tb.plan_id) if tb.plan_id else None
    return _tenant_billing_out(tb, plan.name if plan else None)


@router.patch(
    "/tenants/{tenant_id}/billing", response_model=TenantBillingOut,
    dependencies=[Depends(_require_superadmin_host)],
)
def update_tenant_billing(
    tenant_id: uuid.UUID, payload: TenantBillingUpdateIn, db=Depends(get_db_unscoped),
    admin: PlatformAdmin = Depends(require_superadmin_role(PlatformAdminRole.owner)),
):
    _get_tenant_or_404(db, tenant_id)
    tb = _get_or_create_billing(db, tenant_id)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("plan_id") is not None and not db.get(PlatformPlan, changes["plan_id"]):
        raise HTTPException(422, "Pla no trobat")

    for key, value in changes.items():
        setattr(tb, key, value)
    db.commit()
    if changes:
        record_audit(
            db, admin, "tenant_billing.update", target_tenant_id=tenant_id,
            details={k: _json_safe(v) for k, v in changes.items()},
        )
    plan = db.get(PlatformPlan, tb.plan_id) if tb.plan_id else None
    return _tenant_billing_out(tb, plan.name if plan else None)


@router.get(
    "/tenants/{tenant_id}/invoices", response_model=list[PlatformInvoiceOut],
    dependencies=[Depends(_require_superadmin_host)],
)
def list_tenant_invoices(
    tenant_id: uuid.UUID, db=Depends(get_db_unscoped), _admin: PlatformAdmin = Depends(require_superadmin),
):
    _get_tenant_or_404(db, tenant_id)
    query = (
        select(PlatformInvoice).where(PlatformInvoice.tenant_id == tenant_id)
        .order_by(PlatformInvoice.created_at.desc())
    )
    return db.scalars(query).all()


# ---------------------------------------------------------------------------
# "Banc" — apartat separat de Plans: aquí es respon "està connectada la
# integració de pagaments?" i "qui paga i qui no", no "quant costa cada
# pla". Plans es queda com a catàleg de preus pur.
# ---------------------------------------------------------------------------

@router.get("/banc/status", response_model=BancStatusOut, dependencies=[Depends(_require_superadmin_host)])
def banc_status(
    db=Depends(get_db_unscoped), _admin: PlatformAdmin = Depends(require_superadmin),
):
    webhook_configured = bool(get_superadmin_settings().revolut_webhook_signing_secret)
    invoices_count = db.scalar(select(func.count()).select_from(PlatformInvoice)) or 0
    last_invoice_at = db.scalar(select(func.max(PlatformInvoice.created_at)))
    return BancStatusOut(
        webhook_configured=webhook_configured, invoices_count=invoices_count, last_invoice_at=last_invoice_at,
    )


@router.get(
    "/banc/tenants", response_model=list[TenantBillingSummaryOut],
    dependencies=[Depends(_require_superadmin_host)],
)
def banc_tenants(
    db=Depends(get_db_unscoped), _admin: PlatformAdmin = Depends(require_superadmin),
):
    tenants = db.scalars(select(Tenant).where(Tenant.activo).order_by(Tenant.nombre)).all()
    billings = {tb.tenant_id: tb for tb in db.scalars(select(TenantBilling)).all()}
    plans = {p.id: p for p in db.scalars(select(PlatformPlan)).all()}
    last_invoice_by_tenant = dict(db.execute(
        select(PlatformInvoice.tenant_id, func.max(PlatformInvoice.created_at))
        .group_by(PlatformInvoice.tenant_id)
    ).all())

    result = []
    for t in tenants:
        tb = billings.get(t.id)
        plan = plans.get(tb.plan_id) if tb and tb.plan_id else None
        result.append(TenantBillingSummaryOut(
            tenant_id=t.id, nombre=t.nombre, slug=t.slug,
            plan_id=tb.plan_id if tb else None, plan_name=plan.name if plan else None,
            status=tb.status if tb else TenantBillingStatus.sense_pla,
            last_invoice_at=last_invoice_by_tenant.get(t.id),
        ))
    return result


@router.get(
    "/banc/invoices", response_model=list[PlatformInvoiceWithTenantOut],
    dependencies=[Depends(_require_superadmin_host)],
)
def banc_invoices(
    limit: int = 100, db=Depends(get_db_unscoped), _admin: PlatformAdmin = Depends(require_superadmin),
):
    query = (
        select(PlatformInvoice, Tenant.nombre)
        .join(Tenant, Tenant.id == PlatformInvoice.tenant_id)
        .order_by(PlatformInvoice.created_at.desc())
        .limit(min(limit, 500))
    )
    return [
        PlatformInvoiceWithTenantOut(
            id=inv.id, tenant_id=inv.tenant_id, amount=inv.amount, currency=inv.currency,
            status=inv.status, period_start=inv.period_start, period_end=inv.period_end,
            created_at=inv.created_at, tenant_nombre=nombre,
        )
        for inv, nombre in db.execute(query).all()
    ]
