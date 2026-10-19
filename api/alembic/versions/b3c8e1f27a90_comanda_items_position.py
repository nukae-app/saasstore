"""numeració de línies: position a comanda_items i numero a solicitud_compra_items

Revision ID: b3c8e1f27a90
Revises: a7e3c91d5b42
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b3c8e1f27a90"
down_revision: Union[str, None] = "a7e3c91d5b42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # created_at empata dins d'una mateixa transacció: l'únic ordre estable
    # per a les files existents és (created_at, id), arbitrari com fins ara.
    op.add_column("comanda_items", sa.Column("position", sa.Integer(), nullable=False, server_default="0"))
    op.execute(
        """
        UPDATE comanda_items SET position = t.rn
        FROM (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY comanda_id ORDER BY created_at, id) AS rn
            FROM comanda_items
        ) t
        WHERE comanda_items.id = t.id
        """
    )

    op.add_column("solicitud_compra_items", sa.Column("numero", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE solicitud_compra_items SET numero = t.rn
        FROM (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY solicitud_id ORDER BY created_at, id) AS rn
            FROM solicitud_compra_items
            WHERE solicitud_id IS NOT NULL
        ) t
        WHERE solicitud_compra_items.id = t.id
        """
    )
    op.create_unique_constraint(
        "uq_solicitud_compra_items_solicitud_id_numero", "solicitud_compra_items", ["solicitud_id", "numero"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_solicitud_compra_items_solicitud_id_numero", "solicitud_compra_items", type_="unique")
    op.drop_column("solicitud_compra_items", "numero")
    op.drop_column("comanda_items", "position")
