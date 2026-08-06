"""afegeix email_verified a users i purpose a auth_tokens

Revision ID: b610df5aa553
Revises: 09134b164755
Create Date: 2026-07-18 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b610df5aa553'
down_revision: Union[str, None] = '09134b164755'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default=true perquè els comptes ja existents (alta amb contrasenya
    # inclosa) no quedin bloquejats retroactivament; el nou flux de /auth/register
    # posa email_verified=False explícitament al crear l'usuari.
    op.add_column('users', sa.Column('email_verified', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.alter_column('users', 'email_verified', server_default=None)

    op.add_column('auth_tokens', sa.Column('purpose', sa.String(length=20), nullable=False, server_default='magic_link'))
    op.alter_column('auth_tokens', 'purpose', server_default=None)


def downgrade() -> None:
    op.drop_column('auth_tokens', 'purpose')
    op.drop_column('users', 'email_verified')
