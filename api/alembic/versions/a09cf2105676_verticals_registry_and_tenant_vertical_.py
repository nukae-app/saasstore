"""verticals registry and tenant vertical id

Revision ID: a09cf2105676
Revises: 2dcb8b93ff59
Create Date: 2026-08-09 16:00:21.063734

Sustituye `Tenant.vertical` (string libre sin constraint, valores
"vinils"/"floristeria") por una tabla `verticals` real (fuente única de
verdad, hoy duplicada entre el Literal de routers/superadmin.py y un array
hardcodeado en el frontend) y una FK `Tenant.vertical_id`. Slugs nuevos en
inglés ("records"/"floristry"), según la convención de nomenclatura
adoptada (ver docs/ARQUITECTURA_CORE_VERTICAL.md) — se remapean los
tenants existentes en el propio upgrade, no hace falta backfill aparte.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a09cf2105676'
down_revision: Union[str, None] = '2dcb8b93ff59'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

verticals_table = sa.table(
    "verticals",
    sa.column("id", sa.String),
    sa.column("name_ca", sa.String),
    sa.column("name_es", sa.String),
    sa.column("name_en", sa.String),
    sa.column("active", sa.Boolean),
)

tenants_table = sa.table(
    "tenants",
    sa.column("vertical", sa.String),
    sa.column("vertical_id", sa.String),
)


def upgrade() -> None:
    op.create_table(
        "verticals",
        sa.Column("id", sa.String(length=30), nullable=False),
        sa.Column("name_ca", sa.String(length=100), nullable=False),
        sa.Column("name_es", sa.String(length=100), nullable=False),
        sa.Column("name_en", sa.String(length=100), nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.bulk_insert(
        verticals_table,
        [
            {"id": "records", "name_ca": "Discos", "name_es": "Discos", "name_en": "Records", "active": True},
            {"id": "floristry", "name_ca": "Floristeria", "name_es": "Floristería", "name_en": "Florist", "active": True},
        ],
    )

    op.add_column("tenants", sa.Column("vertical_id", sa.String(length=30), nullable=True))
    # Remapeo de los valores antiguos (catalán) a los slugs nuevos (inglés).
    # Cualquier valor que no sea "floristeria" cae en "records" — es el
    # mismo comportamiento por defecto que ya tenía el resto del código
    # (ver antes admin/layout.jsx: `vertical === 'floristeria' ? ... : ...`).
    op.execute(
        tenants_table.update().values(vertical_id="floristry").where(tenants_table.c.vertical == "floristeria")
    )
    op.execute(
        tenants_table.update().values(vertical_id="records").where(tenants_table.c.vertical != "floristeria")
    )
    op.alter_column("tenants", "vertical_id", nullable=False, server_default="records")
    op.create_foreign_key(
        "fk_tenants_vertical_id_verticals", "tenants", "verticals", ["vertical_id"], ["id"],
    )
    op.create_index(op.f("ix_tenants_vertical_id"), "tenants", ["vertical_id"])
    op.drop_column("tenants", "vertical")


def downgrade() -> None:
    op.add_column("tenants", sa.Column("vertical", sa.String(length=30), nullable=True))
    op.execute(
        tenants_table.update().values(vertical="floristeria").where(tenants_table.c.vertical_id == "floristry")
    )
    op.execute(
        tenants_table.update().values(vertical="vinils").where(tenants_table.c.vertical_id != "floristry")
    )
    op.alter_column("tenants", "vertical", nullable=False, server_default="vinils")
    op.drop_index(op.f("ix_tenants_vertical_id"), table_name="tenants")
    op.drop_constraint("fk_tenants_vertical_id_verticals", "tenants", type_="foreignkey")
    op.drop_column("tenants", "vertical_id")
    op.drop_table("verticals")
