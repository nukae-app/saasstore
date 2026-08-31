import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from ._base import TenantScoped, _uuid


class Tenant(Base):
    """Un negocio/tienda del SaaS. No hereda de TenantScoped: es la tabla que
    define los tenants, no una tabla perteneciente a uno."""

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    # Dominio con el que se resuelve el tenant a partir del header Host de
    # cada request (ver app/tenancy.py). p.ej. "recordstore.tuplataforma.com"
    # o, en local/tests, "testserver"/"localhost".
    domain: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(200))
    # Vertical de negocio: decide qué campos/tabla de extensión aplican al
    # catàleg (ver ReleaseFloristeria) y, más adelante, qué features activa
    # por defecto un tenant nuevo. FK a `verticals` en vez de string libre:
    # el registro de verticals soportados vive en una única tabla, no
    # duplicado en un Literal de superadmin.py + un array del frontend.
    vertical_id: Mapped[str] = mapped_column(
        ForeignKey("verticals.id"), default="records", server_default="records", index=True
    )
    vertical: Mapped["Vertical"] = relationship()
    # Eix independent del vertical: quina jurisdicció comptable fa servir
    # aquest tenant (decideix el pla de comptes sembrat i les formes
    # jurídiques vàlides, ver AccountingJurisdiction més avall). Tots els
    # tenants existents són espanyols, d'aquí el default.
    accounting_jurisdiction_id: Mapped[str] = mapped_column(
        ForeignKey("accounting_jurisdictions.id"), default="es", server_default="es", index=True
    )
    accounting_jurisdiction: Mapped["AccountingJurisdiction"] = relationship()
    activo: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Vertical(Base):
    """Catálogo de verticales de negocio soportados por la plataforma (qué
    tipo de tienda es un tenant: discos, floristería...). No hereda de
    TenantScoped: es platform-level, igual que Tenant/PlatformAdmin. Tabla
    real en vez de un string libre: dar de alta un vertical nuevo no debe
    exigir tocar un Literal hardcodeado en el backend y un array duplicado
    en el frontend a la vez (ver antes routers/superadmin.py)."""

    __tablename__ = "verticals"

    id: Mapped[str] = mapped_column(String(30), primary_key=True)  # slug estable: "records", "floristry"...
    name_ca: Mapped[str] = mapped_column(String(100))
    name_es: Mapped[str] = mapped_column(String(100))
    name_en: Mapped[str] = mapped_column(String(100))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # Proveedor de búsqueda de referencias externas en compras (ver
    # docs/ARQUITECTURA_CORE_VERTICAL.md §19.1/§20) — null si esta vertical
    # no tiene ninguno (la mayoría). Validado en el schema de superadmin
    # contra `verticals_registry.CATALOG_PROVIDERS` (qué hay realmente
    # implementado en código), no texto libre.
    catalog_provider: Mapped[str | None] = mapped_column(String(30))
    # Arquetipo de extensión de Product/StockItem (§18) al que pertenece esta
    # vertical. "record"/"floristry" ya tienen tabla de extensión real
    # (RecordProduct/RecordStockDetail, ReleaseFloristeria); el resto de
    # valores son arquetipos planificados sin tabla propia todavía — una
    # vertical con uno de esos asignado vende hoy producto Core puro
    # (nombre/precio/stock), sin campos específicos, hasta que se construya
    # su extensión. Validado contra `verticals_registry.PRODUCT_ARCHETYPES`.
    product_archetype: Mapped[str | None] = mapped_column(String(30))
    # Qué `tenant_features` (ver Fase 7, TenantFeature) se siembran por
    # defecto al dar de alta un tenant de esta vertical — p.ej.
    # {"discogs_sync": true, "subscriptions": true} para records (Spotify no
    # es un tenant_feature: es un kill switch global de Settings, ver §13 y
    # routers/spotify.py). No se aplica todavía en `POST /superadmin/tenants`
    # (fuera de alcance de esta fase, que es solo el registro — ver §20),
    # pero ya se guarda para cuando se aborde.
    default_features: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AccountingJurisdiction(Base):
    """Registro de jurisdicciones comptables suportades — mateix criteri que
    `Vertical`: taula real en comptes d'un string lliure, perquè donar
    d'alta una jurisdicció nova no ha d'exigir tocar un Literal hardcodejat.
    Eix independent del vertical de negoci (una tenda de vins pot ser
    espanyola o francesa igual que una de discos): decideix quin pla de
    comptes es sembra (`AccountingAccount`, ver comptabilitat.py) i quines
    formes jurídiques són vàlides (`ConfiguracioBotiga.legal_form`, validat
    contra `accounting_registry.LEGAL_FORMS_BY_JURISDICTION`).

    Només `es` té proveïdor de pla de comptes real implementat avui
    (`accounting_registry.ACCOUNTING_JURISDICTIONS_IMPLEMENTED`); la resta
    es sembren amb `active=False` per reservar l'id/nom des de superadmin,
    sense oferir-les encara en l'alta de tenant — mateix criteri que les 10
    verticals planificades de la migració 0a8e9cde93d3."""

    __tablename__ = "accounting_jurisdictions"

    id: Mapped[str] = mapped_column(String(2), primary_key=True)  # "es", "fr", "it", "uk", "us"
    name: Mapped[str] = mapped_column(String(100))
    # "eu_vat" | "uk_vat" | "us_sales_tax" — no és només metadada descriptiva:
    # el motor de posting (fase 2) haurà de triar quin `TaxRegimeHandler` fer
    # servir segons aquest valor, perquè l'IVA europeu (recuperable en
    # compres, es liquida trimestralment) i el sales tax americà (no
    # recuperable, es cobra només en la venda final) no comparteixen ni
    # l'estructura de comptes ni la lògica de càlcul.
    tax_model: Mapped[str] = mapped_column(String(30))
    active: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlatformAdminRole(str, enum.Enum):
    """`owner`: control total (crear/editar/suspender tenants, tocar
    features, etc). `support`: solo lectura — puede ver tenants, secretos
    (estado) y el audit log, pero ninguna mutación. Ver
    app/services/superadmin_security.py::require_superadmin_role."""

    owner = "owner"
    support = "support"


