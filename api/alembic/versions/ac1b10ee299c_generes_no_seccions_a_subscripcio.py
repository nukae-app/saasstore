"""subscripcio: gèneres musicals (Discogs) en lloc de seccions

Revision ID: ac1b10ee299c
Revises: f412d83dc9a8
Create Date: 2026-07-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'ac1b10ee299c'
down_revision: Union[str, None] = 'f412d83dc9a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Mateix tipus (JSON), només canvia què hi guardem (gèneres Discogs en
    # text, no ids de Seccio) i el nom perquè no confongui. `subscripcions_actives`
    # és false i encara no hi ha subscriptors reals: no cal migrar contingut.
    op.alter_column('subscripcions', 'seccions_preferides', new_column_name='generes_preferits')


def downgrade() -> None:
    op.alter_column('subscripcions', 'generes_preferits', new_column_name='seccions_preferides')
