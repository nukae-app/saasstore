"""add_spotify_connections_and_pgtrgm

Revision ID: a3f1c9d82e40
Revises: 02b9ed04b355
Create Date: 2026-06-12 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3f1c9d82e40'
down_revision: Union[str, None] = '02b9ed04b355'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        'spotify_connections',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('spotify_user_id', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=200), nullable=True),
        sa.Column('access_token', sa.Text(), nullable=False),
        sa.Column('refresh_token', sa.Text(), nullable=False),
        sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('connected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id'),
        sa.UniqueConstraint('spotify_user_id'),
    )


def downgrade() -> None:
    op.drop_table('spotify_connections')
