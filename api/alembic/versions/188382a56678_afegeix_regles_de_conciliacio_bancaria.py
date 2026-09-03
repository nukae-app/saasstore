"""Afegeix regles de conciliacio bancaria

Revision ID: 188382a56678
Revises: f9f2d297102d
Create Date: 2026-09-02 15:56:22.703269

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '188382a56678'
down_revision: Union[str, None] = 'f9f2d297102d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('regles_conciliacio',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('pattern', sa.String(length=200), nullable=False),
    sa.Column('proveidor_id', sa.Uuid(), nullable=False),
    sa.Column('active', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['proveidor_id'], ['proveedores.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_regles_conciliacio_active'), 'regles_conciliacio', ['active'], unique=False)
    op.create_index(op.f('ix_regles_conciliacio_proveidor_id'), 'regles_conciliacio', ['proveidor_id'], unique=False)
    op.create_index(op.f('ix_regles_conciliacio_tenant_id'), 'regles_conciliacio', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_regles_conciliacio_tenant_id'), table_name='regles_conciliacio')
    op.drop_index(op.f('ix_regles_conciliacio_proveidor_id'), table_name='regles_conciliacio')
    op.drop_index(op.f('ix_regles_conciliacio_active'), table_name='regles_conciliacio')
    op.drop_table('regles_conciliacio')
