"""bizum_bono_cultural_metodo_pago

Revision ID: 9a1c5e7f2b6d
Revises: 4e64f56931ca
Create Date: 2026-08-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9a1c5e7f2b6d'
down_revision: Union[str, None] = '4e64f56931ca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE metodo_pago ADD VALUE IF NOT EXISTS 'bizum'")
    op.execute("ALTER TYPE metodo_pago ADD VALUE IF NOT EXISTS 'bono_cultural'")


def downgrade() -> None:
    # Postgres no permet treure valors d'un ENUM sense recrear el tipus;
    # no cal per a una migració additiva com aquesta.
    pass
