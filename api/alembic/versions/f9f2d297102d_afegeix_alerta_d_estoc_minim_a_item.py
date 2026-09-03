"""Afegeix alerta d'estoc minim a Item

Revision ID: f9f2d297102d
Revises: 0c52eb025920
Create Date: 2026-09-02 15:33:30.085957

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f9f2d297102d'
down_revision: Union[str, None] = '0c52eb025920'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('items', sa.Column('min_stock_alert', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('items', 'min_stock_alert')
