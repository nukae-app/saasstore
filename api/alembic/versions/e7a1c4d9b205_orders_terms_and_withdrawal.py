"""orders.terms_accepted_at i orders.withdrawal_requested_at (prova legal)

Revision ID: e7a1c4d9b205
Revises: d5f2a8c1b936
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e7a1c4d9b205"
down_revision: Union[str, None] = "d5f2a8c1b936"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable i sense backfill: les comandes existents no tenen prova
    # d'acceptació i no s'inventa; només les noves la porten.
    op.add_column("orders", sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("withdrawal_requested_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "withdrawal_requested_at")
    op.drop_column("orders", "terms_accepted_at")
