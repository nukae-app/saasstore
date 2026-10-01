"""add figma_import_jobs.figma_node_id

Revision ID: f60f71b05e91
Revises: a6a451afd252
Create Date: 2026-09-28 00:00:00.000000

Fase 4 de docs/ARQUITECTURA_DISENY_FIGMA.md §4 (import estructural): la
columna que faltaba para recordar QUÉ frame concreto del fichero se importó
(`FigmaImportJob` se creó en Fase 1 sin ella porque todavía no existía el
concepto de "elegir un frame" — solo se sabía que haría falta encolar
importaciones). Escrita a mano (columna única) — mismo criterio que
`a6a451afd252`.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f60f71b05e91'
down_revision: Union[str, None] = 'a6a451afd252'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('figma_import_jobs', sa.Column('figma_node_id', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('figma_import_jobs', 'figma_node_id')
