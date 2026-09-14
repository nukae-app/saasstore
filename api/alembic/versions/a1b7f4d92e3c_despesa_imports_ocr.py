"""despesa_imports_ocr

Cua de revisió per donar d'alta Despeses a partir d'un PDF de factura
(extracció amb Claude, veure services/despesa_extraction.py i
routers/comptabilitat/despeses_imports.py): taula `despesa_imports` +
`despeses.source_document_url` (justificant original, opcional).

Revision ID: a1b7f4d92e3c
Revises: 7a3aa78f0c30
Create Date: 2026-09-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b7f4d92e3c'
down_revision: Union[str, None] = '7a3aa78f0c30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('despeses', sa.Column('source_document_url', sa.String(length=500), nullable=True))

    op.create_table(
        'despesa_imports',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('file_url', sa.String(length=500), nullable=False),
        sa.Column('original_filename', sa.String(length=300), nullable=False),
        sa.Column(
            'status',
            sa.Enum('pendent', 'processat', 'error', 'confirmat', 'descartat', name='despesa_import_status'),
            server_default='pendent', nullable=False,
        ),
        sa.Column('extracted_data', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('despesa_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['despesa_id'], ['despeses.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_despesa_imports_status'), 'despesa_imports', ['status'], unique=False)
    op.create_index(op.f('ix_despesa_imports_despesa_id'), 'despesa_imports', ['despesa_id'], unique=False)
    op.create_index(op.f('ix_despesa_imports_tenant_id'), 'despesa_imports', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_despesa_imports_tenant_id'), table_name='despesa_imports')
    op.drop_index(op.f('ix_despesa_imports_despesa_id'), table_name='despesa_imports')
    op.drop_index(op.f('ix_despesa_imports_status'), table_name='despesa_imports')
    op.drop_table('despesa_imports')
    op.execute("DROP TYPE IF EXISTS despesa_import_status")

    op.drop_column('despeses', 'source_document_url')
