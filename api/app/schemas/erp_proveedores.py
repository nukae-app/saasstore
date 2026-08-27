import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


TIPUS_PROVEIDOR = Literal[
    "distribuidor", "proveidor_online", "subministrador",
    "professional", "transport", "particular", "altres"
]


METODES_PAGAMENT_PROV = Literal[
    "transferencia", "rebut_domiciliat", "targeta", "efectiu", "paypal_altres"
]


class ProveedorIn(BaseModel):
    name: str
    type: TIPUS_PROVEIDOR | None = None
    nif: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    contact: str | None = None
    active: bool = True
    supplier_iban: str | None = None
    payment_method: METODES_PAGAMENT_PROV | None = None
    payment_days: int | None = None
    payment_day_of_month: int | None = None
    notes: str | None = None


class ProveedorOut(BaseModel):
    id: uuid.UUID
    name: str
    type: str | None
    nif: str | None
    email: str | None
    phone: str | None
    address: str | None
    contact: str | None
    active: bool
    supplier_iban: str | None
    payment_method: str | None
    payment_days: int | None
    payment_day_of_month: int | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- ERP: Compras a particular (entrada de stock instantània) ---
# Les compres a proveïdor ja no es creen directament: passen sempre per
# Comanda -> recepció (veure més avall).
