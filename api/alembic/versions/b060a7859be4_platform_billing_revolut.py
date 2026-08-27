"""platform_billing_revolut

Revision ID: b060a7859be4
Revises: 311ff8279269
Create Date: 2026-08-27 08:12:09.982237

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b060a7859be4'
down_revision: Union[str, None] = '311ff8279269'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# NOTA: el --autogenerate original també detectava ~90 renames d'índex sense
# relació amb aquest canvi (deixalla cosmètica coneguda de la Fase 4 Etapa A,
# ver docs/ARQUITECTURA_CORE_VERTICAL.md §16 — les columnes es van renombrar
# a l'anglès però Postgres no renombra l'índex automàticament amb un RENAME
# COLUMN) més un `alter_column` de `configuracio_botiga.id` i un unique
# constraint de `cobraments_subscripcio` també sense relació. S'han tret a
# mà d'aquest fitxer: aquesta migració conté NOMÉS les 3 taules noves de
# facturació de plataforma.


def upgrade() -> None:
    op.create_table('platform_plans',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), server_default='EUR', nullable=False),
        sa.Column('billing_period', sa.Enum('monthly', 'yearly', name='platform_plan_billing_period'), server_default='monthly', nullable=False),
        sa.Column('revolut_plan_id', sa.String(length=100), nullable=True),
        sa.Column('revolut_variation_id', sa.String(length=100), nullable=True),
        sa.Column('active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('platform_invoices',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('revolut_event_id', sa.String(length=100), nullable=True),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), server_default='EUR', nullable=False),
        sa.Column('status', sa.Enum('pagada', 'fallida', 'pendent', name='platform_invoice_status'), nullable=False),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('raw_event', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('revolut_event_id'),
    )
    op.create_index(op.f('ix_platform_invoices_tenant_id'), 'platform_invoices', ['tenant_id'], unique=False)
    op.create_table('tenant_billing',
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('plan_id', sa.Uuid(), nullable=True),
        sa.Column('revolut_customer_id', sa.String(length=100), nullable=True),
        sa.Column('revolut_subscription_id', sa.String(length=100), nullable=True),
        sa.Column('status', sa.Enum('sense_pla', 'pendent_targeta', 'activa', 'impagada', 'cancellada', name='tenant_billing_status'), server_default='sense_pla', nullable=False),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['plan_id'], ['platform_plans.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('tenant_id'),
    )
    op.create_index(op.f('ix_tenant_billing_revolut_subscription_id'), 'tenant_billing', ['revolut_subscription_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_tenant_billing_revolut_subscription_id'), table_name='tenant_billing')
    op.drop_table('tenant_billing')
    op.drop_index(op.f('ix_platform_invoices_tenant_id'), table_name='platform_invoices')
    op.drop_table('platform_invoices')
    op.drop_table('platform_plans')
