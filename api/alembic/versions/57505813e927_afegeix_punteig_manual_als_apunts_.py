"""Afegeix punteig manual als apunts comptables

Revision ID: 57505813e927
Revises: d552871ac0ba
Create Date: 2026-09-06 19:30:50.840473

Punteig manual d'apunts (docs/MEJORAS_COMPTABILITAT.md, docs/PLAN_PARIDAD_HOLDED.md
B3): flag booleà `punteat` per marcar una línia com a revisada des de la
vista del llibre major, amb `punteat_at`/`punteat_by_id` per auditoria de
qui i quan. És una simple marca de revisió manual, no una conciliació amb
matching automàtic com `moviments_bancaris.status` — per això booleà i no
un enum tri-state.

Nota: l'autogenerate també va detectar ~60 diffs d'índexs sense relació amb
aquest canvi (mateix lastre de "Fase 4 Etapa B" ja documentat a la migració
767d1dd7032d — noms d'índex que encara no s'han renomenat de
castellà/català a anglès). S'han descartat d'aquesta migració a mà,
deixant només els canvis reals sobre `apunts`.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '57505813e927'
down_revision: Union[str, None] = 'd552871ac0ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('apunts', sa.Column('punteat', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('apunts', sa.Column('punteat_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('apunts', sa.Column('punteat_by_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_apunts_punteat'), 'apunts', ['punteat'], unique=False)
    op.create_index(op.f('ix_apunts_punteat_by_id'), 'apunts', ['punteat_by_id'], unique=False)
    op.create_foreign_key(None, 'apunts', 'users', ['punteat_by_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint(None, 'apunts', type_='foreignkey')
    op.drop_index(op.f('ix_apunts_punteat_by_id'), table_name='apunts')
    op.drop_index(op.f('ix_apunts_punteat'), table_name='apunts')
    op.drop_column('apunts', 'punteat_by_id')
    op.drop_column('apunts', 'punteat_at')
    op.drop_column('apunts', 'punteat')
