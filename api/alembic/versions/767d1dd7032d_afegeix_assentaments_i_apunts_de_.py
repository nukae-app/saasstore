"""afegeix assentaments i apunts de partida doble

Revision ID: 767d1dd7032d
Revises: 1f6cdaeec993
Create Date: 2026-08-31 14:54:47.868174

Fase 2 del mòdul de contabilitat: motor de posting automàtic (ver
app/services/comptabilitat_posting.py). Tres taules noves, cap canvi a les
existents:

- `assentament_comptadors`: comptador correlatiu d'assentaments per any
  fiscal (requisit legal del Libro Diario) — actualitzat amb UPDATE
  condicionat, mai SELECT+UPDATE, mateix criteri que la reserva atòmica
  d'exemplars.
- `assentaments` (JournalEntry): capçalera de l'assentament. `source_type`/
  `source_id` apunten al document de negoci que el va originar; `source_id`
  no és FK real perquè cada `source_type` apunta a una taula diferent.
- `apunts` (JournalLine): línies de l'assentament, amb el CHECK
  `ck_apunts_debit_xor_credit` (exactament un de debit/credit > 0 per
  línia). La invariant d'assentament complet (sum(debit)==sum(credit)) es
  garanteix al servei, no aquí — Postgres no la pot expressar com a CHECK
  entre files.

NOTA: com a la migració anterior (1f6cdaeec993), l'autogenerate va detectar
~60 diferències de nom d'índex no relacionades (deute de la Fase 4 Etapa B).
Descartades expressament d'aquesta migració pel mateix motiu.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '767d1dd7032d'
down_revision: Union[str, None] = '1f6cdaeec993'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'assentament_comptadors',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('fiscal_year', sa.Integer(), nullable=False),
        sa.Column('next_number', sa.Integer(), server_default='1', nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'fiscal_year'),
    )
    op.create_index(op.f('ix_assentament_comptadors_fiscal_year'), 'assentament_comptadors', ['fiscal_year'], unique=False)
    op.create_index(op.f('ix_assentament_comptadors_tenant_id'), 'assentament_comptadors', ['tenant_id'], unique=False)

    op.create_table(
        'assentaments',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('fiscal_year', sa.Integer(), nullable=False),
        sa.Column('entry_number', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=False),
        sa.Column(
            'source_type',
            sa.Enum('venda_web', 'venda_externa', 'despesa_alta', 'despesa_pagament', 'caixa_diaria', 'manual', name='journal_source_type'),
            nullable=False,
        ),
        sa.Column('source_id', sa.Uuid(), nullable=True),
        sa.Column('period_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['period_id'], ['periodes_comptables.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'fiscal_year', 'entry_number'),
    )
    op.create_index(op.f('ix_assentaments_date'), 'assentaments', ['date'], unique=False)
    op.create_index(op.f('ix_assentaments_fiscal_year'), 'assentaments', ['fiscal_year'], unique=False)
    op.create_index(op.f('ix_assentaments_period_id'), 'assentaments', ['period_id'], unique=False)
    op.create_index(op.f('ix_assentaments_source_id'), 'assentaments', ['source_id'], unique=False)
    op.create_index(op.f('ix_assentaments_source_type'), 'assentaments', ['source_type'], unique=False)
    op.create_index(op.f('ix_assentaments_tenant_id'), 'assentaments', ['tenant_id'], unique=False)

    op.create_table(
        'apunts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('entry_id', sa.Uuid(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('debit', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
        sa.Column('credit', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.CheckConstraint('(debit = 0 AND credit > 0) OR (debit > 0 AND credit = 0)', name='ck_apunts_debit_xor_credit'),
        sa.ForeignKeyConstraint(['account_id'], ['comptes_comptables.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['entry_id'], ['assentaments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_apunts_account_id'), 'apunts', ['account_id'], unique=False)
    op.create_index(op.f('ix_apunts_entry_id'), 'apunts', ['entry_id'], unique=False)
    op.create_index(op.f('ix_apunts_tenant_id'), 'apunts', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_apunts_tenant_id'), table_name='apunts')
    op.drop_index(op.f('ix_apunts_entry_id'), table_name='apunts')
    op.drop_index(op.f('ix_apunts_account_id'), table_name='apunts')
    op.drop_table('apunts')

    op.drop_index(op.f('ix_assentaments_tenant_id'), table_name='assentaments')
    op.drop_index(op.f('ix_assentaments_source_type'), table_name='assentaments')
    op.drop_index(op.f('ix_assentaments_source_id'), table_name='assentaments')
    op.drop_index(op.f('ix_assentaments_period_id'), table_name='assentaments')
    op.drop_index(op.f('ix_assentaments_fiscal_year'), table_name='assentaments')
    op.drop_index(op.f('ix_assentaments_date'), table_name='assentaments')
    op.drop_table('assentaments')

    op.drop_index(op.f('ix_assentament_comptadors_tenant_id'), table_name='assentament_comptadors')
    op.drop_index(op.f('ix_assentament_comptadors_fiscal_year'), table_name='assentament_comptadors')
    op.drop_table('assentament_comptadors')
