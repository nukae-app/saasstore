"""ticket_id_ventas_externas

Revision ID: c7e4b1a9d3f8
Revises: 9a1c5e7f2b6d
Create Date: 2026-08-05 10:00:00.000000

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = 'c7e4b1a9d3f8'
down_revision: Union[str, None] = '9a1c5e7f2b6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('ventas_externas', sa.Column('ticket_id', sa.Uuid(), nullable=True))

    # Backfill: les línies creades juntes (venda individual o cistella)
    # comparteixen exactament el mateix `fecha` (és el mateix valor enviat
    # pel front en una sola petició, no server_default independent per
    # fila), així que agrupar per fecha reconstrueix els tiquets històrics
    # en comptes d'assignar un ticket_id nou i solt a cada fila.
    conn = op.get_bind()
    fechas = conn.execute(text("SELECT DISTINCT fecha FROM ventas_externas")).fetchall()
    for (fecha,) in fechas:
        conn.execute(
            text("UPDATE ventas_externas SET ticket_id = :tid WHERE fecha = :fecha"),
            {"tid": str(uuid.uuid4()), "fecha": fecha},
        )

    op.alter_column('ventas_externas', 'ticket_id', nullable=False)
    op.create_index('ix_ventas_externas_ticket_id', 'ventas_externas', ['ticket_id'])


def downgrade() -> None:
    op.drop_index('ix_ventas_externas_ticket_id', table_name='ventas_externas')
    op.drop_column('ventas_externas', 'ticket_id')
