"""backfill catalog feature flags per a tenants records existents

Sense canvi d'esquema — `tenant_features` ja existeix. Abans d'aquesta
migració, el mode "Remena" i els filtres de format/gènere a /cataleg
depenien únicament de `Tenant.vertical_id == 'records'` (ver
web/app/[locale]/cataleg/page.jsx). Ara depenen també d'una fila a
`tenant_features` (ConfiguracioBotiga.catalog_browse_mode/etc., patró
passthrough igual que discogs_habilitat) — sense aquest backfill, els
tenants "records" que ja existeixen perdrien aquestes tres funcions de cop
en desplegar, perquè no tindrien encara cap fila i el default és False.

Revision ID: 230eb4cfc0b5
Revises: af9e10038ae7
Create Date: 2026-08-28 07:12:09.610421

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = '230eb4cfc0b5'
down_revision: Union[str, None] = 'af9e10038ae7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FEATURE_KEYS = ("catalog_browse_mode", "catalog_format_filter", "catalog_genre_filter")


def upgrade() -> None:
    conn = op.get_bind()
    for key in FEATURE_KEYS:
        conn.execute(
            text(
                """
                INSERT INTO tenant_features (tenant_id, feature_key, enabled)
                SELECT id, :key, true FROM tenants WHERE vertical_id = 'records'
                ON CONFLICT (tenant_id, feature_key) DO NOTHING
                """
            ),
            {"key": key},
        )


def downgrade() -> None:
    conn = op.get_bind()
    for key in FEATURE_KEYS:
        conn.execute(text("DELETE FROM tenant_features WHERE feature_key = :key"), {"key": key})
