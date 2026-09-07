"""Afegeix tancament d'exercici (regularitzacio)

Revision ID: 909c657203ee
Revises: 57505813e927
Create Date: 2026-09-06 20:04:25.505313

Tancament d'exercici formal (docs/PLAN_PARIDAD_HOLDED.md B5,
docs/MEJORAS_COMPTABILITAT.md): un únic assentament de regularització,
datat 31/12, que salda contra el compte 129 totes les comptes d'ingrés/
despesa amb saldo no nul de l'any — substitueix la línia sintètica
"129* (provisional)" que `balanc_situacio` fabricava fins ara.

No cal cap assentament d'obertura de l'exercici següent: el balanç de
situació ja calcula els saldos d'actiu/passiu/patrimoni net de forma
ACUMULADA des de l'origen (sense filtrar per `fiscal_year`), no any a any
— arrosseguen sols. Tampoc calen taules noves: "exercici tancat" es
dedueix de si ja existeix un assentament amb source_type
'tancament_exercici' per aquell any (ver routers/comptabilitat/tancament.py).

Sol afegeix un valor nou a l'enum `journal_source_type`, mateix patró que
84f8e4883ad3 (actiu_alta/actiu_amortitzacio).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '909c657203ee'
down_revision: Union[str, None] = '57505813e927'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE journal_source_type ADD VALUE IF NOT EXISTS 'tancament_exercici'")


def downgrade() -> None:
    # No es treu 'tancament_exercici' de journal_source_type: Postgres no
    # permet eliminar valors d'un enum sense recrear el tipus.
    pass
