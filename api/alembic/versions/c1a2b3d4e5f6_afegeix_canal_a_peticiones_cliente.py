"""afegeix_canal_a_peticiones_cliente

Revision ID: c1a2b3d4e5f6
Revises: aea779e03404
Create Date: 2026-07-22 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c1a2b3d4e5f6"
down_revision: Union[str, None] = "aea779e03404"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "peticiones_cliente",
        sa.Column("canal", sa.String(20), nullable=False, server_default="web"),
    )


def downgrade() -> None:
    op.drop_column("peticiones_cliente", "canal")