class PlatformAdmin(Base):
    """Operador de la plataforma (nosotros), NO un admin de una tienda —
    por eso no hereda de TenantScoped: vive fuera de cualquier tenant, ve y
    gestiona todos. Autenticación completamente separada de `User`/`Identity`
    (ver app/services/superadmin_security.py): secreto de firma JWT propio,
    para que una fuga de la clave de un realm nunca sirva para falsificar
    tokens del otro."""

    __tablename__ = "platform_admins"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    nombre: Mapped[str | None] = mapped_column(String(200))
    # Default owner: no romper a los PlatformAdmin ya existentes (creados
    # antes de que este campo existiera) quitándoles poder de golpe.
    role: Mapped[PlatformAdminRole] = mapped_column(
        Enum(PlatformAdminRole, name="platform_admin_role"),
        default=PlatformAdminRole.owner, server_default=PlatformAdminRole.owner.value,
    )
    activo: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlatformAdminAuditLog(Base):
    """Rastro de acciones mutables hechas desde el panel de superadmin
    (crear/editar/suspender tenant, tocar tenant_features...). No hereda de
    TenantScoped: es platform-level, igual que PlatformAdmin/Tenant — un
    registro puede referenciar un tenant concreto (`target_tenant_id`) sin
    pertenecer a él.

    `action` es un slug libre en código (`"tenant.create"`,
    `"tenant.suspend"`...), no un Enum de BD — mismo criterio que
    `TenantFeature.feature_key`: añadir una acción nueva no debe exigir una
    migración."""

    __tablename__ = "platform_admin_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # SET NULL: borrar un PlatformAdmin no debe borrar su historial de
    # acciones, solo desvincularlo (mismo motivo por el que Order.user_id
    # es nullable con ON DELETE SET NULL, ver CLAUDE.md).
    platform_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("platform_admins.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(50), index=True)
    target_tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    details: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------


class TenantFeature(TenantScoped, Base):
    """Registro genérico de qué features tiene activadas cada tenant —
    sustituye columnas sueltas por feature (como las antiguas
    `ConfiguracioBotiga.discogs_habilitat`/`subscripcions_actives`) para
    que dar de alta un vertical nuevo con su propio interruptor no obligue
    a añadir una columna a `ConfiguracioBotiga` cada vez. Ver
    docs/ARQUITECTURA_CORE_VERTICAL.md §9/§13.

    `feature_key` es un slug libre en código (`"discogs_sync"`,
    `"subscriptions"`...), no un Enum de BD — mismo criterio que
    `Tenant.vertical_id` en su momento: la lista de features válidas vive
    en el código que las consume, no en un constraint de esquema."""

    __tablename__ = "tenant_features"
    __table_args__ = (UniqueConstraint("tenant_id", "feature_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feature_key: Mapped[str] = mapped_column(String(50), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    config: Mapped[dict | None] = mapped_column(JSON)


# ---------------------------------------------------------------------------
# Facturació de plataforma (Revolut Business Subscriptions) — el tenant paga
# A LA PLATAFORMA per fer servir el SaaS. No confondre amb
# `ConfiguracioSubscripcio`/`club de subscripció` (models/subscripcions.py):
# allò és el que un tenant ofereix als SEUS clients, això és el negoci del
# SaaS en si. Muntat sense credencials de Revolut sandbox disponibles
# (decisió explícita de l'usuari, 2026-08-27): els camps `revolut_*` es
# guarden a mà des del superadmin mentre no hi ha integració provada de la
# creació de customer/subscription via API — el webhook (únic camí ja
# testejable sense credencials reals, veure `verify_revolut_signature` a
# services/revolut_billing.py) és qui manté `TenantBilling`/`PlatformInvoice`
# al dia un cop Revolut hi truca de veritat.
# ---------------------------------------------------------------------------


class BillingPeriod(str, enum.Enum):
    monthly = "monthly"
    yearly = "yearly"


class PlatformPlan(Base):
    """Pla de tarifa fixa del catàleg de preus de la plataforma (p. ex.
    "Bàsic"/"Pro"), gestionat des del superadmin. Un tenant es vincula a
    com a molt un pla via `TenantBilling.plan_id`."""

    __tablename__ = "platform_plans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(100))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="EUR", server_default="EUR")
    billing_period: Mapped[BillingPeriod] = mapped_column(
        Enum(BillingPeriod, name="platform_plan_billing_period"),
        default=BillingPeriod.monthly, server_default=BillingPeriod.monthly.value,
    )
    # Id del Plan/Variation equivalent a Revolut — avui creats a mà des del
    # seu dashboard (no des d'aquí, ver comentari de secció) i enganxats
    # aquí perquè `TenantBilling` sàpiga a quina subscripció de Revolut
    # correspon aquest pla quan es creï.
    revolut_plan_id: Mapped[str | None] = mapped_column(String(100))
    revolut_variation_id: Mapped[str | None] = mapped_column(String(100))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TenantBillingStatus(str, enum.Enum):
    sense_pla = "sense_pla"
    pendent_targeta = "pendent_targeta"
    activa = "activa"
    impagada = "impagada"
    cancellada = "cancellada"


class TenantBilling(Base):
    """Estat de facturació SaaS d'UN tenant — 1:1 amb `Tenant`, taula pròpia
    en lloc de columnes soltes a `Tenant` perquè és un domini clarament
    separat (identitat del tenant vs. si paga i com). No hereda de
    TenantScoped: viu fora de qualsevol tenant scope, igual que `Tenant`
    mateix — el superadmin la gestiona sense passar per `scoped_to`, i el
    propi tenant mai hi té accés (no és cosa seva veure com es factura a si
    mateix la plataforma)."""

    __tablename__ = "tenant_billing"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("platform_plans.id", ondelete="SET NULL"))
    revolut_customer_id: Mapped[str | None] = mapped_column(String(100))
    revolut_subscription_id: Mapped[str | None] = mapped_column(String(100), index=True)
    status: Mapped[TenantBillingStatus] = mapped_column(
        Enum(TenantBillingStatus, name="tenant_billing_status"),
        default=TenantBillingStatus.sense_pla, server_default=TenantBillingStatus.sense_pla.value,
    )
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )


class PlatformInvoiceStatus(str, enum.Enum):
    pagada = "pagada"
    fallida = "fallida"
    pendent = "pendent"


class PlatformInvoice(Base):
    """Rèplica local de cada cobrament (fet o fallit) d'un tenant per la
    seva facturació SaaS — poblada pel webhook de Revolut, no per l'usuari.
    `revolut_event_id` únic fa idempotent el processament del webhook
    (entregues "at-least-once": un mateix event puntualment repetit no ha de
    duplicar la factura)."""

    __tablename__ = "platform_invoices"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    revolut_event_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="EUR", server_default="EUR")
    status: Mapped[PlatformInvoiceStatus] = mapped_column(Enum(PlatformInvoiceStatus, name="platform_invoice_status"))
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_event: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
