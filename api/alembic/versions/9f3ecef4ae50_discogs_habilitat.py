"""discogs_habilitat

Revision ID: 9f3ecef4ae50
Revises: f6e5cb9b0832
Create Date: 2026-08-07 08:00:00.000000

Interruptor de Discogs per tenant (ver plan, sección C): por defecto False
para cualquier tenant nuevo (no todos los verticales usan Discogs), pero se
activa explícitamente para el tenant existente (recordstore), que sí lo usa
hoy en producción.
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '9f3ecef4ae50'
down_revision: Union[str, None] = 'f6e5cb9b0832'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_TENANT_ID = uuid.UUID('00000000-0000-0000-0000-000000000001')


def upgrade() -> None:
    op.add_column(
        'configuracio_botiga',
        sa.Column('discogs_habilitat', sa.Boolean(), nullable=False, server_default='false'),
    )
    op.execute(
        sa.text("UPDATE configuracio_botiga SET discogs_habilitat = true WHERE tenant_id = :tid").bindparams(
            sa.bindparam("tid", value=DEFAULT_TENANT_ID, type_=sa.Uuid())
        )
    )


def downgrade() -> None:
    op.drop_column('configuracio_botiga', 'discogs_habilitat')
