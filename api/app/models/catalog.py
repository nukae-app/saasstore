import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from ._base import TenantScoped, _uuid


class Etiqueta(TenantScoped, Base):
    """Etiqueta configurable per destacar releases al catàleg (Novetat, Recomanat, etc.)."""

    __tablename__ = "etiquetes"
    __table_args__ = (UniqueConstraint("tenant_id", "slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(60), index=True)
    name_ca: Mapped[str] = mapped_column(String(100))
    name_es: Mapped[str | None] = mapped_column(String(100))
    color: Mapped[str | None] = mapped_column(String(20))  # hex o classe Tailwind
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    releases: Mapped[list["Release"]] = relationship(
        secondary="release_etiquetes", back_populates="etiquetes"
    )


class Seccio(TenantScoped, Base):
    """Cubeta física de la botiga (Nacional, Internacional, Alternatiu...).

    A diferència d'Etiqueta (M2M, distintius promocionals), un release viu
    en una sola cubeta: relació 1-a-molts.
    """

    __tablename__ = "seccions"
    __table_args__ = (UniqueConstraint("tenant_id", "slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(60), index=True)
    name_ca: Mapped[str] = mapped_column(String(100))
    name_es: Mapped[str | None] = mapped_column(String(100))
    color: Mapped[str | None] = mapped_column(String(20))  # hex o classe Tailwind
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    releases: Mapped[list["Release"]] = relationship(back_populates="seccio")


class ReleaseEtiqueta(TenantScoped, Base):
    """M2M: un release pot tenir múltiples etiquetes."""

    __tablename__ = "release_etiquetes"

    release_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("releases.id", ondelete="CASCADE"), primary_key=True
    )
    etiqueta_id: Mapped[int] = mapped_column(
        ForeignKey("etiquetes.id", ondelete="CASCADE"), primary_key=True
    )


class Release(TenantScoped, Base):
    """Un producto/edición: los metadatos core compartidos por todas sus
    copias, sea cual sea el vertical del tenant. Los campos propios de
    "discos" viven en la extensión `RecordProduct` (ver más abajo), no
    aquí — mismo patrón que `ReleaseFloristeria` para floristeria, ahora
    aplicado también al vertical por defecto en vez de solo al añadido
    (ver docs/ARQUITECTURA_CORE_VERTICAL.md, Fase 2)."""

    __tablename__ = "releases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(300), index=True)
    ean: Mapped[str | None] = mapped_column(String(20), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(800))
    # Pes en grams: s'usa per calcular el cost d'enviament (veure
    # services/enviament.py) — genèric a qualsevol producte físic, encara
    # que avui només es calcula automàticament per al vertical discos
    # (veure RecordWeightByFormat/PesFormat).
    weight_g: Mapped[int | None] = mapped_column(Integer)
    coming_soon: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    available_at: Mapped[date | None] = mapped_column(Date)
    section_id: Mapped[int | None] = mapped_column(
        ForeignKey("seccions.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list["Item"]] = relationship(back_populates="release")
    etiquetes: Mapped[list["Etiqueta"]] = relationship(
        secondary="release_etiquetes", back_populates="releases"
    )
    seccio: Mapped["Seccio | None"] = relationship(back_populates="releases")
    images: Mapped[list["ReleaseImage"]] = relationship(
        back_populates="release", order_by="ReleaseImage.position", cascade="all, delete-orphan"
    )
    floristeria: Mapped["ReleaseFloristeria | None"] = relationship(
        back_populates="release", uselist=False, cascade="all, delete-orphan"
    )
    record: Mapped["RecordProduct | None"] = relationship(
        back_populates="release", uselist=False, cascade="all, delete-orphan"
    )

    # Passthrough a la extensió de floristeria (Fase 7): calen com a
    # propietats, no com a columnes, perquè ReleaseOut es serialitza amb
    # from_attributes=True directe sobre aquest objecte ORM — sense això,
    # Pydantic no trobaria cap atribut "color"/"tipus_flor"/"durabilitat_dies"
    # a Release (viuen a la taula filla). Sempre None per a un tenant que no
    # sigui floristry.
    @property
    def color(self) -> str | None:
        return self.floristeria.color if self.floristeria else None

    @property
    def tipus_flor(self) -> str | None:
        return self.floristeria.tipus_flor if self.floristeria else None

    @property
    def durabilitat_dies(self) -> int | None:
        return self.floristeria.durabilitat_dies if self.floristeria else None

    # Passthrough (lectura Y escritura, a diferencia de floristeria arriba)
    # a la extensión `RecordProduct`: además de servir ReleaseOut igual que
    # antes, permite que TODO el código existente que hacía
    # `Release(artista=..., sello=..., ...)` o `release.artista = ...` siga
    # funcionando sin tocar cada punto de escritura uno a uno — el setter
    # crea la fila hija de forma perezosa la primera vez que se asigna
    # cualquier campo. Lo que SÍ hay que revisar aparte son los usos a nivel
    # de clase en queries (`Release.artista.ilike(...)`), que ya no
    # funcionan como columna — ver RecordProduct y los joins añadidos en
    # catalog.py/admin.py/erp.py/etc.
    def _ensure_record(self) -> "RecordProduct":
        if self.record is None:
            self.record = RecordProduct()
        return self.record

    @property
    def artista(self) -> str | None:
        return self.record.artista if self.record else None

    @artista.setter
    def artista(self, value: str | None) -> None:
        self._ensure_record().artista = value

    @property
    def sello(self) -> str | None:
        return self.record.sello if self.record else None

    @sello.setter
    def sello(self, value: str | None) -> None:
        self._ensure_record().sello = value

    @property
    def referencia(self) -> str | None:
        return self.record.referencia if self.record else None

    @referencia.setter
    def referencia(self, value: str | None) -> None:
        self._ensure_record().referencia = value

    @property
    def formato(self) -> str | None:
        return self.record.formato if self.record else None

    @formato.setter
    def formato(self, value: str | None) -> None:
        self._ensure_record().formato = value

    @property
    def anio(self) -> int | None:
        return self.record.anio if self.record else None

    @anio.setter
    def anio(self, value: int | None) -> None:
        self._ensure_record().anio = value

    @property
    def genero(self) -> str | None:
        return self.record.genero if self.record else None

    @genero.setter
    def genero(self, value: str | None) -> None:
        self._ensure_record().genero = value

    @property
    def pais(self) -> str | None:
        return self.record.pais if self.record else None

    @pais.setter
    def pais(self, value: str | None) -> None:
        self._ensure_record().pais = value

    @property
    def estilos(self) -> str | None:
        return self.record.estilos if self.record else None

    @estilos.setter
    def estilos(self, value: str | None) -> None:
        self._ensure_record().estilos = value

    @property
    def tracklist(self) -> list | None:
        return self.record.tracklist if self.record else None

    @tracklist.setter
    def tracklist(self, value: list | None) -> None:
        self._ensure_record().tracklist = value

    @property
    def credits(self) -> list | None:
        return self.record.credits if self.record else None

    @credits.setter
    def credits(self, value: list | None) -> None:
        self._ensure_record().credits = value

    @property
    def discogs_release_id(self) -> int | None:
        return self.record.discogs_release_id if self.record else None

    @discogs_release_id.setter
    def discogs_release_id(self, value: int | None) -> None:
        self._ensure_record().discogs_release_id = value

    @property
    def spotify_album_id(self) -> str | None:
        return self.record.spotify_album_id if self.record else None

    @spotify_album_id.setter
    def spotify_album_id(self, value: str | None) -> None:
        self._ensure_record().spotify_album_id = value

    @property
    def esta_sonant(self) -> bool:
        return bool(self.record.esta_sonant) if self.record else False

    @esta_sonant.setter
    def esta_sonant(self, value: bool) -> None:
        self._ensure_record().esta_sonant = value


class ReleaseFloristeria(TenantScoped, Base):
    """Extensió 1:1 de Release amb els camps propis del vertical
    floristeria (Fase 4, prova de concepte) — mai s'ompla per a un tenant
    del vertical records. `tenant_id` propi, no només heretat via
    `release_id`: mateix criteri que `ReleaseEtiqueta`/`ReleaseImage`,
    filles d'un Release ja escopat que igualment porten el seu propi
    tenant_id+RLS."""

    __tablename__ = "release_floristeria"

    release_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("releases.id", ondelete="CASCADE"), primary_key=True
    )
    color: Mapped[str | None] = mapped_column(String(100))
    tipus_flor: Mapped[str | None] = mapped_column(String(100))
    durabilitat_dies: Mapped[int | None] = mapped_column(Integer)

    release: Mapped["Release"] = relationship(back_populates="floristeria")


class RecordProduct(TenantScoped, Base):
    """Extensión 1:1 de Release con los campos propios del vertical
    "records" (discos) — pareja simétrica de `ReleaseFloristeria`, ver
    docs/ARQUITECTURA_CORE_VERTICAL.md §4.2. Antes vivían directamente en
    `Release`, lo que hacía que "core" fuera en realidad "discos por
    defecto". `tenant_id` propio, mismo criterio que `ReleaseFloristeria`."""

    __tablename__ = "release_records"

    release_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("releases.id", ondelete="CASCADE"), primary_key=True
    )
    artista: Mapped[str | None] = mapped_column(String(300), index=True)
    sello: Mapped[str | None] = mapped_column(String(500))
    referencia: Mapped[str | None] = mapped_column(String(200))
    formato: Mapped[str | None] = mapped_column(String(120), index=True)
    anio: Mapped[int | None] = mapped_column(Integer)
    genero: Mapped[str | None] = mapped_column(String(200), index=True)
    pais: Mapped[str | None] = mapped_column(String(100))
    estilos: Mapped[str | None] = mapped_column(String(300))
    tracklist: Mapped[list | None] = mapped_column(JSON)
    credits: Mapped[list | None] = mapped_column(JSON)
    discogs_release_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    spotify_album_id: Mapped[str | None] = mapped_column(String(50))
    esta_sonant: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", index=True)

    release: Mapped["Release"] = relationship(back_populates="record")


class ReleaseImage(TenantScoped, Base):
    """Imatge de la galeria d'un release (portada, posterior, etiqueta, vinil...)."""

    __tablename__ = "release_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    release_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("releases.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(String(800))
    position: Mapped[int] = mapped_column(Integer, default=0)
    # portada | posterior | etiqueta | vinil | altre
    type: Mapped[str | None] = mapped_column(String(40))
    # discogs | upload
    source: Mapped[str] = mapped_column(String(20), default="upload")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    release: Mapped["Release"] = relationship(back_populates="images")
