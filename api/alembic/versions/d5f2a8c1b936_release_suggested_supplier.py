"""releases.suggested_supplier_id: proveïdor habitual fixat a mà des del catàleg

Revision ID: d5f2a8c1b936
Revises: b3c8e1f27a90
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d5f2a8c1b936"
down_revision: Union[str, None] = "b3c8e1f27a90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable i sense backfill: cap disc existent canvia de comportament (el
    # suggeriment segueix sortint de l'històric) fins que s'hi fixi un proveïdor.
    op.add_column("releases", sa.Column("suggested_supplier_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_releases_suggested_supplier_id", "releases", "proveedores",
        ["suggested_supplier_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_releases_suggested_supplier_id", "releases", ["suggested_supplier_id"])


def downgrade() -> None:
    op.drop_index("ix_releases_suggested_supplier_id", table_name="releases")
    op.drop_constraint("fk_releases_suggested_supplier_id", "releases", type_="foreignkey")
    op.drop_column("releases", "suggested_supplier_id")
