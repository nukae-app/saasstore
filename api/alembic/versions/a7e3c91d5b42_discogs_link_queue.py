"""Cola Vincular de Discogs: release_records.discogs_link_checked_at / discogs_link_skipped

Revision ID: a7e3c91d5b42
Revises: c3d9f6b2e715
"""
import sqlalchemy as sa
from alembic import op

revision = "a7e3c91d5b42"
down_revision = "c3d9f6b2e715"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("release_records", sa.Column("discogs_link_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "release_records",
        sa.Column("discogs_link_skipped", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("release_records", "discogs_link_skipped")
    op.drop_column("release_records", "discogs_link_checked_at")
