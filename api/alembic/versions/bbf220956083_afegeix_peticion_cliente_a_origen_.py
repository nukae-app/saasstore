"""afegeix peticion_cliente a origen_solicitud

Revision ID: bbf220956083
Revises: 613cb77f674d
Create Date: 2026-07-15 19:51:39.598324

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'bbf220956083'
down_revision: Union[str, None] = '613cb77f674d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE origen_solicitud ADD VALUE IF NOT EXISTS 'peticion_cliente'")


def downgrade() -> None:
    # Postgres no permet treure valors d'un ENUM sense recrear el tipus;
    # no cal per a una migració additiva com aquesta.
    pass
