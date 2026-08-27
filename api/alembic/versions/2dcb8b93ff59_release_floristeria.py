"""release_floristeria

Revision ID: 2dcb8b93ff59
Revises: f4d289479368
Create Date: 2026-08-07 09:20:42.608444

Fase 4 (ver plan, sección C): tabla de extensión 1:1 de Release para el
vertical floristeria (prueba de concepto) — solo los campos propios
(color, tipus_flor, durabilitat_dies), nunca rellenados para un tenant
vinils. `tenant_id` propio (no solo heredado vía release_id), mismo
criterio que ReleaseEtiqueta/ReleaseImage.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2dcb8b93ff59'
down_revision: Union[str, None] = 'f4d289479368'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        'release_floristeria',
        sa.Column('release_id', sa.Uuid(), nullable=False),
        sa.Column('color', sa.String(length=100), nullable=True),
        sa.Column('tipus_flor', sa.String(length=100), nullable=True),
        sa.Column('durabilitat_dies', sa.Integer(), nullable=True),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['release_id'], ['releases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('release_id'),
    )
    op.create_index(op.f('ix_release_floristeria_tenant_id'), 'release_floristeria', ['tenant_id'], unique=False)

    # Nota: se descartan a propósito dos cambios que autogenerate vuelve a
    # proponer cada vez (drift preexistente ya documentado en migraciones
    # anteriores, ajeno a esta): el drop de
    # `cobraments_subscripcio_ds_order_key` y el alter_column de
    # `configuracio_botiga.id`.

    if bind.dialect.name == 'postgresql':
        op.execute("ALTER TABLE release_floristeria ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE release_floristeria FORCE ROW LEVEL SECURITY")
        op.execute(
            "CREATE POLICY tenant_isolation ON release_floristeria "
            "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("DROP POLICY IF EXISTS tenant_isolation ON release_floristeria")
        op.execute("ALTER TABLE release_floristeria NO FORCE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE release_floristeria DISABLE ROW LEVEL SECURITY")

    op.drop_index(op.f('ix_release_floristeria_tenant_id'), table_name='release_floristeria')
    op.drop_table('release_floristeria')
