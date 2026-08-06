"""add_marges_config

Revision ID: 9f3d7c2b1a44
Revises: d4e5f6a7b8c9
Create Date: 2026-07-22 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9f3d7c2b1a44'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'marges_config',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('nom', sa.String(length=200), nullable=False),
        sa.Column('percentatge', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('per_defecte_nou', sa.Boolean(), nullable=False),
        sa.Column('per_defecte_segona_ma', sa.Boolean(), nullable=False),
        sa.Column('actiu', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_marges_config_per_defecte_nou'), 'marges_config', ['per_defecte_nou'], unique=False)
    op.create_index(op.f('ix_marges_config_per_defecte_segona_ma'), 'marges_config', ['per_defecte_segona_ma'], unique=False)
    op.create_index(op.f('ix_marges_config_actiu'), 'marges_config', ['actiu'], unique=False)

    # Seed: un marge raonable de sortida per a cada condició, editable des de l'admin.
    op.execute(
        "INSERT INTO marges_config (nom, percentatge, per_defecte_nou, per_defecte_segona_ma, actiu) "
        "VALUES ('Marge estàndard nou', 40.00, true, false, true)"
    )
    op.execute(
        "INSERT INTO marges_config (nom, percentatge, per_defecte_nou, per_defecte_segona_ma, actiu) "
        "VALUES ('Marge estàndard 2a mà', 60.00, false, true, true)"
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_marges_config_actiu'), table_name='marges_config')
    op.drop_index(op.f('ix_marges_config_per_defecte_segona_ma'), table_name='marges_config')
    op.drop_index(op.f('ix_marges_config_per_defecte_nou'), table_name='marges_config')
    op.drop_table('marges_config')
