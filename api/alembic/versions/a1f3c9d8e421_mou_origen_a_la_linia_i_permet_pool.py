"""mou origen a la linia i permet pool sense solicitud

Revision ID: a1f3c9d8e421
Revises: 833428addbb2
Create Date: 2026-09-03 16:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1f3c9d8e421'
down_revision: Union[str, None] = '833428addbb2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `origen` passa de la sol·licitud a la línia: cal saber-lo abans que
    # existeixi cap sol·licitud (línies encara al pool), i una sol·licitud
    # consolidada pot barrejar línies de diversos orígens.
    op.execute("ALTER TABLE solicitud_compra_items ADD COLUMN origen origen_solicitud")
    op.execute("""
        UPDATE solicitud_compra_items li
        SET origen = sc.origen
        FROM solicitudes_compra sc
        WHERE li.solicitud_id = sc.id
    """)
    op.execute("ALTER TABLE solicitud_compra_items ALTER COLUMN origen SET NOT NULL")
    op.create_index(
        op.f('ix_solicitud_compra_items_origen'), 'solicitud_compra_items', ['origen'], unique=False
    )

    # `solicitud_id` esdevé opcional: una línia viu al pool fins que es
    # consolida explícitament ("Crear sol·licitud") en una sol·licitud
    # numerada.
    op.alter_column(
        'solicitud_compra_items', 'solicitud_id', existing_type=sa.Uuid(), nullable=True,
    )

    op.drop_index('ix_solicitudes_compra_origen', table_name='solicitudes_compra')
    op.drop_column('solicitudes_compra', 'origen')


def downgrade() -> None:
    op.add_column(
        'solicitudes_compra',
        sa.Column('origen', sa.Enum('manual', 'refill_stock', 'peticion_cliente', name='origen_solicitud'), nullable=True),
    )
    op.execute("""
        UPDATE solicitudes_compra sc
        SET origen = sub.origen
        FROM (
            SELECT DISTINCT ON (solicitud_id) solicitud_id, origen
            FROM solicitud_compra_items
            WHERE solicitud_id IS NOT NULL
            ORDER BY solicitud_id, created_at
        ) sub
        WHERE sc.id = sub.solicitud_id
    """)
    op.execute("UPDATE solicitudes_compra SET origen = 'manual' WHERE origen IS NULL")
    op.alter_column('solicitudes_compra', 'origen', existing_type=sa.Enum(
        'manual', 'refill_stock', 'peticion_cliente', name='origen_solicitud',
    ), nullable=False)
    op.create_index(op.f('ix_solicitudes_compra_origen'), 'solicitudes_compra', ['origen'], unique=False)

    # No es pot fer downgrade net de `solicitud_id` a NOT NULL si hi ha
    # línies de pool (solicitud_id NULL) creades amb el nou model — caldria
    # esborrar-les o assignar-les a mà abans de baixar aquesta migració.
    op.alter_column(
        'solicitud_compra_items', 'solicitud_id', existing_type=sa.Uuid(), nullable=False,
    )
    op.drop_index(op.f('ix_solicitud_compra_items_origen'), table_name='solicitud_compra_items')
    op.drop_column('solicitud_compra_items', 'origen')
