import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

DiscountTypeLiteral = Literal["percentage", "fixed_amount", "fixed_price"]
OfferItemModeLiteral = Literal["include", "exclude"]


class OfferCriteria(BaseModel):
    """Criteris dinàmics d'una Offer (es desen a `Offer.criteria`, JSON).
    Camps core disponibles per a qualsevol vertical; `genero`/`artista`/
    `sello`/`formato` només tenen efecte per al vertical "records" (viuen a
    `RecordProduct`) — per a un altre vertical (p.ex. floristeria) simplement
    no matchegen mai, no calen registrar-se a part. Si en el futur cal un
    criteri propi d'un altre vertical, s'afegeix aquí i al resolver
    (`services/pricing.py::match_items_by_criteria`): no hi ha un registre
    plugable per vertical, seria sobre-enginyeria amb només dos verticals
    actius (veure CLAUDE.md, "no hace falta sobre-ingeniería")."""

    seccio_id: int | None = None
    etiqueta_id: int | None = None
    condicion: Literal["nou", "segona_ma"] | None = None
    precio_min: Decimal | None = Field(default=None, ge=0)
    precio_max: Decimal | None = Field(default=None, ge=0)
    # Antiguitat mínima a catàleg (dies des de `entry_date`/`created_at`).
    antiguedad_dias_min: int | None = Field(default=None, ge=0)
    # Rotació: no s'ha venut (web ni externa) en aquests dies. No distingeix
    # si l'item és prou "vell" per haver tingut l'oportunitat de vendre's en
    # aquest període — combina amb `antiguedad_dias_min` (tots dos apliquen
    # en AND) si cal excloure alta recent.
    sin_venta_dias_min: int | None = Field(default=None, ge=0)
    genero: str | None = None
    artista: str | None = None
    sello: str | None = None
    formato: str | None = None

    model_config = {"extra": "forbid"}


class OfferItemIn(BaseModel):
    item_id: uuid.UUID
    mode: OfferItemModeLiteral


class OfferItemOut(BaseModel):
    id: uuid.UUID
    item_id: uuid.UUID
    mode: OfferItemModeLiteral
    created_at: datetime
    item_title: str | None = None
    item_artista: str | None = None
    item_price: Decimal | None = None

    model_config = {"from_attributes": True}


class OfferIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    discount_type: DiscountTypeLiteral
    discount_value: Decimal = Field(gt=0)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    active: bool = True
    # Quan dues ofertes actives matchegen el mateix item, guanya la de
    # priority més alta (desempat: la creada més recentment). El panell no
    # ho resol sol — avisa del solapament (veure `detect_overlaps`) i
    # l'admin ajusta priority/criteris/exclusions a mà.
    priority: int = 0
    criteria: OfferCriteria | None = None

    @model_validator(mode="after")
    def _validar_percentage(self) -> "OfferIn":
        if self.discount_type == "percentage" and self.discount_value > 100:
            raise ValueError("Un descuento porcentual no puede superar el 100%")
        return self


class OfferOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    discount_type: DiscountTypeLiteral
    discount_value: Decimal
    starts_at: datetime | None
    ends_at: datetime | None
    active: bool
    priority: int
    criteria: OfferCriteria | None
    created_by: uuid.UUID | None
    created_at: datetime
    items: list[OfferItemOut] = []

    model_config = {"from_attributes": True}


class OfferPreviewItem(BaseModel):
    item_id: uuid.UUID
    release_id: uuid.UUID
    title: str
    artista: str | None = None
    price: Decimal
    condition: str


class OfferPreviewOut(BaseModel):
    """Respuesta al previsualizar unos criterios antes de guardar la oferta:
    cuántos items matchean en total y una muestra para enseñar en el panel."""
    total_items: int
    sample: list[OfferPreviewItem]


class OfferOverlapOut(BaseModel):
    offer_id: uuid.UUID
    offer_name: str
    priority: int
    overlapping_items: int


class OfferApplyResultOut(BaseModel):
    applied: int
    reverted: int


class CouponIn(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    # fixed_price no té sentit a nivell de comanda (és "el preu final d'un
    # item concret", no d'un total heterogeni) — només vàlid per a Offer.
    discount_type: Literal["percentage", "fixed_amount"]
    discount_value: Decimal = Field(gt=0)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    active: bool = True
    max_uses: int | None = Field(default=None, gt=0)
    max_uses_per_user: int | None = Field(default=None, gt=0)
    min_order_amount: Decimal | None = Field(default=None, ge=0)
    combinable_with_offers: bool = False
    restrict_to_offer_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _validar_percentage(self) -> "CouponIn":
        if self.discount_type == "percentage" and self.discount_value > 100:
            raise ValueError("Un descuento porcentual no puede superar el 100%")
        return self


class CouponOut(BaseModel):
    id: uuid.UUID
    code: str
    discount_type: DiscountTypeLiteral
    discount_value: Decimal
    starts_at: datetime | None
    ends_at: datetime | None
    active: bool
    max_uses: int | None
    max_uses_per_user: int | None
    min_order_amount: Decimal | None
    combinable_with_offers: bool
    restrict_to_offer_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CouponRedemptionOut(BaseModel):
    id: uuid.UUID
    coupon_id: uuid.UUID
    order_id: uuid.UUID
    user_id: uuid.UUID | None
    discount_amount: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}


class CouponApplyResultOut(BaseModel):
    """Import a descomptar ja calculado y redondeado, listo para restar del
    subtotal — se congela en `orders.coupon_discount` al confirmar (mismo
    criterio que `order_items.price`), nunca se recalcula después."""
    coupon_code: str
    discount_amount: Decimal
