from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
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
    # Favicon propio del tenant (/uploads/{uuid}.ext, mismo mecanismo que
    # ReleaseImage — ver routers/configuracio.py). Sin valor: la app no
    # manda ningún <link rel="icon"> propio y el navegador usa su default,
    # en vez de heredar el favicon de otro tenant (ver web/app/layout.jsx).
    favicon_url: Mapped[str | None] = mapped_column(String(300))
    # Logo del nav/footer públic (mateix mecanisme que favicon_url) — el del
    # tiquet imprès del TPV és un asset a part (aspect ratio diferent, per
    # impressora tèrmica), no es toca aquí.
    logo_url: Mapped[str | None] = mapped_column(String(300))
    # Tokens de tema (colors hex + tipografies) que sobreescriuen les
    # variables CSS de web/app/globals.css per aquest tenant — injectats a
    # web/app/layout.jsx. `JSON`, no `JSONB`: és l'únic tipus JSON que fa
    # servir tot aquest codebase (Release.tracklist, Order.shipping_address...)
    # i aquí mai cal filtrar/indexar pel contingut, només carregar el blob
    # sencer per tenant_id. Validat amb un schema fix (ThemeTokens) al
    # router — mai un dict obert de noms de variable arbitraris.
    theme: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    # CSS lliure del tenant, sanejat a l'escriure (ver
    # services/sanitize.py::sanitize_custom_css) i injectat tal qual en un
    # <style> després dels tokens de dalt, així pot sobreescriure'ls.
    custom_css: Mapped[str | None] = mapped_column(Text)
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

    # Tres interruptors nous: fins ara `isVinils` (derivat de Tenant.vertical_id,
    # no configurable) era l'únic que decidia si un tenant veia el mode
    # "Remena" i els filtres de format/gènere a /cataleg (ver
    # web/app/[locale]/cataleg/page.jsx i CatalogFilters.jsx). El vertical
    # segueix sent el sostre (una floristeria mai els veu), però dins de
    # "records" cada tenant ara pot apagar-los individualment.
    @property
    def catalog_browse_mode(self) -> bool:
        feature = self._feature("catalog_browse_mode")
        return bool(feature and feature.enabled)

    @catalog_browse_mode.setter
    def catalog_browse_mode(self, value: bool) -> None:
        self._set_feature("catalog_browse_mode", value)

    @property
    def catalog_format_filter(self) -> bool:
        feature = self._feature("catalog_format_filter")
        return bool(feature and feature.enabled)

    @catalog_format_filter.setter
    def catalog_format_filter(self, value: bool) -> None:
        self._set_feature("catalog_format_filter", value)

    @property
    def catalog_genre_filter(self) -> bool:
        feature = self._feature("catalog_genre_filter")
        return bool(feature and feature.enabled)

    @catalog_genre_filter.setter
    def catalog_genre_filter(self, value: bool) -> None:
        self._set_feature("catalog_genre_filter", value)
