"""comissions_pagament_i_compte_626

Afegeix la taula `comissions_pagament` (config. de comissio bancaria per
canal de cobrament amb targeta, ver docs/PLAN_COBRAMENTS_PAGAMENTS.md), el
valor 'comissions_bancaries' a l'enum `categoria_despesa`, i la cuenta 626
"Serveis bancaris i similars" al pla de comptes. A diferencia de la resta
d'aquesta migracio (nomes esquema), l'alta del compte 626 SI es fa backfill
per als tenants ja existents amb jurisdiccio 'es' -- no es un dato de negoci
per confirmar (com el legal_form), es una cuenta estandard que tothom hauria
de tenir al pla de comptes.

Revision ID: c4adc39ce147
Revises: 9c1d4f2a6b31
Create Date: 2026-09-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4adc39ce147'
down_revision: Union[str, None] = '9c1d4f2a6b31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'comissions_pagament',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            'canal',
            sa.Enum('web_targeta', 'mostrador_targeta', 'club_targeta', name='canal_comissio'),
            nullable=False,
        ),
        sa.Column('mode', sa.Enum('deduccio', 'cobrament_apart', name='mode_comissio'), nullable=False),
        sa.Column('pct', sa.Numeric(precision=5, scale=2), server_default='0', nullable=False),
        sa.Column('fixed_fee', sa.Numeric(precision=10, scale=2), server_default='0', nullable=False),
        sa.Column('active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'canal', name='uq_comissions_pagament_tenant_canal'),
    )
    op.create_index(op.f('ix_comissions_pagament_active'), 'comissions_pagament', ['active'], unique=False)
    op.create_index(op.f('ix_comissions_pagament_canal'), 'comissions_pagament', ['canal'], unique=False)
    op.create_index(op.f('ix_comissions_pagament_tenant_id'), 'comissions_pagament', ['tenant_id'], unique=False)

    op.execute("ALTER TYPE categoria_despesa ADD VALUE IF NOT EXISTS 'comissions_bancaries'")

    # Backfill del compte 626 per als tenants existents amb pla de comptes
    # espanyol -- nomes si encara no el tenen (idempotent).
    op.execute(
        """
        INSERT INTO comptes_comptables (tenant_id, code, name, "group", account_type, active, created_at)
        SELECT t.id, '626', 'Serveis bancaris i similars', 6, 'despesa', true, now()
        FROM tenants t
        WHERE t.accounting_jurisdiction_id = 'es'
          AND NOT EXISTS (
              SELECT 1 FROM comptes_comptables c WHERE c.tenant_id = t.id AND c.code = '626'
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM comptes_comptables c
        WHERE c.code = '626'
          AND NOT EXISTS (SELECT 1 FROM apunts a WHERE a.account_id = c.id)
        """
    )
    # Postgres no permet treure valors d'un ENUM sense recrear el tipus;
    # 'comissions_bancaries' es queda definit encara que no s'usi (mateix
    # criteri que 9a1c5e7f2b6d).

    op.drop_index(op.f('ix_comissions_pagament_tenant_id'), table_name='comissions_pagament')
    op.drop_index(op.f('ix_comissions_pagament_canal'), table_name='comissions_pagament')
    op.drop_index(op.f('ix_comissions_pagament_active'), table_name='comissions_pagament')
    op.drop_table('comissions_pagament')
    op.execute("DROP TYPE IF EXISTS mode_comissio")
    op.execute("DROP TYPE IF EXISTS canal_comissio")
