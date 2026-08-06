"""afegeix_avisada_recollida_at_a_orders

Revision ID: b3c4d5e6f7a8
Revises: a552e477bc7b
Create Date: 2026-07-23 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "a552e477bc7b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("avisada_recollida_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "avisada_recollida_at")
