import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
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


class AssetCategory(str, enum.Enum):
    maquinaria = "maquinaria"                    # 213
    mobiliari = "mobiliari"                      # 216
    equips_informatics = "equips_informatics"    # 217
    elements_transport = "elements_transport"    # 218
    altres = "altres"                            # 219


class DepreciationMethod(str, enum.Enum):
    lineal = "lineal"


class FixedAsset(TenantScoped, Base):
    """Actiu fix (immobilitzat material). El % d'amortització anual el
    decideix l'admin a mà (les taules oficials d'Hisenda són una referència
    externa, no es guarden aquí — canvien i equivocar-se té conseqüències
    fiscals reals). L'alta posteja el seu propi assentament (Debe categoria +
    472 / Haber 400, ver services/comptabilitat_posting.py::post_actiu_alta);
    NO passa per `Despesa`, els actius no encaixen a `CategoriaDespesa`.

    La baixa (venda/desballestament, amb càlcul de guany/pèrdua 671/771) NO
    està implementada — deliberadament fora d'abast, ver docstring de
    services/comptabilitat_posting.py per context. `disposal_date`/
    `disposal_amount` només deixen constància manual, no generen assentament."""

    __tablename__ = "actius"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(300))
    category: Mapped[AssetCategory] = mapped_column(Enum(AssetCategory, name="asset_category"), index=True)
    acquisition_date: Mapped[date] = mapped_column(Date, index=True)
    acquisition_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # base imposable, sense IVA
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    supplier_name: Mapped[str | None] = mapped_column(String(300))
    depreciation_method: Mapped[DepreciationMethod] = mapped_column(
        Enum(DepreciationMethod, name="depreciation_method"), default=DepreciationMethod.lineal
    )
    annual_depreciation_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    disposal_date: Mapped[date | None] = mapped_column(Date)
    disposal_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    depreciations: Mapped[list["AssetDepreciationEntry"]] = relationship(
        back_populates="asset", order_by="AssetDepreciationEntry.year, AssetDepreciationEntry.month"
    )


class AssetDepreciationEntry(TenantScoped, Base):
    """Una fila per actiu i mes amortitzat — generada sota demanda (mai per
    cron) via `POST /admin/amortitzacions/{y}/{m}/generar`. La unicitat
    (tenant, actiu, any, mes) és el que fa la generació idempotent: cridar-la
    dues vegades el mateix mes no duplica res."""

    __tablename__ = "actiu_amortitzacions"
    __table_args__ = (UniqueConstraint("tenant_id", "actiu_id", "year", "month"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    actiu_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("actius.id", ondelete="CASCADE"), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    month: Mapped[int] = mapped_column(Integer)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    asset: Mapped["FixedAsset"] = relationship(back_populates="depreciations")
