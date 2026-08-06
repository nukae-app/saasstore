"""afegeix_esta_sonant_a_releases

Revision ID: d4e5f6a7b8c9
Revises: c1a2b3d4e5f6
Create Date: 2026-07-22 14:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c1a2b3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("releases", sa.Column("esta_sonant", sa.Boolean(), nullable=False, server_default="false"))
    op.create_index("ix_releases_esta_sonant", "releases", ["esta_sonant"])

    # "Recomanat" -> "Recomanats": ara és el checkbox explícit de "Selecció del
    # curador" a la portada, no una etiqueta genèrica més entre d'altres.
    op.execute("UPDATE etiquetes SET nom_ca = 'Recomanats' WHERE slug = 'recomanat'")


def downgrade() -> None:
    op.execute("UPDATE etiquetes SET nom_ca = 'Recomanat' WHERE slug = 'recomanat'")
    op.drop_index("ix_releases_esta_sonant", "releases")
    op.drop_column("releases", "esta_sonant")
