"""backfill etiqueta_slug al bloc curator_selection existent

Sense canvi d'esquema. `curator_selection` passa de EmptyProps a tenir un
`etiqueta_slug` configurable (ver api/app/blocks/registry.py), igual que ja
tenia `carousel` — abans, [locale]/page.jsx resolia sempre la mateixa
etiqueta "recomanat" en dur. Sense aquest backfill, els `home_blocks`
`curator_selection` que ja existeixen (`props={}`) es quedarien sense cap
etiqueta_slug i la secció desapareixeria del home en desplegar (el nou
resolveBlockProps depèn de `block.props.etiqueta_slug`).

Revision ID: 9f3a7c1d5e2b
Revises: 7db26e104bf8
Create Date: 2026-08-29 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = '9f3a7c1d5e2b'
down_revision: Union[str, None] = '7db26e104bf8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            """
            UPDATE home_blocks
            SET props = (props::jsonb || '{"etiqueta_slug": "recomanat"}'::jsonb)::json
            WHERE block_type = 'curator_selection'
              AND NOT (props::jsonb ? 'etiqueta_slug')
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            """
            UPDATE home_blocks
            SET props = (props::jsonb - 'etiqueta_slug')::json
            WHERE block_type = 'curator_selection'
            """
        )
    )
