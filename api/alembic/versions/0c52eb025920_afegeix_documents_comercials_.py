"""Afegeix documents comercials (pressupostos i albarans)

Revision ID: 0c52eb025920
Revises: 84f8e4883ad3
Create Date: 2026-09-02 09:37:59.410336

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0c52eb025920'
down_revision: Union[str, None] = '84f8e4883ad3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('document_comptadors',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('document_type', sa.String(length=30), nullable=False),
    sa.Column('fiscal_year', sa.Integer(), nullable=False),
    sa.Column('next_number', sa.Integer(), server_default='1', nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'document_type', 'fiscal_year')
    )
    op.create_index(op.f('ix_document_comptadors_document_type'), 'document_comptadors', ['document_type'], unique=False)
    op.create_index(op.f('ix_document_comptadors_fiscal_year'), 'document_comptadors', ['fiscal_year'], unique=False)
    op.create_index(op.f('ix_document_comptadors_tenant_id'), 'document_comptadors', ['tenant_id'], unique=False)
    op.create_table('albarans',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('fiscal_year', sa.Integer(), nullable=False),
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Uuid(), nullable=False),
    sa.Column('delivery_date', sa.Date(), server_default=sa.text('CURRENT_DATE'), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'fiscal_year', 'number')
    )
    op.create_index(op.f('ix_albarans_fiscal_year'), 'albarans', ['fiscal_year'], unique=False)
    op.create_index(op.f('ix_albarans_order_id'), 'albarans', ['order_id'], unique=True)
    op.create_index(op.f('ix_albarans_tenant_id'), 'albarans', ['tenant_id'], unique=False)
    op.create_table('pressupostos',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('fiscal_year', sa.Integer(), nullable=False),
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('esborrany', 'enviat', 'acceptat', 'rebutjat', 'caducat', name='pressupost_status'), server_default='esborrany', nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=True),
    sa.Column('client_name', sa.String(length=200), nullable=False),
    sa.Column('client_email', sa.String(length=320), nullable=True),
    sa.Column('client_address', sa.JSON(), nullable=True),
    sa.Column('issue_date', sa.Date(), server_default=sa.text('CURRENT_DATE'), nullable=False),
    sa.Column('valid_until', sa.Date(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('converted_order_id', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['converted_order_id'], ['orders.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'fiscal_year', 'number')
    )
    op.create_index(op.f('ix_pressupostos_fiscal_year'), 'pressupostos', ['fiscal_year'], unique=False)
    op.create_index(op.f('ix_pressupostos_status'), 'pressupostos', ['status'], unique=False)
    op.create_index(op.f('ix_pressupostos_tenant_id'), 'pressupostos', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_pressupostos_user_id'), 'pressupostos', ['user_id'], unique=False)
    op.create_table('pressupost_linies',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('pressupost_id', sa.Uuid(), nullable=False),
    sa.Column('position', sa.Integer(), server_default='0', nullable=False),
    sa.Column('description', sa.String(length=500), nullable=False),
    sa.Column('quantity', sa.Numeric(precision=10, scale=2), server_default='1', nullable=False),
    sa.Column('unit_price', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('vat_pct', sa.Numeric(precision=5, scale=2), server_default='21', nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['pressupost_id'], ['pressupostos.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pressupost_linies_pressupost_id'), 'pressupost_linies', ['pressupost_id'], unique=False)
    op.create_index(op.f('ix_pressupost_linies_tenant_id'), 'pressupost_linies', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_pressupost_linies_tenant_id'), table_name='pressupost_linies')
    op.drop_index(op.f('ix_pressupost_linies_pressupost_id'), table_name='pressupost_linies')
    op.drop_table('pressupost_linies')
    op.drop_index(op.f('ix_pressupostos_user_id'), table_name='pressupostos')
    op.drop_index(op.f('ix_pressupostos_tenant_id'), table_name='pressupostos')
    op.drop_index(op.f('ix_pressupostos_status'), table_name='pressupostos')
    op.drop_index(op.f('ix_pressupostos_fiscal_year'), table_name='pressupostos')
    op.drop_table('pressupostos')
    op.drop_index(op.f('ix_albarans_tenant_id'), table_name='albarans')
    op.drop_index(op.f('ix_albarans_order_id'), table_name='albarans')
    op.drop_index(op.f('ix_albarans_fiscal_year'), table_name='albarans')
    op.drop_table('albarans')
    op.drop_index(op.f('ix_document_comptadors_tenant_id'), table_name='document_comptadors')
    op.drop_index(op.f('ix_document_comptadors_fiscal_year'), table_name='document_comptadors')
    op.drop_index(op.f('ix_document_comptadors_document_type'), table_name='document_comptadors')
    op.drop_table('document_comptadors')
