"""afegeix numeracio a solicituds de compra

Revision ID: 833428addbb2
Revises: 188382a56678
Create Date: 2026-09-03 14:19:14.324353

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '833428addbb2'
down_revision: Union[str, None] = '188382a56678'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('solicitudes_compra', sa.Column('fiscal_year', sa.Integer(), nullable=True))
    op.add_column('solicitudes_compra', sa.Column('number', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_solicitudes_compra_fiscal_year'), 'solicitudes_compra', ['fiscal_year'], unique=False)

    # Retroactiu: assigna any fiscal (any de created_at) i numeració
    # correlativa per tenant+any, ordenada per data de creació — mateix
    # criteri "SOL-{any}-{seq}" que s'usarà per a les noves.
    op.execute("""
        UPDATE solicitudes_compra sc
        SET fiscal_year = sub.fiscal_year, number = sub.rn
        FROM (
            SELECT id,
                   EXTRACT(YEAR FROM created_at)::int AS fiscal_year,
                   ROW_NUMBER() OVER (
                       PARTITION BY tenant_id, EXTRACT(YEAR FROM created_at)
                       ORDER BY created_at
                   ) AS rn
            FROM solicitudes_compra
        ) sub
        WHERE sc.id = sub.id
    """)

    # Sincronitza el comptador atòmic (`document_comptadors`) perquè la
    # numeració de les properes sol·licituds continuï just després de les
    # retroactives, sense duplicar-ne cap (violaria l'UNIQUE de sota).
    op.execute("""
        INSERT INTO document_comptadors (tenant_id, document_type, fiscal_year, next_number)
        SELECT tenant_id, 'solicitud_compra', fiscal_year, MAX(number) + 1
        FROM solicitudes_compra
        GROUP BY tenant_id, fiscal_year
        ON CONFLICT (tenant_id, document_type, fiscal_year)
        DO UPDATE SET next_number = GREATEST(document_comptadors.next_number, EXCLUDED.next_number)
    """)

    op.alter_column('solicitudes_compra', 'fiscal_year', existing_type=sa.Integer(), nullable=False)
    op.alter_column('solicitudes_compra', 'number', existing_type=sa.Integer(), nullable=False)
    op.create_unique_constraint(None, 'solicitudes_compra', ['tenant_id', 'fiscal_year', 'number'])


def downgrade() -> None:
    op.drop_constraint(None, 'solicitudes_compra', type_='unique')
    op.drop_index(op.f('ix_solicitudes_compra_fiscal_year'), table_name='solicitudes_compra')
    op.drop_column('solicitudes_compra', 'number')
    op.drop_column('solicitudes_compra', 'fiscal_year')
