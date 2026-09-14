"""model303_recc_prorrata_importacio

Suport per als tres regims especials i l'arrossegament de compensacio del
fitxer AEAT Model 303 (ver docs/PLAN_MODELO303_FITXER.md):
- configuracio_botiga: recc_actiu, prorrata_pct_provisional
- tipus_iva: exempt
- despeses: destino_iva (enum nou), importacio_diferida
- taula nova iva_compensacio_pendent

Revision ID: 7a3aa78f0c30
Revises: 8e3e6b825f8c
Create Date: 2026-09-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7a3aa78f0c30'
down_revision: Union[str, None] = '8e3e6b825f8c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'configuracio_botiga', sa.Column('recc_actiu', sa.Boolean(), server_default='false', nullable=False)
    )
    op.add_column(
        'configuracio_botiga', sa.Column('prorrata_pct_provisional', sa.Numeric(precision=5, scale=2), nullable=True)
    )

    op.add_column('tipus_iva', sa.Column('exempt', sa.Boolean(), server_default='false', nullable=False))

    op.add_column(
        'despeses',
        sa.Column(
            'destino_iva',
            sa.Enum('activitat_gravada', 'activitat_exempta', 'comu', name='destino_iva'),
            server_default='activitat_gravada', nullable=False,
        ),
    )
    op.create_index(op.f('ix_despeses_destino_iva'), 'despeses', ['destino_iva'], unique=False)
    op.add_column(
        'despeses', sa.Column('importacio_diferida', sa.Boolean(), server_default='false', nullable=False)
    )

    op.create_table(
        'iva_compensacio_pendent',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('fiscal_year', sa.Integer(), nullable=False),
        sa.Column('trimestre', sa.Integer(), nullable=False),
        sa.Column('import_pendent', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tenant_id', 'fiscal_year', 'trimestre', name='uq_iva_compensacio_pendent_tenant_year_trimestre'
        ),
    )
    op.create_index(
        op.f('ix_iva_compensacio_pendent_fiscal_year'), 'iva_compensacio_pendent', ['fiscal_year'], unique=False
    )
    op.create_index(
        op.f('ix_iva_compensacio_pendent_tenant_id'), 'iva_compensacio_pendent', ['tenant_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_iva_compensacio_pendent_tenant_id'), table_name='iva_compensacio_pendent')
    op.drop_index(op.f('ix_iva_compensacio_pendent_fiscal_year'), table_name='iva_compensacio_pendent')
    op.drop_table('iva_compensacio_pendent')

    op.drop_column('despeses', 'importacio_diferida')
    op.drop_index(op.f('ix_despeses_destino_iva'), table_name='despeses')
    op.drop_column('despeses', 'destino_iva')
    op.execute("DROP TYPE IF EXISTS destino_iva")

    op.drop_column('tipus_iva', 'exempt')

    op.drop_column('configuracio_botiga', 'prorrata_pct_provisional')
    op.drop_column('configuracio_botiga', 'recc_actiu')
