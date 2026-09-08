"""Afegeix factura de venda (Bloc B2)

Revision ID: c45438ab3d61
Revises: 450069a2a06a
Create Date: 2026-09-08 00:00:00.000000

Capa base del Reglament de Facturació (RD 1619/2012): numeració
correlativa (reutilitza `document_comptadors`, ja preparat per a
document_type='factura'), dades emissor/receptor, desglossament d'IVA. NO
implementa VeriFactu (RD 1007/2023) — ver docstring de
app/models/documents.py.

Afegeix també el compte 705 (Prestació de serveis) al pla de comptes de
tots els tenants existents amb jurisdicció 'es', i el valor 'factura_manual'
a l'enum journal_source_type (mateix patró que 909c657203ee).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c45438ab3d61'
down_revision: Union[str, None] = '450069a2a06a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE journal_source_type ADD VALUE IF NOT EXISTS 'factura_manual'")

    # Els enums 'factura_origen'/'factura_status' es creen sols com a part de
    # create_table (columnes inline) — mateix criteri que la resta de taules
    # noves d'aquest projecte (p.ex. 0c52eb025920), a diferència de quan un
    # enum s'afegeix amb ADD COLUMN sobre una taula ja existent (aquest cas sí
    # necessita precrear el tipus, ver ed0cb3ae47e4).
    op.create_table(
        'factures',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('fiscal_year', sa.Integer(), nullable=False),
        sa.Column('number', sa.Integer(), nullable=False),
        sa.Column('origen', sa.Enum('ticket', 'manual', name='factura_origen'), nullable=False),
        sa.Column('status', sa.Enum('emesa', 'anullada', name='factura_status'), server_default='emesa', nullable=False),
        sa.Column('order_id', sa.Uuid(), nullable=True),
        sa.Column('venta_externa_ticket_id', sa.Uuid(), nullable=True),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('client_name', sa.String(length=200), nullable=False),
        sa.Column('client_nif', sa.String(length=20), nullable=True),
        sa.Column('client_address', sa.JSON(), nullable=True),
        sa.Column('issue_date', sa.Date(), server_default=sa.text('CURRENT_DATE'), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('base_total', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('vat_total', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('total', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'fiscal_year', 'number'),
    )
    op.create_index(op.f('ix_factures_tenant_id'), 'factures', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_factures_fiscal_year'), 'factures', ['fiscal_year'], unique=False)
    op.create_index(op.f('ix_factures_origen'), 'factures', ['origen'], unique=False)
    op.create_index(op.f('ix_factures_status'), 'factures', ['status'], unique=False)
    op.create_index(op.f('ix_factures_order_id'), 'factures', ['order_id'], unique=False)
    op.create_index(op.f('ix_factures_venta_externa_ticket_id'), 'factures', ['venta_externa_ticket_id'], unique=False)
    op.create_index(op.f('ix_factures_user_id'), 'factures', ['user_id'], unique=False)

    op.create_table(
        'factura_linies',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('factura_id', sa.Uuid(), nullable=False),
        sa.Column('position', sa.Integer(), server_default='0', nullable=False),
        sa.Column('description', sa.String(length=500), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=10, scale=2), server_default='1', nullable=False),
        sa.Column('unit_price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('vat_pct', sa.Numeric(precision=5, scale=2), server_default='21', nullable=False),
        sa.ForeignKeyConstraint(['factura_id'], ['factures.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_factura_linies_tenant_id'), 'factura_linies', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_factura_linies_factura_id'), 'factura_linies', ['factura_id'], unique=False)

    op.execute("""
        INSERT INTO comptes_comptables (tenant_id, code, name, "group", account_type, active, created_at)
        SELECT tenant_id, '705', 'Prestació de serveis', 7, 'ingres', true, now()
        FROM comptes_comptables
        WHERE code = '700'
        AND tenant_id NOT IN (
            SELECT tenant_id FROM comptes_comptables WHERE code = '705'
        )
    """)


def downgrade() -> None:
    op.execute("DELETE FROM comptes_comptables WHERE code = '705'")
    op.drop_index(op.f('ix_factura_linies_factura_id'), table_name='factura_linies')
    op.drop_index(op.f('ix_factura_linies_tenant_id'), table_name='factura_linies')
    op.drop_table('factura_linies')
    op.drop_index(op.f('ix_factures_user_id'), table_name='factures')
    op.drop_index(op.f('ix_factures_venta_externa_ticket_id'), table_name='factures')
    op.drop_index(op.f('ix_factures_order_id'), table_name='factures')
    op.drop_index(op.f('ix_factures_status'), table_name='factures')
    op.drop_index(op.f('ix_factures_origen'), table_name='factures')
    op.drop_index(op.f('ix_factures_fiscal_year'), table_name='factures')
    op.drop_index(op.f('ix_factures_tenant_id'), table_name='factures')
    op.drop_table('factures')
    sa.Enum(name='factura_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='factura_origen').drop(op.get_bind(), checkfirst=True)
    # No es treu 'factura_manual' de journal_source_type: Postgres no permet
    # eliminar valors d'un enum sense recrear el tipus (mateix criteri que 909c657203ee).
