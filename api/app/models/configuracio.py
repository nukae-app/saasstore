from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.orm import Mapped, mapped_column, object_session

from ..database import Base
from ._base import TenantScoped
from .platform import TenantFeature


class MargeConfig(TenantScoped, Base):
    """Marges configurables per suggerir el preu de venda a la recepció de
    stock (compra_adquisicion -> preu). `default_new`/`default_used`
    marquen quin marge es fa servir automàticament segons la condició triada
    (només un actiu de cada a la vegada, validat a l'endpoint, mateix patró
    que TipusIva). El càlcul és sempre un suggeriment: el preu final es pot
    editar sempre a mà a la recepció."""

    __tablename__ = "marges_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Fase 4 Etapa B: atributo Python en inglés, ya alineado con el nombre
    # de columna que fijó la Etapa A.
    name: Mapped[str] = mapped_column(String(200))
    percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    default_new: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    default_used: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TramEnviament(TenantScoped, Base):
    """Trams de pes per país per calcular el cost d'enviament al checkout
    (veure services/enviament.py): cada línia és (país, pes màxim, preu). Un
    país només és venedor si té almenys un tram actiu — no hi ha cap llista
    de països hardcodejada, afegir-ne un de nou és només crear un tram des
    de l'admin, sense tocar codi. No hi ha cap API de tarifes de missatgeria
    en temps real: aquesta taula és la nostra pròpia tarifa, editable des de
    l'admin sense redesplegar, mateix patró que `MargeConfig`/`TipusIva`."""

    __tablename__ = "trams_enviament"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Fase 4 Etapa B: atributo Python en inglés, ya alineado con el nombre
    # de columna que fijó la Etapa A.
    country: Mapped[str] = mapped_column(String(2), index=True)  # ISO 3166-1 alpha-2, p. ex. "ES", "FR"
    max_weight_g: Mapped[int] = mapped_column(Integer)  # tram vàlid fins aquest pes (inclusiu)
    price: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PesFormat(TenantScoped, Base):
    """Pes per defecte (grams) segons `Release.formato`, per no haver
    d'omplir `Release.weight_g` disc a disc. Resolució a services/enviament.py:
    pes propi de la còpia > pes per defecte del seu format > DEFAULT_PES_G
    global. Editable des de l'admin, mateix patró que `TramEnviament`."""

    __tablename__ = "pes_format"
    __table_args__ = (UniqueConstraint("tenant_id", "formato"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    formato: Mapped[str] = mapped_column(String(120))
    pes_g: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConfiguracioBotiga(TenantScoped, Base):
    """Configuració general de la botiga: una fila per tenant (abans era
    una fila singleton fixa `id=1` — ara `tenant_id` és la clau natural,
    ver `__table_args__`).

    Dades fiscals (capçalera del PDF de comandes), contacte/xarxes (footer
    públic) i paràmetres operatius (minuts de reserva de stock). Abans
    vivien a `Settings`/`.env`; aquí són editables des de l'admin sense
    redesplegar."""

    __tablename__ = "configuracio_botiga"
    __table_args__ = (UniqueConstraint("tenant_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fiscal_name: Mapped[str] = mapped_column(String(200))
    nif: Mapped[str | None] = mapped_column(String(20))
    address: Mapped[str] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(30))
    contact_email: Mapped[str | None] = mapped_column(String(200))
    # Remitente ("From") de los emails transaccionales de este tenant — no es
    # secreto, es texto de cara al cliente (ver services/emailer.py). Antes
    # vivía en Settings.email_from, global para todos los tenants.
    email_from: Mapped[str | None] = mapped_column(String(300))
    instagram_url: Mapped[str | None] = mapped_column(String(300))
    hours: Mapped[str | None] = mapped_column(Text)
    reservation_minutes: Mapped[int] = mapped_column(Integer, default=20)
    # Mode manteniment: bloqueja /checkout/start i /checkout/confirm per a
    # qualsevol usuari que no sigui admin (veure routers/checkout.py) i el
    # front mostra un banner "en construcció" (veure useManteniment.js).
    # L'admin sempre pot provar el flux de compra sencer amb aquest actiu.
    maintenance_active: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Passthrough (lectura y escritura) a `TenantFeature`: antes eran
    # columnas propias de esta tabla, ahora viven en el registro genérico
    # de features por tenant (ver TenantFeature más arriba). Se mantienen
    # como propiedades con el mismo nombre para que todo el código
    # existente (schemas con from_attributes=True, `setattr` genérico del
    # PATCH de configuracio.py) siga funcionando sin cambios — mismo
    # patrón que Release.artista/etc. en la extracción de RecordProduct.
    # Requieren que el objeto ya esté adjunto a una sesión (`db.add(...)`
    # + flush/commit antes de leer o escribir, no como kwarg del
    # constructor) — ver routers/superadmin.py::create_tenant.
    def _feature(self, key: str) -> "TenantFeature | None":
        session = object_session(self)
        if session is None or self.tenant_id is None:
            return None
        return session.scalar(
            select(TenantFeature).where(TenantFeature.tenant_id == self.tenant_id, TenantFeature.feature_key == key)
        )

    def _set_feature(self, key: str, enabled: bool) -> None:
        session = object_session(self)
        if session is None or self.tenant_id is None:
            raise RuntimeError(
                f"ConfiguracioBotiga.{key} no se puede fijar antes de que el objeto esté en sesión "
                "(añade con db.add()/flush() primero)"
            )
        feature = self._feature(key)
        if feature is None:
            session.add(TenantFeature(tenant_id=self.tenant_id, feature_key=key, enabled=enabled))
        else:
            feature.enabled = enabled

    @property
    def subscripcions_actives(self) -> bool:
        """Interruptor general del club de subscripció: si és False, l'API
        pública de plans no retorna res i el front no mostra l'opció (veure
        routers/subscripcions_public.py)."""
        feature = self._feature("subscriptions")
        return bool(feature and feature.enabled)

    @subscripcions_actives.setter
    def subscripcions_actives(self, value: bool) -> None:
        self._set_feature("subscriptions", value)

    @property
    def discogs_habilitat(self) -> bool:
        """Interruptor per tenant del mòdul Discogs (cercar/sincronitzar
        listings — veure require_discogs_enabled a routers/admin.py): sense
        això, un tenant que no ven discos veuria igualment les rutes de
        Discogs. A diferència de `spotify_enabled` (Settings, interruptor
        global de plataforma), aquest és per tenant perquè Discogs només té
        sentit per al vertical records, no és una decisió de plataforma
        sencera."""
        feature = self._feature("discogs_sync")
        return bool(feature and feature.enabled)

    @discogs_habilitat.setter
    def discogs_habilitat(self, value: bool) -> None:
        self._set_feature("discogs_sync", value)
