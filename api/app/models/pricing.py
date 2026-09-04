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
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from ._base import TenantScoped, _uuid


class DiscountType(str, enum.Enum):
    percentage = "percentage"
    fixed_amount = "fixed_amount"
    fixed_price = "fixed_price"


class Offer(TenantScoped, Base):
    """Campanya d'oferta: aplica un descompte a un conjunt d'`Item` mentre
    està activa. La selecció d'items combina dos mecanismes (com les "smart
    collections" de Shopify):

    - Dinàmica: `criteria` (JSON) es re-avalua periòdicament (veure
      `tasks/pricing.py`) perquè camps com "antiguitat en catàleg" o
      "rotació" canvien sols cada dia sense que l'admin toqui res.
    - Manual: `OfferItem` afegeix/exclou items concrets per afinar el que
      els criteris no capten bé.

    `criteria` només porta claus core sempre disponibles (secció, etiqueta,
    condició, preu, antiguitat, rotació); claus pròpies d'un vertical (p.ex.
    genere/artista/segell per a discos) hi poden aparèixer però només les
    interpreta el resolver del vertical corresponent — igual que
    `RecordProduct`/`ReleaseFloristeria` estenen `Release` sense que el core
    en sàpiga el contingut.

    Quan una oferta s'activa/desactiva, el resolver escriu `Item.price` a
    partir de `Item.list_price` (veure stock.py): és la primera peça del
    sistema que escriu `price` de forma automàtica, no només l'admin a mà.
    """

    __tablename__ = "offers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    discount_type: Mapped[DiscountType] = mapped_column(Enum(DiscountType, name="discount_type"))
    discount_value: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    # Quan dos ofertes actives matchegen el mateix item, guanya la de
    # `priority` més alta. No es resol sol: el panell avisa del solapament i
    # l'admin decideix (ajustant priority, criteris, o excloent l'item a mà
    # d'una de les dues via OfferItem) — veure conversa de disseny.
    priority: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    criteria: Mapped[dict | None] = mapped_column(JSON)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list["OfferItem"]] = relationship(back_populates="offer", cascade="all, delete-orphan")


class OfferItemMode(str, enum.Enum):
    include = "include"
    exclude = "exclude"


class OfferItem(TenantScoped, Base):
    """Ajust manual sobre el resultat dinàmic d'una `Offer`: afegeix
    (`include`) o treu (`exclude`) un item concret sense tocar `criteria`.
    Un item afegit "include" que ja matchejava per criteris és un no-op
    idempotent; "exclude" sempre guanya sobre el match dinàmic."""

    __tablename__ = "offer_items"
    __table_args__ = (UniqueConstraint("offer_id", "item_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    offer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), index=True)
    mode: Mapped[OfferItemMode] = mapped_column(Enum(OfferItemMode, name="offer_item_mode"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    offer: Mapped["Offer"] = relationship(back_populates="items")
    item: Mapped["Item"] = relationship()

    # Passthrough de solo lectura para que el panel admin pueda mostrar qué
    # disco es cada ajuste manual sin un endpoint aparte — igual patrón que
    # los passthrough de Release/Item en catalog.py/stock.py.
    @property
    def item_title(self) -> str | None:
        return self.item.release.title if self.item else None

    @property
    def item_artista(self) -> str | None:
        return self.item.release.artista if self.item else None

    @property
    def item_price(self) -> Decimal | None:
        return self.item.price if self.item else None


class Coupon(TenantScoped, Base):
    """Codi de descompte aplicat pel client al checkout (a diferència
    d'`Offer`, que rebaixa el preu de catàleg per a tothom). `combinable_with_offers`
    decideix si es pot acumular sobre un item que ja porta descompte
    d'`Offer` — configurable per cupó, no una regla global (veure disseny)."""

    __tablename__ = "coupons"
    __table_args__ = (UniqueConstraint("tenant_id", "code"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(40), index=True)
    discount_type: Mapped[DiscountType] = mapped_column(Enum(DiscountType, name="discount_type"))
    discount_value: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    max_uses: Mapped[int | None] = mapped_column(Integer)
    max_uses_per_user: Mapped[int | None] = mapped_column(Integer)
    min_order_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    combinable_with_offers: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Si s'omple, el cupó només és vàlid quan la comanda inclou algun item
    # cobert per aquesta Offer (p.ex. un cupó exclusiu d'una col·lecció).
    restrict_to_offer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("offers.id", ondelete="SET NULL")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    restrict_to_offer: Mapped["Offer | None"] = relationship()
    redemptions: Mapped[list["CouponRedemption"]] = relationship(back_populates="coupon")


class CouponRedemption(TenantScoped, Base):
    """Ús d'un cupó en una comanda concreta: fa falta una taula (no només
    comptar `orders.coupon_code`) per fer complir `max_uses_per_user` i per
    guardar `discount_amount` com a snapshot — igual criteri que
    `order_items.price` (decisió #3 del projecte): l'import descomptat mai
    es recalcula encara que el cupó canviï o s'esborri després."""

    __tablename__ = "coupon_redemptions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    coupon_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("coupons.id", ondelete="CASCADE"), index=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True, unique=True)
    # Nullable: guest checkout (veure decisió #5 del projecte) també pot fer
    # servir cupons; en aquest cas només queda l'email de la comanda.
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    coupon: Mapped["Coupon"] = relationship(back_populates="redemptions")
