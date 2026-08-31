"""afegeix jurisdiccio comptable, forma juridica i pla de comptes

Revision ID: 1f6cdaeec993
Revises: 0a8e9cde93d3
Create Date: 2026-08-31 14:05:58.531876

Fase 1 del mòdul de contabilitat madur (docs/ARQUITECTURA_CORE_VERTICAL.md
— pendent d'afegir la secció corresponent): introdueix l'eix de jurisdicció
comptable (independent del vertical de negoci) i el pla de comptes.

- `accounting_jurisdictions`: registre de jurisdiccions suportades, mateix
  criteri que `verticals` (§20) — taula real en comptes de text lliure.
  Sembrada amb 5 files, només `es` amb `active=True` (única amb proveïdor de
  pla de comptes real, ver app/accounting_registry.py i
  app/services/comptabilitat_seed.py); `fr`/`it`/`uk`/`us` es reserven
  `active=False` fins que existeixi el seu chart provider — mateix criteri
  que les 10 verticals planificades de la migració 0a8e9cde93d3.
- `tenants.accounting_jurisdiction_id`: eix independent de `vertical_id`,
  amb default `"es"` (tots els tenants existents ho són).
- `configuracio_botiga.legal_form`: string nul·lable (no Enum de BD — cada
  jurisdicció té les seves pròpies formes jurídiques, ver
  accounting_registry.LEGAL_FORMS_BY_JURISDICTION). Sense backfill: els
  tenants existents no tenen aquest dato confirmat, no s'inventa.
- `comptes_comptables`: pla de comptes per tenant (`AccountingAccount`),
  sembrat a `create_tenant` per als tenants NOUS (fase 2, pendent de
  connectar l'endpoint) — aquesta migració només crea l'esquema, no
  sembra cap fila per als tenants existents.

NOTA: l'autogenerate d'Alembic va detectar ~60 diferències de nom d'índex
addicionals a tot el schema (arrossegades de renames de columna de la Fase
4 Etapa B — Postgres no renombra l'índex quan es renombra la columna).
S'han descartat expressament d'aquesta migració per no barrejar deute
tècnic no relacionat amb un canvi de model nou; queden pendents d'una
migració pròpia de sanejament d'índexs.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '1f6cdaeec993'
down_revision: Union[str, None] = '0a8e9cde93d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

accounting_jurisdictions_table = sa.table(
    "accounting_jurisdictions",
    sa.column("id", sa.String),
    sa.column("name", sa.String),
    sa.column("tax_model", sa.String),
    sa.column("active", sa.Boolean),
)

JURISDICTIONS = [
    {"id": "es", "name": "España", "tax_model": "eu_vat", "active": True},
    {"id": "fr", "name": "Francia", "tax_model": "eu_vat", "active": False},
    {"id": "it", "name": "Italia", "tax_model": "eu_vat", "active": False},
    {"id": "uk", "name": "Reino Unido", "tax_model": "uk_vat", "active": False},
    {"id": "us", "name": "Estados Unidos", "tax_model": "us_sales_tax", "active": False},
]


def upgrade() -> None:
    op.create_table(
        'accounting_jurisdictions',
        sa.Column('id', sa.String(length=2), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('tax_model', sa.String(length=30), nullable=False),
        sa.Column('active', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.bulk_insert(accounting_jurisdictions_table, JURISDICTIONS)

    op.create_table(
        'comptes_comptables',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(length=10), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('group', sa.Integer(), nullable=False),
        sa.Column('account_type', sa.Enum('actiu', 'passiu', 'patrimoni_net', 'ingres', 'despesa', name='account_type'), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'code'),
    )
    op.create_index(op.f('ix_comptes_comptables_account_type'), 'comptes_comptables', ['account_type'], unique=False)
    op.create_index(op.f('ix_comptes_comptables_active'), 'comptes_comptables', ['active'], unique=False)
    op.create_index(op.f('ix_comptes_comptables_code'), 'comptes_comptables', ['code'], unique=False)
    op.create_index(op.f('ix_comptes_comptables_group'), 'comptes_comptables', ['group'], unique=False)
    op.create_index(op.f('ix_comptes_comptables_tenant_id'), 'comptes_comptables', ['tenant_id'], unique=False)

    op.add_column('configuracio_botiga', sa.Column('legal_form', sa.String(length=30), nullable=True))
    op.create_index(op.f('ix_configuracio_botiga_legal_form'), 'configuracio_botiga', ['legal_form'], unique=False)

    op.add_column('tenants', sa.Column('accounting_jurisdiction_id', sa.String(length=2), server_default='es', nullable=False))
    op.create_index(op.f('ix_tenants_accounting_jurisdiction_id'), 'tenants', ['accounting_jurisdiction_id'], unique=False)
    op.create_foreign_key(None, 'tenants', 'accounting_jurisdictions', ['accounting_jurisdiction_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint(None, 'tenants', type_='foreignkey')
    op.drop_index(op.f('ix_tenants_accounting_jurisdiction_id'), table_name='tenants')
    op.drop_column('tenants', 'accounting_jurisdiction_id')

    op.drop_index(op.f('ix_configuracio_botiga_legal_form'), table_name='configuracio_botiga')
    op.drop_column('configuracio_botiga', 'legal_form')

    op.drop_index(op.f('ix_comptes_comptables_tenant_id'), table_name='comptes_comptables')
    op.drop_index(op.f('ix_comptes_comptables_group'), table_name='comptes_comptables')
    op.drop_index(op.f('ix_comptes_comptables_code'), table_name='comptes_comptables')
    op.drop_index(op.f('ix_comptes_comptables_active'), table_name='comptes_comptables')
    op.drop_index(op.f('ix_comptes_comptables_account_type'), table_name='comptes_comptables')
    op.drop_table('comptes_comptables')

    op.execute(accounting_jurisdictions_table.delete())
    op.drop_table('accounting_jurisdictions')
