import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class VentaExternaIn(BaseModel):
    # Venda de catàleg: item_id (còpia física reservada i venuda). Venda
    # d'article manual (llibre, samarreta...): item_id buit, descripcion +
    # tipus_iva_id obligatoris perquè no hi ha `Item` del qual deduir-los.
    item_id: uuid.UUID | None = None
    description: str | None = None
    tipus_iva_id: int | None = None
    channel: Literal["mostrador", "discogs", "otro"]
    payment_method: Literal["efectivo", "tarjeta", "bizum", "bono_cultural"] = "efectivo"
    sale_price: Decimal
    # Solo relevante para condicion='nou': unidades que cubre sale_price
    # (que es el TOTAL de la línea, no por unidad).
    quantity: int = 1
    date: datetime
    client_name: str | None = None
    user_id: uuid.UUID | None = None   # usuari registrat (opcional)
    discogs_sale_id: int | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _item_o_manual(self):
        if self.item_id is None:
            if not (self.description and self.description.strip()):
                raise ValueError("Un article manual necessita descripcion")
            if self.tipus_iva_id is None:
                raise ValueError("Un article manual necessita tipus_iva_id")
        return self


class VentaExternaLoteLineaIn(BaseModel):
    item_id: uuid.UUID | None = None
    description: str | None = None
    tipus_iva_id: int | None = None
    sale_price: Decimal
    # Solo relevante para condicion='nou' (stock agregado): unidades que
    # cubre sale_price (que es el TOTAL de la línea, no por unidad).
    quantity: int = 1

    @model_validator(mode="after")
    def _item_o_manual(self):
        if self.item_id is None:
            if not (self.description and self.description.strip()):
                raise ValueError("Un article manual necessita descripcion")
            if self.tipus_iva_id is None:
                raise ValueError("Un article manual necessita tipus_iva_id")
        return self


class VentaExternaLoteIn(BaseModel):
    """Venta de varios ejemplares (discos distintos, o varias copias del
    mismo álbum) en una sola operación de TPV. Comparten canal, método de
    pago, fecha y cliente; el precio se fija por línea porque cada ejemplar
    es único."""
    lineas: list[VentaExternaLoteLineaIn] = Field(min_length=1)
    channel: Literal["mostrador", "discogs", "otro"] = "mostrador"
    payment_method: Literal["efectivo", "tarjeta", "bizum", "bono_cultural"] = "efectivo"
    date: datetime
    client_name: str | None = None
    user_id: uuid.UUID | None = None
    notes: str | None = None


class VincularUsuariTicketIn(BaseModel):
    """Vincula (o desvincula, amb None) un usuari registrat a totes les
    línies d'un tiquet ja cobrat — per quan al moment de vendre no es va
    triar client i es vol lligar més tard des de Resum vendes."""
    user_id: uuid.UUID | None = None


class VentaExternaOut(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID
    item_id: uuid.UUID | None
    description: str | None = None
    channel: str
    payment_method: str = "efectivo"
    sale_price: Decimal
    coste_adquisicion: Decimal | None
    date: datetime
    client_name: str | None = None
    user_id: uuid.UUID | None = None
    user_nom: str | None = None
    discogs_sale_id: int | None
    notes: str | None
    created_at: datetime
    tipus_iva_id: int | None = None
    vat_pct: Decimal | None = None
    vat_amount: Decimal | None = None
    quantity: int = 1
    condition: str | None = None
    # Enriquecido en el endpoint (no viene del ORM directamente)
    artista: str | None = None
    titulo: str | None = None
    devuelta: bool = False

    model_config = {"from_attributes": True}
