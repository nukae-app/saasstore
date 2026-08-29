"""verticals: catalog_provider, product_archetype, default_features + seed

Revision ID: 0a8e9cde93d3
Revises: ab367beb5812
Create Date: 2026-08-29 00:00:00.000000

Amplía el registro de verticales (docs/ARQUITECTURA_CORE_VERTICAL.md §20)
con tres columnas nuevas, todas nullable/con default, sin tocar ningún dato
existente salvo rellenar estas columnas para `records`/`floristry`:

- `catalog_provider`: qué proveedor de búsqueda de referencias en compras
  usa esta vertical (§19.1) — null si no tiene ninguno.
- `product_archetype`: a qué arquetipo de extensión de Product/StockItem
  pertenece (§18) — "record"/"floristry" ya tienen tabla real; el resto son
  arquetipos planificados, sin tabla propia todavía.
- `default_features`: qué `tenant_features` se sembrarían por defecto al
  dar de alta un tenant de esta vertical (no aplicado todavía en
  `POST /superadmin/tenants`, solo almacenado).

De paso, siembra el resto de verticales previstas en la conversación con el
usuario (discos, café, flores, vino, queso, cerveza artesana, ropa, libros,
juguetes, cosmética, plantas, alimentación) — como REGISTRO únicamente
(`active=False` salvo records/floristry, que ya tenían tenants reales): no
se crea ningún tenant nuevo, y ninguna de las 10 verticales nuevas tiene
todavía tabla de extensión de catálogo (por eso `product_archetype` en
estas es un arquetipo "planeado", no implementado — ver
app/verticals_registry.py).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0a8e9cde93d3'
down_revision: Union[str, None] = 'ab367beb5812'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

verticals_table = sa.table(
    "verticals",
    sa.column("id", sa.String),
    sa.column("name_ca", sa.String),
    sa.column("name_es", sa.String),
    sa.column("name_en", sa.String),
    sa.column("active", sa.Boolean),
    sa.column("catalog_provider", sa.String),
    sa.column("product_archetype", sa.String),
    sa.column("default_features", sa.JSON),
)

NEW_VERTICALS = [
    {
        "id": "coffee", "name_ca": "Cafè", "name_es": "Café", "name_en": "Coffee",
        "active": False, "catalog_provider": None, "product_archetype": "consumable",
        "default_features": {},
    },
    {
        "id": "wine", "name_ca": "Vi", "name_es": "Vino", "name_en": "Wine",
        "active": False, "catalog_provider": None, "product_archetype": "consumable",
        "default_features": {},
    },
    {
        "id": "cheese", "name_ca": "Formatge", "name_es": "Queso", "name_en": "Cheese",
        "active": False, "catalog_provider": None, "product_archetype": "consumable",
        "default_features": {},
    },
    {
        "id": "craft_beer", "name_ca": "Cervesa artesana", "name_es": "Cerveza artesana", "name_en": "Craft beer",
        "active": False, "catalog_provider": None, "product_archetype": "consumable",
        "default_features": {},
    },
    {
        "id": "food", "name_ca": "Alimentació", "name_es": "Alimentación", "name_en": "Food",
        "active": False, "catalog_provider": None, "product_archetype": "consumable",
        "default_features": {},
    },
    {
        "id": "plants", "name_ca": "Plantes", "name_es": "Plantas", "name_en": "Plants",
        "active": False, "catalog_provider": None, "product_archetype": "botanical",
        "default_features": {},
    },
    {
        "id": "toys", "name_ca": "Joguines", "name_es": "Juguetes", "name_en": "Toys",
        "active": False, "catalog_provider": None, "product_archetype": "retail_simple",
        "default_features": {},
    },
    {
        "id": "cosmetics", "name_ca": "Cosmètica", "name_es": "Cosmética", "name_en": "Cosmetics",
        "active": False, "catalog_provider": None, "product_archetype": "retail_simple",
        "default_features": {},
    },
    {
        "id": "clothing", "name_ca": "Roba", "name_es": "Ropa", "name_en": "Clothing",
        "active": False, "catalog_provider": None, "product_archetype": "apparel_variant",
        "default_features": {},
    },
    {
        "id": "books", "name_ca": "Llibres", "name_es": "Libros", "name_en": "Books",
        "active": False, "catalog_provider": None, "product_archetype": "media_catalog",
        "default_features": {},
    },
]


def upgrade() -> None:
    op.add_column("verticals", sa.Column("catalog_provider", sa.String(length=30), nullable=True))
    op.add_column("verticals", sa.Column("product_archetype", sa.String(length=30), nullable=True))
    op.add_column(
        "verticals",
        sa.Column("default_features", sa.JSON(), nullable=False, server_default="{}"),
    )

    op.execute(
        verticals_table.update()
        .values(catalog_provider="discogs", product_archetype="record",
                default_features={
                    "discogs_sync": True, "subscriptions": True, "catalog_browse_mode": True,
                    "catalog_format_filter": True, "catalog_genre_filter": True,
                })
        .where(verticals_table.c.id == "records")
    )
    op.execute(
        verticals_table.update()
        .values(product_archetype="floristry", default_features={})
        .where(verticals_table.c.id == "floristry")
    )
    op.bulk_insert(verticals_table, NEW_VERTICALS)


def downgrade() -> None:
    op.execute(
        verticals_table.delete().where(
            verticals_table.c.id.in_([v["id"] for v in NEW_VERTICALS])
        )
    )
    op.drop_column("verticals", "default_features")
    op.drop_column("verticals", "product_archetype")
    op.drop_column("verticals", "catalog_provider")
