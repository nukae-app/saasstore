"""split_factura_recepcio

Separa la recepcio (albara, num_factura -> num_albaran a compras) de la
factura (despeses): una Despesa pot cobrir diverses Compra (recepcions),
per aixo el link es mou de despeses.compra_id (1:1 unique) a
compras.despesa_id (N:1).

Revision ID: 9c1d4f2a6b31
Revises: 7b1f4a2c9e31
Create Date: 2026-07-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9c1d4f2a6b31"
down_revision = "7b1f4a2c9e31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("compras", "num_factura", new_column_name="num_albaran")

    op.add_column("compras", sa.Column("despesa_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_compras_despesa_id"), "compras", ["despesa_id"], unique=False)
    op.create_foreign_key(
        "fk_compras_despesa_id_despeses", "compras", "despeses",
        ["despesa_id"], ["id"], ondelete="SET NULL",
    )

    op.execute(
        """
        UPDATE compras
        SET despesa_id = despeses.id
        FROM despeses
        WHERE despeses.compra_id = compras.id
        """
    )

    op.drop_index(op.f("ix_despeses_compra_id"), table_name="despeses")
    op.drop_constraint("despeses_compra_id_fkey", "despeses", type_="foreignkey")
    op.drop_column("despeses", "compra_id")


def downgrade() -> None:
    op.add_column("despeses", sa.Column("compra_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "despeses_compra_id_fkey", "despeses", "compras",
        ["compra_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index(op.f("ix_despeses_compra_id"), "despeses", ["compra_id"], unique=True)

    op.execute(
        """
        UPDATE despeses
        SET compra_id = compras.id
        FROM compras
        WHERE compras.despesa_id = despeses.id
        """
    )

    op.drop_constraint("fk_compras_despesa_id_despeses", "compras", type_="foreignkey")
    op.drop_index(op.f("ix_compras_despesa_id"), table_name="compras")
    op.drop_column("compras", "despesa_id")

    op.alter_column("compras", "num_albaran", new_column_name="num_factura")
