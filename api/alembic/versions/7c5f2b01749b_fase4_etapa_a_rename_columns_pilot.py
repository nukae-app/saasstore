"""fase 4 etapa a: rename columns to english (pilot: etiquetes, seccions, tipus_iva)

Revision ID: 7c5f2b01749b
Revises: 8ac01b667f42
Create Date: 2026-08-25 00:00:00.000000

Fase 4 Etapa A (ver docs/ARQUITECTURA_CORE_VERTICAL.md §6/§14): rename
DB-only de columnas a inglés vía `ALTER TABLE ... RENAME COLUMN`, sin tocar
el atributo Python del modelo (mapped_column("nombre_ingles")), ni
schemas.py, ni routers, ni frontend — el contrato JSON de la API no
cambia. Piloto en 3 tablas pequeñas y simétricas antes de extender al
resto: `etiquetes`, `seccions`, `tipus_iva`.

IMPORTANTE: `alembic revision --autogenerate` habría detectado esto como
DROP + ADD (pérdida de datos), porque desde el punto de vista de SQLAlchemy
solo cambia el nombre de columna mapeado, no hay forma de que autogenerate
infiera que es un rename y no una columna nueva. Esta migración está escrita
a mano con `alter_column(new_column_name=...)`, que sí preserva los datos.
"""
from typing import Sequence, Union

from alembic import op


revision: str = '7c5f2b01749b'
down_revision: Union[str, None] = '8ac01b667f42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('etiquetes', 'nom_ca', new_column_name='name_ca')
    op.alter_column('etiquetes', 'nom_es', new_column_name='name_es')
    op.alter_column('etiquetes', 'activa', new_column_name='active')
    op.alter_column('etiquetes', 'posicio', new_column_name='position')

    op.alter_column('seccions', 'nom_ca', new_column_name='name_ca')
    op.alter_column('seccions', 'nom_es', new_column_name='name_es')
    op.alter_column('seccions', 'activa', new_column_name='active')
    op.alter_column('seccions', 'posicio', new_column_name='position')

    op.alter_column('tipus_iva', 'nom', new_column_name='name')
    op.alter_column('tipus_iva', 'actiu', new_column_name='active')


def downgrade() -> None:
    op.alter_column('tipus_iva', 'name', new_column_name='nom')
    op.alter_column('tipus_iva', 'active', new_column_name='actiu')

    op.alter_column('seccions', 'position', new_column_name='posicio')
    op.alter_column('seccions', 'active', new_column_name='activa')
    op.alter_column('seccions', 'name_es', new_column_name='nom_es')
    op.alter_column('seccions', 'name_ca', new_column_name='nom_ca')

    op.alter_column('etiquetes', 'position', new_column_name='posicio')
    op.alter_column('etiquetes', 'active', new_column_name='activa')
    op.alter_column('etiquetes', 'name_es', new_column_name='nom_es')
    op.alter_column('etiquetes', 'name_ca', new_column_name='nom_ca')
