"""tenant_vertical

Revision ID: f4d289479368
Revises: d49fb8ad7897
Create Date: 2026-08-07 09:20:00.000000

Fase 4 (ver plan, sección B): añade el concepto de vertical de negocio al
tenant. `server_default='vinils'` cubre el tenant existente sin necesidad
de un backfill aparte.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f4d289479368'
down_revision: Union[str, None] = 'd49fb8ad7897'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'tenants',
        sa.Column('vertical', sa.String(length=30), nullable=False, server_default='vinils'),
    )


def downgrade() -> None:
    op.drop_column('tenants', 'vertical')
