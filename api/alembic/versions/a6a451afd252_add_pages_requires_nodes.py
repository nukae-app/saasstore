"""add pages.requires_nodes

Revision ID: a6a451afd252
Revises: f3f9efa93dd9
Create Date: 2026-09-28 00:00:00.000000

Fase 1 de docs/ARQUITECTURA_DISENY_FIGMA.md §3d (nodos protegidos): añade la
columna que faltaba para poder marcar qué tipos de nodo son obligatorios en
una `Page` (p. ej. `checkout_form`/`cart_summary` en el checkout) y que
`publish_page` (routers/pages.py) pueda rechazar la publicación si faltan.
Escrita a mano (columna única, sin autogenerate) — mismo criterio que el
resto de migraciones pequeñas del repo.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a6a451afd252'
down_revision: Union[str, None] = 'f3f9efa93dd9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('pages', sa.Column('requires_nodes', sa.JSON(), server_default='[]', nullable=False))


def downgrade() -> None:
    op.drop_column('pages', 'requires_nodes')
