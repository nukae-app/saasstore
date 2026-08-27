"""extract record product and stock detail from release and item

Revision ID: 0c06c9e78a72
Revises: a09cf2105676
Create Date: 2026-08-09 16:31:04.685419

Fase 2 (ver docs/ARQUITECTURA_CORE_VERTICAL.md): extrae de `releases`/`items`
los campos propios del vertical "records" (discos) a dos tablas de
extensión 1:1 — `release_records` y `record_stock_details` — pareja
simétrica de `release_floristeria`, que ya existía. Antes esos campos
vivían directamente en las tablas core, lo que hacía que "core" fuera en
realidad "discos por defecto" con floristeria como añadido.

Backfill incondicional: TODAS las filas de `releases`/`items` (de
cualquier vertical) obtienen su fila de extensión, preservando exactamente
los valores que ya tenían — no hay pérdida de datos, solo relocalización.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0c06c9e78a72'
down_revision: Union[str, None] = 'a09cf2105676'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Tabla nueva: release_records (RecordProduct) ---
    op.create_table(
        'release_records',
        sa.Column('release_id', sa.Uuid(), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('artista', sa.String(length=300), nullable=True),
        sa.Column('sello', sa.String(length=500), nullable=True),
        sa.Column('referencia', sa.String(length=200), nullable=True),
        sa.Column('formato', sa.String(length=120), nullable=True),
        sa.Column('anio', sa.Integer(), nullable=True),
        sa.Column('genero', sa.String(length=200), nullable=True),
        sa.Column('pais', sa.String(length=100), nullable=True),
        sa.Column('estilos', sa.String(length=300), nullable=True),
        sa.Column('tracklist', sa.JSON(), nullable=True),
        sa.Column('credits', sa.JSON(), nullable=True),
        sa.Column('discogs_release_id', sa.BigInteger(), nullable=True),
        sa.Column('spotify_album_id', sa.String(length=50), nullable=True),
        sa.Column('esta_sonant', sa.Boolean(), server_default='false', nullable=False),
        sa.ForeignKeyConstraint(['release_id'], ['releases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('release_id'),
    )
    op.create_index(op.f('ix_release_records_tenant_id'), 'release_records', ['tenant_id'])
    op.create_index(op.f('ix_release_records_artista'), 'release_records', ['artista'])
    op.create_index(op.f('ix_release_records_formato'), 'release_records', ['formato'])
    op.create_index(op.f('ix_release_records_genero'), 'release_records', ['genero'])
    op.create_index(op.f('ix_release_records_discogs_release_id'), 'release_records', ['discogs_release_id'])
    op.create_index(op.f('ix_release_records_esta_sonant'), 'release_records', ['esta_sonant'])

    # --- Tabla nueva: record_stock_details (RecordStockDetail) ---
    op.create_table(
        'record_stock_details',
        sa.Column('item_id', sa.Uuid(), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('codi_discogs', sa.BigInteger(), nullable=True),
        sa.Column('estado_disco', sa.String(length=60), nullable=True),
        sa.Column('estado_funda', sa.String(length=60), nullable=True),
        sa.ForeignKeyConstraint(['item_id'], ['items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('item_id'),
        sa.UniqueConstraint('tenant_id', 'codi_discogs'),
    )
    op.create_index(op.f('ix_record_stock_details_tenant_id'), 'record_stock_details', ['tenant_id'])

    # --- Backfill: copia 1:1 desde releases/items, incondicional ---
    op.execute("""
        INSERT INTO release_records (
            release_id, tenant_id, artista, sello, referencia, formato, anio, genero,
            pais, estilos, tracklist, credits, discogs_release_id, spotify_album_id, esta_sonant
        )
        SELECT
            id, tenant_id, artista, sello, referencia, formato, anio, genero,
            pais, estilos, tracklist, credits, discogs_release_id, spotify_album_id, esta_sonant
        FROM releases
    """)
    op.execute("""
        INSERT INTO record_stock_details (item_id, tenant_id, codi_discogs, estado_disco, estado_funda)
        SELECT id, tenant_id, codi_discogs, estado_disco, estado_funda
        FROM items
    """)

    # --- Columnas antiguas fuera de releases/items ---
    # items.codi_discogs lleva un UNIQUE(tenant_id, codi_discogs) sin nombre
    # explícito (autogenerado por Postgres) — DROP COLUMN normal falla por
    # esa dependencia; CASCADE se lleva también el constraint, ya recreado
    # arriba en record_stock_details.
    op.execute("ALTER TABLE items DROP COLUMN codi_discogs CASCADE")
    op.drop_column('items', 'estado_disco')
    op.drop_column('items', 'estado_funda')

    op.drop_column('releases', 'artista')
    op.drop_column('releases', 'sello')
    op.drop_column('releases', 'referencia')
    op.drop_column('releases', 'formato')
    op.drop_column('releases', 'anio')
    op.drop_column('releases', 'genero')
    op.drop_column('releases', 'pais')
    op.drop_column('releases', 'estilos')
    op.drop_column('releases', 'tracklist')
    op.drop_column('releases', 'credits')
    op.drop_column('releases', 'discogs_release_id')
    op.drop_column('releases', 'spotify_album_id')
    op.drop_column('releases', 'esta_sonant')


def downgrade() -> None:
    op.add_column('releases', sa.Column('esta_sonant', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('releases', sa.Column('spotify_album_id', sa.String(length=50), nullable=True))
    op.add_column('releases', sa.Column('discogs_release_id', sa.BigInteger(), nullable=True))
    op.add_column('releases', sa.Column('credits', sa.JSON(), nullable=True))
    op.add_column('releases', sa.Column('tracklist', sa.JSON(), nullable=True))
    op.add_column('releases', sa.Column('estilos', sa.String(length=300), nullable=True))
    op.add_column('releases', sa.Column('pais', sa.String(length=100), nullable=True))
    op.add_column('releases', sa.Column('genero', sa.String(length=200), nullable=True))
    op.add_column('releases', sa.Column('anio', sa.Integer(), nullable=True))
    op.add_column('releases', sa.Column('formato', sa.String(length=120), nullable=True))
    op.add_column('releases', sa.Column('referencia', sa.String(length=200), nullable=True))
    op.add_column('releases', sa.Column('sello', sa.String(length=500), nullable=True))
    # `artista` era NOT NULL originalmente; se restaura con '' como relleno
    # temporal para no bloquear el downgrade — no hay forma de recuperar un
    # valor "correcto" con certeza si algo se creó ya sin extensión record.
    op.add_column('releases', sa.Column('artista', sa.String(length=300), server_default='', nullable=False))

    op.add_column('items', sa.Column('estado_funda', sa.String(length=60), nullable=True))
    op.add_column('items', sa.Column('estado_disco', sa.String(length=60), nullable=True))
    op.add_column('items', sa.Column('codi_discogs', sa.BigInteger(), nullable=True))

    op.execute("""
        UPDATE releases SET
            artista = COALESCE(release_records.artista, ''), sello = release_records.sello,
            referencia = release_records.referencia, formato = release_records.formato,
            anio = release_records.anio, genero = release_records.genero, pais = release_records.pais,
            estilos = release_records.estilos, tracklist = release_records.tracklist,
            credits = release_records.credits, discogs_release_id = release_records.discogs_release_id,
            spotify_album_id = release_records.spotify_album_id, esta_sonant = release_records.esta_sonant
        FROM release_records
        WHERE release_records.release_id = releases.id
    """)
    op.execute("""
        UPDATE items SET
            codi_discogs = record_stock_details.codi_discogs, estado_disco = record_stock_details.estado_disco,
            estado_funda = record_stock_details.estado_funda
        FROM record_stock_details
        WHERE record_stock_details.item_id = items.id
    """)

    op.create_index(op.f('ix_releases_artista'), 'releases', ['artista'])
    op.create_index(op.f('ix_releases_formato'), 'releases', ['formato'])
    op.create_index(op.f('ix_releases_genero'), 'releases', ['genero'])
    op.create_index(op.f('ix_releases_discogs_release_id'), 'releases', ['discogs_release_id'])
    op.create_index(op.f('ix_releases_esta_sonant'), 'releases', ['esta_sonant'])
    op.create_unique_constraint(None, 'items', ['tenant_id', 'codi_discogs'])

    op.drop_table('record_stock_details')
    op.drop_table('release_records')
