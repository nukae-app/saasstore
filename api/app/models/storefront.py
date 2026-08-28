from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from ._base import TenantScoped


class HomeBlock(TenantScoped, Base):
    """Un bloc del home públic del tenant, en l'ordre en què es renderitza.
    Substitueix la seqüència fixa que abans hi havia hardcoded a
    web/app/[locale]/page.jsx (hero, novetats, curador...) per una llista
    per tenant que l'admin pot afegir/reordenar/apagar des del constructor.

    `block_type` es valida contra `api/app/blocks/registry.py` (un schema
    Pydantic fix per tipus), mateix criteri que `Tenant.vertical_id`: el
    vocabulari vàlid viu en codi, no en un constraint de BD. `props` només
    guarda copy/comportament configurable (títol, subtítol, quina etiqueta
    alimenta un carrusel...) — mai dades de catàleg en viu (releases,
    stock): això sempre el resol `page.jsx` en cada request, igual que avui.

    Sense columna `page` en v1 — només existeix una pàgina "construïble",
    el home. Afegir-la el dia que calgui una segona és una migració trivial."""

    __tablename__ = "home_blocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    block_type: Mapped[str] = mapped_column(String(60), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    props: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
