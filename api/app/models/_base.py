import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class TenantScoped:
    """Mixin declarativo: añade `tenant_id` a cualquier tabla que lo use
    (`class X(TenantScoped, Base)`). No es una tabla propia."""

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
