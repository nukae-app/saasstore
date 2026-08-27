import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
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


class Translation(TenantScoped, Base):
    """Traducciones de la UI. key = 'nav.purchases', lang = 'ca'|'es'|'en'."""

    __tablename__ = "translations"
    __table_args__ = (UniqueConstraint("tenant_id", "key", "lang"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    key: Mapped[str] = mapped_column(String(200), index=True)
    lang: Mapped[str] = mapped_column(String(5), index=True)
    value: Mapped[str] = mapped_column(Text)


class Pagina(TenantScoped, Base):
    """Secció/pàgina del lloc: apareix al nav i té la seva pròpia ruta (/blog, /podcast, ...)."""

    __tablename__ = "pagines"
    __table_args__ = (UniqueConstraint("tenant_id", "slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(100), index=True)
    # Fase 4 Etapa B: atributo Python en inglés, ya alineado con el nombre
    # de columna que fijó la Etapa A.
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(40), default="llista-posts")
    # 'llista-posts' → mostra posts assignats, amb sidebar d'arxiu
    # 'estatica'     → mostra `content` (HTML lliure)
    # 'agenda'       → mostra events
    position: Mapped[int] = mapped_column(Integer, default=0)
    menu_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    content: Mapped[str | None] = mapped_column(Text)  # per a pàgines estàtiques
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    posts: Mapped[list["Post"]] = relationship(
        secondary="posts_pagines", back_populates="pagines"
    )


class Post(TenantScoped, Base):
    __tablename__ = "posts"
    __table_args__ = (UniqueConstraint("tenant_id", "slug"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(300), index=True)
    # Fase 4 Etapa B: atributo Python en inglés, ya alineado con el nombre
    # de columna que fijó la Etapa A.
    title: Mapped[str] = mapped_column(String(400))
    content: Mapped[str] = mapped_column(Text)  # HTML (los posts de Blogger vienen en HTML)
    language: Mapped[str] = mapped_column(String(5), default="ca")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    legacy_blogger_url: Mapped[str | None] = mapped_column(String(800))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    pagines: Mapped[list["Pagina"]] = relationship(
        secondary="posts_pagines", back_populates="posts"
    )


class PostPagina(TenantScoped, Base):
    """M2M: un post pot aparèixer a múltiples pàgines."""

    __tablename__ = "posts_pagines"

    post_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True
    )
    pagina_id: Mapped[int] = mapped_column(
        ForeignKey("pagines.id", ondelete="CASCADE"), primary_key=True
    )


class Event(TenantScoped, Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    # Fase 4 Etapa B: atributo Python en inglés, ya alineado con el nombre
    # de columna que fijó la Etapa A.
    title: Mapped[str] = mapped_column(String(400))
    description: Mapped[str | None] = mapped_column(Text)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    location: Mapped[str] = mapped_column(String(300), default="")
    link: Mapped[str | None] = mapped_column(String(800))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
