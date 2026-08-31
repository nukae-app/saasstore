"""afegeix actius fixos i amortitzacions

Revision ID: 84f8e4883ad3
Revises: 767d1dd7032d
Create Date: 2026-08-31 19:25:26.780638

Fase 4 del mòdul de contabilitat: actius fixos (`FixedAsset`) i les seves
amortitzacions mensuals (`AssetDepreciationEntry`) — ver models/actius.py
per què la baixa (venda/desballestament) no està implementada encara.

- Dues taules noves: `actius`, `actiu_amortitzacions`.
- Dos valors nous a l'enum `journal_source_type` (`actiu_alta`,
  `actiu_amortitzacio`) — l'autogenerate d'Alembic NO detecta canvis de
  valors d'un Enum de Postgres ja existent (només create/drop de columnes),
  així que aquesta part és manual, no ve de l'autogenerate.
- Backfill: 4 comptes nous al pla de comptes (213, 219, 671, 771) per als
  tenants que ja en tenien un (jurisdicció "es") — mateix criteri que la
  migració 1f6cdaeec993, però aquí no cal cap dada nova de l'usuari (els
  codis/noms són fixos), així que el backfill entra a la pròpia migració.

NOTA (com a les dues migracions anteriors): descartades ~60 diferències de
nom d'índex no relacionades, detectades per l'autogenerate (deute de la
Fase 4 Etapa B, no d'aquesta fase 4 de contabilitat).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '84f8e4883ad3'
down_revision: Union[str, None] = '767d1dd7032d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOUS_COMPTES = [
    ("213", "Maquinaria", 2, "actiu"),
    ("219", "Altres immobilitzats materials", 2, "actiu"),
    ("671", "Pèrdues procedents de l'immobilitzat material", 6, "despesa"),
    ("771", "Beneficis procedents de l'immobilitzat material", 7, "ingres"),
]


def upgrade() -> None:
    op.create_table(
        'actius',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=300), nullable=False),
        sa.Column('category', sa.Enum('maquinaria', 'mobiliari', 'equips_informatics', 'elements_transport', 'altres', name='asset_category'), nullable=False),
        sa.Column('acquisition_date', sa.Date(), nullable=False),
        sa.Column('acquisition_cost', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('vat_amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('supplier_name', sa.String(length=300), nullable=True),
        sa.Column('depreciation_method', sa.Enum('lineal', name='depreciation_method'), nullable=False),
        sa.Column('annual_depreciation_pct', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('disposal_date', sa.Date(), nullable=True),
        sa.Column('disposal_amount', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_actius_acquisition_date'), 'actius', ['acquisition_date'], unique=False)
    op.create_index(op.f('ix_actius_category'), 'actius', ['category'], unique=False)
    op.create_index(op.f('ix_actius_tenant_id'), 'actius', ['tenant_id'], unique=False)

    op.create_table(
        'actiu_amortitzacions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('actiu_id', sa.Uuid(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['actiu_id'], ['actius.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'actiu_id', 'year', 'month'),
    )
    op.create_index(op.f('ix_actiu_amortitzacions_actiu_id'), 'actiu_amortitzacions', ['actiu_id'], unique=False)
    op.create_index(op.f('ix_actiu_amortitzacions_tenant_id'), 'actiu_amortitzacions', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_actiu_amortitzacions_year'), 'actiu_amortitzacions', ['year'], unique=False)

    op.execute("ALTER TYPE journal_source_type ADD VALUE IF NOT EXISTS 'actiu_alta'")
    op.execute("ALTER TYPE journal_source_type ADD VALUE IF NOT EXISTS 'actiu_amortitzacio'")

    for code, name, grup, account_type in NOUS_COMPTES:
        op.execute(
            sa.text(
                """
                INSERT INTO comptes_comptables (code, name, "group", account_type, active, created_at, tenant_id)
                SELECT :code, :name, :grup, CAST(:account_type AS account_type), true, now(), t.id
                FROM tenants t
                WHERE t.accounting_jurisdiction_id = 'es'
                  AND NOT EXISTS (
                      SELECT 1 FROM comptes_comptables cc WHERE cc.tenant_id = t.id AND cc.code = :code
                  )
                """
            ).bindparams(code=code, name=name, grup=grup, account_type=account_type)
        )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM comptes_comptables WHERE code IN ('213', '219', '671', '771')")
    )
    # No es treuen 'actiu_alta'/'actiu_amortitzacio' de journal_source_type:
    # Postgres no permet eliminar valors d'un enum sense recrear el tipus.

    op.drop_index(op.f('ix_actiu_amortitzacions_year'), table_name='actiu_amortitzacions')
    op.drop_index(op.f('ix_actiu_amortitzacions_tenant_id'), table_name='actiu_amortitzacions')
    op.drop_index(op.f('ix_actiu_amortitzacions_actiu_id'), table_name='actiu_amortitzacions')
    op.drop_table('actiu_amortitzacions')

    op.drop_index(op.f('ix_actius_tenant_id'), table_name='actius')
    op.drop_index(op.f('ix_actius_category'), table_name='actius')
    op.drop_index(op.f('ix_actius_acquisition_date'), table_name='actius')
    op.drop_table('actius')
