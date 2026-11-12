"""Data del consentiment de newsletter (users.consent_newsletter_at)

Revision ID: a3c9d51e7f02
Revises: e7a1c4d9b205
Create Date: 2026-11-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3c9d51e7f02'
down_revision: Union[str, None] = 'e7a1c4d9b205'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('consent_newsletter_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'consent_newsletter_at')
