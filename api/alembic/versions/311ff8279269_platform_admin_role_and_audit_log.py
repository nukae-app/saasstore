"""platform_admin_role_and_audit_log

Revision ID: 311ff8279269
Revises: eb3f17c1d293
Create Date: 2026-08-26 21:31:53.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '311ff8279269'
down_revision: Union[str, None] = 'eb3f17c1d293'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Escrita a mano en vez de autogenerate: es una adición pura (columna nueva +
# tabla nueva), no un rename, así que autogenerate no habría propuesto nada
# destructivo aquí — pero se hizo a mano igualmente para no depender de una
# conexión contra el Postgres real de dev en el momento de escribir el
# archivo (ver docs/ARQUITECTURA_CORE_VERTICAL.md: autogenerate solo hace
# falta cuestionarlo en renames, para adiciones puras es intercambiable).
platform_admin_role_enum = sa.Enum('owner', 'support', name='platform_admin_role')


def upgrade() -> None:
    platform_admin_role_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'platform_admins',
        sa.Column('role', platform_admin_role_enum, nullable=False, server_default='owner'),
    )

    op.create_table(
        'platform_admin_audit_logs',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('platform_admin_id', sa.Uuid(), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('target_tenant_id', sa.Uuid(), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['platform_admin_id'], ['platform_admins.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['target_tenant_id'], ['tenants.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_platform_admin_audit_logs_platform_admin_id'),
        'platform_admin_audit_logs', ['platform_admin_id'], unique=False,
    )
    op.create_index(
        op.f('ix_platform_admin_audit_logs_action'), 'platform_admin_audit_logs', ['action'], unique=False,
    )
    op.create_index(
        op.f('ix_platform_admin_audit_logs_target_tenant_id'),
        'platform_admin_audit_logs', ['target_tenant_id'], unique=False,
    )
    op.create_index(
        op.f('ix_platform_admin_audit_logs_created_at'), 'platform_admin_audit_logs', ['created_at'], unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_platform_admin_audit_logs_created_at'), table_name='platform_admin_audit_logs')
    op.drop_index(op.f('ix_platform_admin_audit_logs_target_tenant_id'), table_name='platform_admin_audit_logs')
    op.drop_index(op.f('ix_platform_admin_audit_logs_action'), table_name='platform_admin_audit_logs')
    op.drop_index(op.f('ix_platform_admin_audit_logs_platform_admin_id'), table_name='platform_admin_audit_logs')
    op.drop_table('platform_admin_audit_logs')

    op.drop_column('platform_admins', 'role')
    platform_admin_role_enum.drop(op.get_bind(), checkfirst=True)
