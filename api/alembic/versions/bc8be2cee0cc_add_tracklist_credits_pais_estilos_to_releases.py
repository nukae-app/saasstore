"""add_tracklist_credits_pais_estilos_to_releases

Revision ID: bc8be2cee0cc
Revises: a3f1c9d82e40
Create Date: 2026-06-12 21:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "bc8be2cee0cc"
down_revision: Union[str, None] = "a3f1c9d82e40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("releases", sa.Column("pais", sa.String(100), nullable=True))
    op.add_column("releases", sa.Column("estilos", sa.String(300), nullable=True))
    op.add_column("releases", sa.Column("tracklist", sa.JSON(), nullable=True))
    op.add_column("releases", sa.Column("credits", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("releases", "credits")
    op.drop_column("releases", "tracklist")
    op.drop_column("releases", "estilos")
    op.drop_column("releases", "pais")
