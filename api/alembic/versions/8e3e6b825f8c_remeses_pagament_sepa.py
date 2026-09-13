"""remeses_pagament_sepa

Afegeix les remeses de pagament a proveidors (SEPA pain.001, transferencia
-- no domiciliacio, ver docs/PLAN_COBRAMENTS_PAGAMENTS.md): taula
remeses_pagament + remesa_pagament_linies, el valor 'en_remesa' a l'enum
estat_pagament_despesa, el camp opcional `bic` a comptes_bancaris, i
`remesa_pagament_id` (nullable) a moviments_bancaris per poder conciliar
tota una remesa d'un cop quan el banc la liquida en bloc.

Revision ID: 8e3e6b825f8c
Revises: c4adc39ce147
Create Date: 2026-09-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8e3e6b825f8c'
down_revision: Union[str, None] = 'c4adc39ce147'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE estat_pagament_despesa ADD VALUE IF NOT EXISTS 'en_remesa'")

    op.add_column('comptes_bancaris', sa.Column('bic', sa.String(length=11), nullable=True))

    op.create_table(
        'remeses_pagament',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('fiscal_year', sa.Integer(), nullable=False),
        sa.Column('number', sa.Integer(), nullable=False),
        sa.Column(
            'status', sa.Enum('generada', 'anullada', name='remesa_pagament_status'),
            server_default='generada', nullable=False,
        ),
        sa.Column('compte_bancari_id', sa.Integer(), nullable=False),
        sa.Column('execution_date', sa.Date(), nullable=False),
        sa.Column('total', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('xml_content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['compte_bancari_id'], ['comptes_bancaris.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'fiscal_year', 'number', name='uq_remeses_pagament_tenant_year_number'),
    )
    op.create_index(op.f('ix_remeses_pagament_fiscal_year'), 'remeses_pagament', ['fiscal_year'], unique=False)
    op.create_index(op.f('ix_remeses_pagament_status'), 'remeses_pagament', ['status'], unique=False)
    op.create_index(op.f('ix_remeses_pagament_compte_bancari_id'), 'remeses_pagament', ['compte_bancari_id'], unique=False)
    op.create_index(op.f('ix_remeses_pagament_tenant_id'), 'remeses_pagament', ['tenant_id'], unique=False)

    op.create_table(
        'remesa_pagament_linies',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('remesa_id', sa.Uuid(), nullable=False),
        sa.Column('despesa_id', sa.Uuid(), nullable=False),
        sa.Column('position', sa.Integer(), server_default='0', nullable=False),
        sa.Column('import_', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('end_to_end_id', sa.String(length=35), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['remesa_id'], ['remeses_pagament.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['despesa_id'], ['despeses.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_remesa_pagament_linies_remesa_id'), 'remesa_pagament_linies', ['remesa_id'], unique=False)
    op.create_index(op.f('ix_remesa_pagament_linies_despesa_id'), 'remesa_pagament_linies', ['despesa_id'], unique=False)
    op.create_index(op.f('ix_remesa_pagament_linies_tenant_id'), 'remesa_pagament_linies', ['tenant_id'], unique=False)

    op.add_column('moviments_bancaris', sa.Column('remesa_pagament_id', sa.Uuid(), nullable=True))
    op.create_index(
        op.f('ix_moviments_bancaris_remesa_pagament_id'), 'moviments_bancaris', ['remesa_pagament_id'], unique=False
    )
    op.create_foreign_key(
        'fk_moviments_bancaris_remesa_pagament_id', 'moviments_bancaris', 'remeses_pagament',
        ['remesa_pagament_id'], ['id'], ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_moviments_bancaris_remesa_pagament_id', 'moviments_bancaris', type_='foreignkey')
    op.drop_index(op.f('ix_moviments_bancaris_remesa_pagament_id'), table_name='moviments_bancaris')
    op.drop_column('moviments_bancaris', 'remesa_pagament_id')

    op.drop_index(op.f('ix_remesa_pagament_linies_tenant_id'), table_name='remesa_pagament_linies')
    op.drop_index(op.f('ix_remesa_pagament_linies_despesa_id'), table_name='remesa_pagament_linies')
    op.drop_index(op.f('ix_remesa_pagament_linies_remesa_id'), table_name='remesa_pagament_linies')
    op.drop_table('remesa_pagament_linies')

    op.drop_index(op.f('ix_remeses_pagament_tenant_id'), table_name='remeses_pagament')
    op.drop_index(op.f('ix_remeses_pagament_compte_bancari_id'), table_name='remeses_pagament')
    op.drop_index(op.f('ix_remeses_pagament_status'), table_name='remeses_pagament')
    op.drop_index(op.f('ix_remeses_pagament_fiscal_year'), table_name='remeses_pagament')
    op.drop_table('remeses_pagament')
    op.execute("DROP TYPE IF EXISTS remesa_pagament_status")

    op.drop_column('comptes_bancaris', 'bic')

    # Postgres no permet treure valors d'un ENUM sense recrear el tipus;
    # 'en_remesa' es queda definit encara que no s'usi (mateix criteri que
    # 9a1c5e7f2b6d / c4adc39ce147).
