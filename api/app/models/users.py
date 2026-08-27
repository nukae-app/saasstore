import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from ._base import TenantScoped, _uuid


class User(TenantScoped, Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "email"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(30))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="cliente")  # cliente | admin
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    # Provada per magic link/Google en el moment del login; l'alta amb contrasenya
    # comença en False i cal confirmar-la clicant l'enllaç del mail (ver auth.py).
    email_verified: Mapped[bool] = mapped_column(Boolean, default=True)
    consent_newsletter: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[str] = mapped_column(String(5), default="ca")  # ca | es | en
    internal_notes: Mapped[str | None] = mapped_column(Text)  # notes visibles solo per admin
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    identities: Mapped[list["Identity"]] = relationship(back_populates="user")
    addresses: Mapped[list["Address"]] = relationship(back_populates="user")
    vendes: Mapped[list["VentaExterna"]] = relationship(back_populates="client", foreign_keys="VentaExterna.user_id")
    compres_client: Mapped[list["Compra"]] = relationship(back_populates="client", foreign_keys="Compra.user_id")
    peticiones: Mapped[list["PeticionCliente"]] = relationship(back_populates="user")


class Identity(TenantScoped, Base):
    """Vínculo con un proveedor externo de identidad (Google hoy; otros mañana)."""

    __tablename__ = "identities"
    __table_args__ = (UniqueConstraint("tenant_id", "provider", "provider_user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(40))         # "google"
    provider_user_id: Mapped[str] = mapped_column(String(255))  # el `sub` del id_token
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="identities")


class RefreshToken(TenantScoped, Base):
    """Sesiones propias. Guardamos solo el hash del token, nunca el token."""

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuthToken(TenantScoped, Base):
    """Tokens de un solo uso para magic links y verificación de email tras el registro.

    Lleva `email` (no user_id) porque para el magic link el usuario puede no
    existir aún: se crea/recupera al canjear el enlace. `purpose` distingue
    ambos usos para que un token de un flujo no sirva para canjear el otro.
    """

    __tablename__ = "auth_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    purpose: Mapped[str] = mapped_column(String(20), default="magic_link")  # magic_link | verify_email
    # Idioma del visitante en el momento de PEDIR el enlace (no al canjearlo: el
    # magic link se abre a menudo desde el correu, en un altre dispositiu/navegador).
    idioma: Mapped[str | None] = mapped_column(String(5))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Address(TenantScoped, Base):
    """Libreta de direcciones (para autorellenar). El pedido guarda su propia copia."""

    __tablename__ = "addresses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    recipient_name: Mapped[str] = mapped_column(String(200))
    address_line1: Mapped[str] = mapped_column(String(300))
    address_line2: Mapped[str | None] = mapped_column(String(300))
    city: Mapped[str] = mapped_column(String(120))
    postal_code: Mapped[str] = mapped_column(String(20))
    province: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str] = mapped_column(String(2), default="ES")
    phone: Mapped[str | None] = mapped_column(String(40))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="addresses")


# ---------------------------------------------------------------------------
# Carrito y pedidos
# ---------------------------------------------------------------------------
