"""add_pagines_and_posts_pagines

Revision ID: 02b9ed04b355
Revises: 991782a64e63
Create Date: 2026-06-12 09:12:15.997260

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '02b9ed04b355'
down_revision: Union[str, None] = '991782a64e63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'pagines',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('nom', sa.String(length=200), nullable=False),
        sa.Column('tipus', sa.String(length=40), nullable=False, server_default='llista-posts'),
        sa.Column('posicio', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('visible_menu', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('contingut', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_pagines_slug'), 'pagines', ['slug'], unique=True)

    op.create_table(
        'posts_pagines',
        sa.Column('post_id', sa.UUID(), nullable=False),
        sa.Column('pagina_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['pagina_id'], ['pagines.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('post_id', 'pagina_id'),
    )


def downgrade() -> None:
    op.drop_table('posts_pagines')
    op.drop_index(op.f('ix_pagines_slug'), table_name='pagines')
    op.drop_table('pagines')
