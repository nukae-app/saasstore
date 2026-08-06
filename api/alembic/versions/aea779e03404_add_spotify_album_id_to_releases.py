"""add_spotify_album_id_to_releases

Revision ID: aea779e03404
Revises: b610df5aa553
Create Date: 2026-07-19 21:40:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "aea779e03404"
down_revision: Union[str, None] = "b610df5aa553"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("releases", sa.Column("spotify_album_id", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("releases", "spotify_album_id")
