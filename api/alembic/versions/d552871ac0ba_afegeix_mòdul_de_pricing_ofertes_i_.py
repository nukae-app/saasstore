"""Afegeix mòdul de pricing: ofertes i cupons

Revision ID: d552871ac0ba
Revises: a1f3c9d8e421
Create Date: 2026-09-04 08:06:03.773678

Nota: l'autogenerate va detectar també desenes de renombraments d'índexs
(espanyol -> anglès) i un canvi al server_default de `configuracio_botiga.id`
que ja existien com a deriva entre la BD de dev i `models.py`, sense relació
amb aquest mòdul — s'han retirat d'aquesta migració a mà; és deute tècnic
previ, no s'ha de barrejar aquí.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd552871ac0ba'
down_revision: Union[str, None] = 'a1f3c9d8e421'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('offers',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('discount_type', sa.Enum('percentage', 'fixed_amount', 'fixed_price', name='discount_type'), nullable=False),
    sa.Column('discount_value', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('starts_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('priority', sa.Integer(), server_default='0', nullable=False),
    sa.Column('criteria', sa.JSON(), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_offers_active'), 'offers', ['active'], unique=False)
    op.create_index(op.f('ix_offers_tenant_id'), 'offers', ['tenant_id'], unique=False)

    op.create_table('coupons',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('discount_type', sa.Enum('percentage', 'fixed_amount', 'fixed_price', name='discount_type'), nullable=False),
    sa.Column('discount_value', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('starts_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('max_uses', sa.Integer(), nullable=True),
    sa.Column('max_uses_per_user', sa.Integer(), nullable=True),
    sa.Column('min_order_amount', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('combinable_with_offers', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('restrict_to_offer_id', sa.Uuid(), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['restrict_to_offer_id'], ['offers.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'code')
    )
    op.create_index(op.f('ix_coupons_active'), 'coupons', ['active'], unique=False)
    op.create_index(op.f('ix_coupons_code'), 'coupons', ['code'], unique=False)
    op.create_index(op.f('ix_coupons_tenant_id'), 'coupons', ['tenant_id'], unique=False)

    op.create_table('coupon_redemptions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('coupon_id', sa.Uuid(), nullable=False),
    sa.Column('order_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=True),
    sa.Column('discount_amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['coupon_id'], ['coupons.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_coupon_redemptions_coupon_id'), 'coupon_redemptions', ['coupon_id'], unique=False)
    op.create_index(op.f('ix_coupon_redemptions_order_id'), 'coupon_redemptions', ['order_id'], unique=True)
    op.create_index(op.f('ix_coupon_redemptions_tenant_id'), 'coupon_redemptions', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_coupon_redemptions_user_id'), 'coupon_redemptions', ['user_id'], unique=False)

    op.create_table('offer_items',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('offer_id', sa.Uuid(), nullable=False),
    sa.Column('item_id', sa.Uuid(), nullable=False),
    sa.Column('mode', sa.Enum('include', 'exclude', name='offer_item_mode'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['item_id'], ['items.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['offer_id'], ['offers.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('offer_id', 'item_id')
    )
    op.create_index(op.f('ix_offer_items_item_id'), 'offer_items', ['item_id'], unique=False)
    op.create_index(op.f('ix_offer_items_offer_id'), 'offer_items', ['offer_id'], unique=False)
    op.create_index(op.f('ix_offer_items_tenant_id'), 'offer_items', ['tenant_id'], unique=False)

    op.add_column('items', sa.Column('list_price', sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column('items', sa.Column('active_offer_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_items_active_offer_id'), 'items', ['active_offer_id'], unique=False)
    op.create_foreign_key('fk_items_active_offer_id', 'items', 'offers', ['active_offer_id'], ['id'], ondelete='SET NULL')

    op.add_column('orders', sa.Column('coupon_code', sa.String(length=40), nullable=True))
    op.add_column('orders', sa.Column('coupon_discount', sa.Numeric(precision=10, scale=2), nullable=True))


def downgrade() -> None:
    op.drop_column('orders', 'coupon_discount')
    op.drop_column('orders', 'coupon_code')

    op.drop_constraint('fk_items_active_offer_id', 'items', type_='foreignkey')
    op.drop_index(op.f('ix_items_active_offer_id'), table_name='items')
    op.drop_column('items', 'active_offer_id')
    op.drop_column('items', 'list_price')

    op.drop_index(op.f('ix_offer_items_tenant_id'), table_name='offer_items')
    op.drop_index(op.f('ix_offer_items_offer_id'), table_name='offer_items')
    op.drop_index(op.f('ix_offer_items_item_id'), table_name='offer_items')
    op.drop_table('offer_items')

    op.drop_index(op.f('ix_coupon_redemptions_user_id'), table_name='coupon_redemptions')
    op.drop_index(op.f('ix_coupon_redemptions_tenant_id'), table_name='coupon_redemptions')
    op.drop_index(op.f('ix_coupon_redemptions_order_id'), table_name='coupon_redemptions')
    op.drop_index(op.f('ix_coupon_redemptions_coupon_id'), table_name='coupon_redemptions')
    op.drop_table('coupon_redemptions')

    op.drop_index(op.f('ix_coupons_tenant_id'), table_name='coupons')
    op.drop_index(op.f('ix_coupons_code'), table_name='coupons')
    op.drop_index(op.f('ix_coupons_active'), table_name='coupons')
    op.drop_table('coupons')

    op.drop_index(op.f('ix_offers_tenant_id'), table_name='offers')
    op.drop_index(op.f('ix_offers_active'), table_name='offers')
    op.drop_table('offers')
