"""trams_enviament per país (no per zona nacional/internacional)

Revision ID: c94f2a7e1d38
Revises: b7e21f4c9a06
Create Date: 2026-07-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c94f2a7e1d38'
down_revision: Union[str, None] = 'b7e21f4c9a06'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(op.f('ix_trams_enviament_zona'), table_name='trams_enviament')
    # server_default='ES' només per migrar les files existents (eren la
    # tarifa "nacional"); es treu just després perquè cada tram nou hagi
    # d'indicar explícitament el país (via TramEnviamentIn, sense default).
    op.add_column(
        'trams_enviament',
        sa.Column('pais', sa.String(length=2), server_default='ES', nullable=False),
    )
    op.alter_column('trams_enviament', 'pais', server_default=None)
    op.create_index(op.f('ix_trams_enviament_pais'), 'trams_enviament', ['pais'], unique=False)
    op.drop_column('trams_enviament', 'zona')


def downgrade() -> None:
    op.add_column(
        'trams_enviament',
        sa.Column('zona', sa.String(length=20), server_default='nacional', nullable=False),
    )
    op.drop_index(op.f('ix_trams_enviament_pais'), table_name='trams_enviament')
    op.drop_column('trams_enviament', 'pais')
    op.create_index(op.f('ix_trams_enviament_zona'), 'trams_enviament', ['zona'], unique=False)
