"""Afegeix retenció d'IRPF a despeses

Revision ID: 450069a2a06a
Revises: 909c657203ee
Create Date: 2026-09-08 00:00:00.000000

Modela la retenció d'IRPF practicada a un proveïdor (Model 111 si és per
factures de professionals, Model 115 si és per lloguer del local) — cap dels
dos existia fins ara. Afegeix el compte 4751 (H.P. creditora per retencions
practicades) al pla de comptes de tots els tenants existents amb jurisdicció
'es' (mateix criteri que altres altes de compte via migració: seed nou no
n'afegeix cap a tenants ja creats, ver comptabilitat_seed.py).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '450069a2a06a'
down_revision: Union[str, None] = '909c657203ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    retencio_tipus = sa.Enum('professional', 'lloguer', name='retencio_tipus')
    retencio_tipus.create(op.get_bind(), checkfirst=True)
    op.add_column('despeses', sa.Column('retencio_tipus', sa.Enum('professional', 'lloguer', name='retencio_tipus'), nullable=True))
    op.add_column('despeses', sa.Column('retencio_pct', sa.Numeric(precision=5, scale=2), nullable=True))
    op.add_column('despeses', sa.Column('retencio_import', sa.Numeric(precision=10, scale=2), nullable=True))
    op.create_index(op.f('ix_despeses_retencio_tipus'), 'despeses', ['retencio_tipus'], unique=False)

    op.execute("""
        INSERT INTO comptes_comptables (tenant_id, code, name, "group", account_type, active, created_at)
        SELECT tenant_id, '4751', 'H.P. creditora per retencions practicades', 4, 'passiu', true, now()
        FROM comptes_comptables
        WHERE code = '4750'
        AND tenant_id NOT IN (
            SELECT tenant_id FROM comptes_comptables WHERE code = '4751'
        )
    """)


def downgrade() -> None:
    op.execute("DELETE FROM comptes_comptables WHERE code = '4751'")
    op.drop_index(op.f('ix_despeses_retencio_tipus'), table_name='despeses')
    op.drop_column('despeses', 'retencio_import')
    op.drop_column('despeses', 'retencio_pct')
    op.drop_column('despeses', 'retencio_tipus')
    sa.Enum(name='retencio_tipus').drop(op.get_bind(), checkfirst=True)
