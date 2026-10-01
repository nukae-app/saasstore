"""recarrec_equivalencia_configurable

`configuracio_botiga.recarrec_equivalencia_pct`: % de recàrrec d'equivalència
que es suma al preu de compra (sense IVA) de mercaderia nova per calcular el
cost real, el marge i el PVP suggerit a la recepció. Per defecte 5.

Revision ID: b2c8e5a1d604
Revises: a1b7f4d92e3c
Create Date: 2026-10-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c8e5a1d604'
down_revision: Union[str, None] = 'a1b7f4d92e3c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'configuracio_botiga',
        sa.Column('recarrec_equivalencia_pct', sa.Numeric(precision=5, scale=2), server_default='5', nullable=False),
    )


def downgrade() -> None:
    op.drop_column('configuracio_botiga', 'recarrec_equivalencia_pct')
