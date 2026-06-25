"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-16

This migration creates the full initial schema for the marketplace.
Generated to match app/models/models.py exactly.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─── user ──────────────────────────────────────────────────────────────
    op.create_table(
        'user',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('role', sa.Enum('buyer', 'seller', 'support', 'moderator', 'superadmin', name='userrole'), nullable=False, server_default='buyer'),
        sa.Column('referral_code', sa.String(32), nullable=True),
        sa.Column('balance', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('bonus_balance', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('promo_balance', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('loyalty_tier_id', sa.Integer(), nullable=True),
        sa.Column('qualifying_spend', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('tier_since', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_qualifying_order_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('is_staff', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('permissions', sa.Text(), nullable=True),
        sa.Column('email_verified', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('phone_verified', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('totp_secret', sa.String(64), nullable=True),
        sa.Column('is_2fa_enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('totp_backup_codes', sa.Text(), nullable=True),
        sa.Column('email_notifications', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('referred_by_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('referral_code'),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_user_email', 'user', ['email'])
    op.create_index('ix_user_referral_code', 'user', ['referral_code'])
    op.create_index('ix_user_role', 'user', ['role'])
    op.create_index('ix_user_is_active', 'user', ['is_active'])

    # ─── shop ──────────────────────────────────────────────────────────────
    op.create_table(
        'shop',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('owner_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('logo_url', sa.String(512), nullable=True),
        sa.Column('banner_url', sa.String(512), nullable=True),
        sa.Column('accent_color', sa.String(9), nullable=False, server_default='#f97316'),
        sa.Column('tagline', sa.String(255), nullable=True),
        sa.Column('contact_email', sa.String(255), nullable=True),
        sa.Column('contact_phone', sa.String(20), nullable=True),
        sa.Column('commission_percent', sa.Numeric(5, 2), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('status', sa.Enum('pending', 'active', 'rejected', 'suspended', name='shopstatus'), nullable=False, server_default='pending'),
        sa.Column('moderation_reason', sa.Text(), nullable=True),
        sa.Column('business_hours', sa.String(255), nullable=True),
        sa.Column('rating', sa.Numeric(3, 2), nullable=False, server_default='0.00'),
        sa.Column('reviews_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('ad_balance', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('total_sales', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('owner_id'),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_shop_is_active', 'shop', ['is_active'])
    op.create_index('ix_shop_status', 'shop', ['status'])

    # ─── category ──────────────────────────────────────────────────────────
    op.create_table(
        'category',
        sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column('parent_id', sa.Integer(), sa.ForeignKey('category.id'), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(255), nullable=False),
        sa.Column('image', sa.String(512), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.UniqueConstraint('slug'),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_category_slug', 'category', ['slug'])

    # ─── product ───────────────────────────────────────────────────────────
    op.create_table(
        'product',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('shop_id', sa.BigInteger(), sa.ForeignKey('shop.id'), nullable=False),
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('category.id'), nullable=False),
        sa.Column('title', sa.String(512), nullable=False),
        sa.Column('slug', sa.String(600), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price', sa.Numeric(12, 2), nullable=False),
        sa.Column('compare_at_price', sa.Numeric(12, 2), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('weight_g', sa.Integer(), nullable=False, server_default='500'),
        sa.Column('status', sa.Enum('pending', 'active', 'rejected', 'blocked', name='productstatus'), nullable=False, server_default='pending'),
        sa.Column('moderation_reason', sa.Text(), nullable=True),
        sa.Column('rating', sa.Numeric(3, 2), nullable=False, server_default='0.00'),
        sa.Column('reviews_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('views_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_product_shop_id', 'product', ['shop_id'])
    op.create_index('ix_product_category_id', 'product', ['category_id'])
    op.create_index('ix_product_status', 'product', ['status'])
    op.create_index('ix_product_price', 'product', ['price'])
    op.create_index('ix_product_rating', 'product', ['rating'])
    op.create_index('ix_product_title', 'product', ['title'])

    # ─── product_co_purchase (materialized "bought together") ──────────────
    op.create_table(
        'product_co_purchase',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('product.id'), nullable=False),
        sa.Column('related_product_id', sa.BigInteger(), sa.ForeignKey('product.id'), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('product_id', 'related_product_id', name='uq_co_purchase_pair'),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_co_purchase_lookup', 'product_co_purchase', ['product_id', 'score'])

    # ─── product_variant ───────────────────────────────────────────────────
    op.create_table(
        'product_variant',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('product.id'), nullable=False),
        sa.Column('sku', sa.String(64), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('price', sa.Numeric(12, 2), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_product_variant_product_id', 'product_variant', ['product_id'])

    # ─── attribute ─────────────────────────────────────────────────────────
    op.create_table(
        'attribute',
        sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('slug', sa.String(100), nullable=False),
        sa.Column('is_filterable', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('slug'),
        mysql_engine='InnoDB',
    )

    # ─── product_attribute_value ───────────────────────────────────────────
    op.create_table(
        'product_attribute_value',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('product.id'), nullable=False),
        sa.Column('attribute_id', sa.Integer(), sa.ForeignKey('attribute.id'), nullable=False),
        sa.Column('value', sa.String(255), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_product_attr_value_product_id', 'product_attribute_value', ['product_id'])
    op.create_index('ix_product_attr_value_attribute_id', 'product_attribute_value', ['attribute_id'])
    op.create_index('ix_product_attr_value_value', 'product_attribute_value', ['value'])

    # ─── product_question ──────────────────────────────────────────────────
    op.create_table(
        'product_question',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('product.id'), nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('answer', sa.Text(), nullable=True),
        sa.Column('answered_by_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('answered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_product_question_product_id', 'product_question', ['product_id'])

    # ─── product_image ─────────────────────────────────────────────────────
    op.create_table(
        'product_image',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('product.id'), nullable=False),
        sa.Column('url', sa.String(512), nullable=False),
        sa.Column('is_main', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_product_image_product_id', 'product_image', ['product_id'])

    # ─── cart_item ─────────────────────────────────────────────────────────
    op.create_table(
        'cart_item',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('product.id'), nullable=False),
        sa.Column('variant_id', sa.BigInteger(), sa.ForeignKey('product_variant.id'), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('user_id', 'product_id', 'variant_id', name='uq_cart_user_product_variant'),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_cart_item_user_id', 'cart_item', ['user_id'])

    # ─── coupon ────────────────────────────────────────────────────────────
    op.create_table(
        'coupon',
        sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('discount_type', sa.Enum('percent', 'fixed', name='discounttype'), nullable=False),
        sa.Column('discount_value', sa.Numeric(10, 2), nullable=False),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=False),
        sa.Column('max_uses', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('used_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('min_order_amount', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('code'),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_coupon_code', 'coupon', ['code'])

    # ─── order ─────────────────────────────────────────────────────────────
    op.create_table(
        'order',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('buyer_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('total_price', sa.Numeric(12, 2), nullable=False),
        sa.Column('subtotal', sa.Numeric(12, 2), nullable=False),
        sa.Column('delivery_cost', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('platform_fee', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('seller_net', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('commission_percent_used', sa.Numeric(5, 2), nullable=False, server_default='10.00'),
        sa.Column('bonus_used', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('promo_used', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('status', sa.Enum(
            'pending_payment', 'paid', 'processing', 'shipped',
            'delivered', 'completed', 'cancelled', 'refunded',
            name='orderstatus'), nullable=False, server_default='pending_payment'),
        sa.Column('delivery_address', sa.Text(), nullable=False),
        sa.Column('coupon_id', sa.Integer(), sa.ForeignKey('coupon.id'), nullable=True),
        sa.Column('coupon_discount', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('currency', sa.Enum('RUB', 'USD', 'EUR', name='currencycode'), nullable=False, server_default='RUB'),
        sa.Column('exchange_rate', sa.Numeric(12, 6), nullable=False, server_default='1.000000'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_order_buyer_id', 'order', ['buyer_id'])
    op.create_index('ix_order_status', 'order', ['status'])
    op.create_index('ix_order_created_at', 'order', ['created_at'])

    # ─── sub_order ─────────────────────────────────────────────────────────
    op.create_table(
        'sub_order',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('order_id', sa.BigInteger(), sa.ForeignKey('order.id'), nullable=False),
        sa.Column('shop_id', sa.BigInteger(), sa.ForeignKey('shop.id'), nullable=False),
        sa.Column('status', sa.Enum('processing', 'shipped', 'delivered', 'completed', 'cancelled', name='suborderstatus'), nullable=False, server_default='processing'),
        sa.Column('tracking_number', sa.String(128), nullable=True),
        sa.Column('delivery_service', sa.String(50), nullable=True),
        sa.Column('carrier_uuid', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('order_id', 'shop_id', name='uq_sub_order_order_shop'),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_sub_order_order_id', 'sub_order', ['order_id'])
    op.create_index('ix_sub_order_shop_id', 'sub_order', ['shop_id'])

    # ─── order_item ────────────────────────────────────────────────────────
    op.create_table(
        'order_item',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('order_id', sa.BigInteger(), sa.ForeignKey('order.id'), nullable=False),
        sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('product.id'), nullable=False),
        sa.Column('variant_id', sa.BigInteger(), sa.ForeignKey('product_variant.id'), nullable=True),
        sa.Column('variant_name', sa.String(255), nullable=True),
        sa.Column('shop_id', sa.BigInteger(), sa.ForeignKey('shop.id'), nullable=False),
        sa.Column('sub_order_id', sa.BigInteger(), sa.ForeignKey('sub_order.id'), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('price_at_time', sa.Numeric(12, 2), nullable=False),
        sa.Column('commission_percent_used', sa.Numeric(5, 2), nullable=False, server_default='10.00'),
        sa.Column('platform_fee', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('seller_net', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('payout_status', sa.String(20), nullable=False, server_default='pending'),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_order_item_order_id', 'order_item', ['order_id'])
    op.create_index('ix_order_item_shop_id', 'order_item', ['shop_id'])

    # ─── payment ───────────────────────────────────────────────────────────
    op.create_table(
        'payment',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('order_id', sa.BigInteger(), sa.ForeignKey('order.id'), nullable=False),
        sa.Column('gateway', sa.Enum('yookassa', 'cloudpayments', name='paymentgateway'), nullable=False),
        sa.Column('gateway_payment_id', sa.String(255), nullable=True),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('status', sa.Enum('pending', 'succeeded', 'cancelled', 'refunded', name='paymentstatus'), nullable=False, server_default='pending'),
        sa.Column('confirmation_url', sa.String(1024), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('order_id'),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_payment_gateway_payment_id', 'payment', ['gateway_payment_id'])

    # ─── transaction ───────────────────────────────────────────────────────
    op.create_table(
        'transaction',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('type', sa.Enum(
            'order_payment', 'order_refund', 'commission', 'payout', 'referral_reward', 'bonus_used',
            name='transactiontype'), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('order_id', sa.BigInteger(), sa.ForeignKey('order.id'), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('balance_after', sa.Numeric(12, 2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_transaction_user_id', 'transaction', ['user_id'])
    op.create_index('ix_transaction_type', 'transaction', ['type'])

    # ─── delivery_info ─────────────────────────────────────────────────────
    op.create_table(
        'delivery_info',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('order_id', sa.BigInteger(), sa.ForeignKey('order.id'), nullable=False),
        sa.Column('delivery_service', sa.String(50), nullable=False, server_default='cdek'),
        sa.Column('tracking_number', sa.String(100), nullable=True),
        sa.Column('cost', sa.Numeric(12, 2), nullable=False),
        sa.Column('estimated_days', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('city_from', sa.String(255), nullable=False, server_default='Москва'),
        sa.Column('city_to', sa.String(255), nullable=False),
        sa.Column('address', sa.Text(), nullable=False),
        sa.Column('shipped_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('order_id'),
        mysql_engine='InnoDB',
    )

    # ─── referral ──────────────────────────────────────────────────────────
    op.create_table(
        'referral',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('referrer_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('referred_user_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('type', sa.Enum('buyer', 'seller', name='referraltype'), nullable=False),
        sa.Column('code', sa.String(32), nullable=False),
        sa.Column('reward_paid', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('referred_user_id'),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_referral_referrer_id', 'referral', ['referrer_id'])

    # ─── referral_reward ───────────────────────────────────────────────────
    op.create_table(
        'referral_reward',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('referral_id', sa.BigInteger(), sa.ForeignKey('referral.id'), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('type', sa.Enum('buyer', 'seller', name='referraltype_reward'), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )

    # ─── balance_transaction ───────────────────────────────────────────────
    op.create_table(
        'balance_transaction',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('change', sa.Numeric(12, 2), nullable=False),
        sa.Column('type', sa.Enum('credit', 'debit', name='balancetransactiontype'), nullable=False),
        sa.Column('reference_type', sa.String(50), nullable=True),
        sa.Column('reference_id', sa.BigInteger(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('balance_after', sa.Numeric(12, 2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_balance_tx_user_id', 'balance_transaction', ['user_id'])

    # ─── report ────────────────────────────────────────────────────────────
    op.create_table(
        'report',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('reporter_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('target_type', sa.String(20), nullable=False),
        sa.Column('target_id', sa.BigInteger(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.Enum('open', 'in_review', 'resolved', 'dismissed', name='reportstatus'), nullable=False, server_default='open'),
        sa.Column('moderator_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('resolution', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_report_status', 'report', ['status'])
    op.create_index('ix_report_target', 'report', ['target_type', 'target_id'])

    # ─── review ────────────────────────────────────────────────────────────
    op.create_table(
        'review',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('product.id'), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected', name='reviewstatus'), nullable=False, server_default='pending'),
        sa.Column('moderation_reason', sa.Text(), nullable=True),
        sa.Column('moderated_by_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('moderated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('helpful_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_verified_purchase', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('order_id', sa.BigInteger(), sa.ForeignKey('order.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('user_id', 'product_id', name='uq_review_user_product'),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_review_product_id', 'review', ['product_id'])
    op.create_index('ix_review_status', 'review', ['status'])

    # ─── review_reply ──────────────────────────────────────────────────────
    op.create_table(
        'review_reply',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('review_id', sa.BigInteger(), sa.ForeignKey('review.id'), nullable=False),
        sa.Column('seller_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('review_id'),
        mysql_engine='InnoDB',
    )

    # ─── review_vote ───────────────────────────────────────────────────────
    op.create_table(
        'review_vote',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('review_id', sa.BigInteger(), sa.ForeignKey('review.id'), nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('review_id', 'user_id', name='uq_review_vote_user'),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_review_vote_review_id', 'review_vote', ['review_id'])

    # ─── favorite ──────────────────────────────────────────────────────────
    op.create_table(
        'favorite',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('product.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('user_id', 'product_id', name='uq_favorite_user_product'),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_favorite_user_id', 'favorite', ['user_id'])

    # ─── seller_plan ───────────────────────────────────────────────────────
    op.create_table(
        'seller_plan',
        sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('monthly_price', sa.Numeric(10, 2), nullable=False, server_default='0.00'),
        sa.Column('commission_percent', sa.Numeric(5, 2), nullable=False),
        sa.Column('trial_days', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )

    # ─── seller_subscription ───────────────────────────────────────────────
    op.create_table(
        'seller_subscription',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('shop_id', sa.BigInteger(), sa.ForeignKey('shop.id'), nullable=False),
        sa.Column('plan_id', sa.Integer(), sa.ForeignKey('seller_plan.id'), nullable=False),
        sa.Column('status', sa.Enum('active', 'trial', 'expired', 'cancelled', name='subscriptionstatus'), nullable=False, server_default='active'),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('trial_used', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('auto_renew', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('shop_id'),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_seller_subscription_shop_id', 'seller_subscription', ['shop_id'])
    op.create_index('ix_seller_subscription_status', 'seller_subscription', ['status'])

    # ─── password_reset_token ──────────────────────────────────────────────
    op.create_table(
        'password_reset_token',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('token', sa.String(64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('token'),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_password_reset_token_token', 'password_reset_token', ['token'])
    op.create_index('ix_password_reset_token_user_id', 'password_reset_token', ['user_id'])

    # ─── review_photo ──────────────────────────────────────────────────────
    op.create_table(
        'review_photo',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('review_id', sa.BigInteger(), sa.ForeignKey('review.id'), nullable=False),
        sa.Column('url', sa.String(512), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_review_photo_review_id', 'review_photo', ['review_id'])

    # ─── notification ──────────────────────────────────────────────────────
    op.create_table(
        'notification',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('type', sa.Enum('order_status', 'review_reply', 'review_moderated', 'product_moderated', 'question_answered', 'new_message', 'payout', 'new_order', 'shop_update', 'system', name='notificationtype'), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('link', sa.String(512), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_notification_user_id', 'notification', ['user_id'])
    op.create_index('ix_notification_is_read', 'notification', ['is_read'])

    # ─── chat_thread ───────────────────────────────────────────────────────
    op.create_table(
        'chat_thread',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('buyer_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('shop_id', sa.BigInteger(), sa.ForeignKey('shop.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('buyer_id', 'shop_id', name='uq_chat_buyer_shop'),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_chat_thread_buyer_id', 'chat_thread', ['buyer_id'])
    op.create_index('ix_chat_thread_shop_id', 'chat_thread', ['shop_id'])

    # ─── chat_message ──────────────────────────────────────────────────────
    op.create_table(
        'chat_message',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('thread_id', sa.BigInteger(), sa.ForeignKey('chat_thread.id'), nullable=False),
        sa.Column('sender_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_chat_message_thread_id', 'chat_message', ['thread_id'])

    # ─── seller_coupon ─────────────────────────────────────────────────────
    op.create_table(
        'seller_coupon',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('shop_id', sa.BigInteger(), sa.ForeignKey('shop.id'), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('discount_type', sa.Enum('percent', 'fixed', name='discounttype'), nullable=False, server_default='percent'),
        sa.Column('discount_value', sa.Numeric(12, 2), nullable=False),
        sa.Column('min_order_amount', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('usage_limit', sa.Integer(), nullable=True),
        sa.Column('used_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('code'),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_seller_coupon_shop_id', 'seller_coupon', ['shop_id'])
    op.create_index('ix_seller_coupon_code', 'seller_coupon', ['code'])

    # ─── payout_request ────────────────────────────────────────────────────
    op.create_table(
        'payout_request',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected', 'paid', name='payoutrequeststatus'), nullable=False, server_default='pending'),
        sa.Column('payout_details', sa.String(512), nullable=False),
        sa.Column('admin_comment', sa.Text(), nullable=True),
        sa.Column('processed_by_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_payout_request_user_id', 'payout_request', ['user_id'])
    op.create_index('ix_payout_request_status', 'payout_request', ['status'])

    # ─── homepage_banner ───────────────────────────────────────────────────
    op.create_table(
        'homepage_banner',
        sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('subtitle', sa.String(512), nullable=True),
        sa.Column('image_url', sa.String(512), nullable=False),
        sa.Column('link', sa.String(512), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )

    # ─── return_request ────────────────────────────────────────────────────
    op.create_table(
        'return_request',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('order_item_id', sa.BigInteger(), sa.ForeignKey('order_item.id'), nullable=False),
        sa.Column('buyer_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('shop_id', sa.BigInteger(), sa.ForeignKey('shop.id'), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.Enum('requested', 'approved', 'rejected', 'in_transit', 'refunded', name='returnrequeststatus'), nullable=False, server_default='requested'),
        sa.Column('refund_amount', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('resolution_comment', sa.Text(), nullable=True),
        sa.Column('processed_by_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_return_request_buyer_id', 'return_request', ['buyer_id'])
    op.create_index('ix_return_request_shop_id', 'return_request', ['shop_id'])
    op.create_index('ix_return_request_status', 'return_request', ['status'])

    # ─── product_subscription ──────────────────────────────────────────────
    op.create_table(
        'product_subscription',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('product.id'), nullable=False),
        sa.Column('kind', sa.String(20), nullable=False),
        sa.Column('target_price', sa.Numeric(12, 2), nullable=True),
        sa.Column('is_notified', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('user_id', 'product_id', 'kind', name='uq_product_sub_user_product_kind'),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_product_subscription_product_id', 'product_subscription', ['product_id'])

    # ─── currency_rate ─────────────────────────────────────────────────────
    op.create_table(
        'currency_rate',
        sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column('code', sa.Enum('RUB', 'USD', 'EUR', name='currencycode'), nullable=False),
        sa.Column('rate', sa.Numeric(12, 6), nullable=False),
        sa.Column('symbol', sa.String(8), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('code'),
        mysql_engine='InnoDB',
    )

    # ─── address ───────────────────────────────────────────────────────────
    op.create_table(
        'address',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('label', sa.String(100), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('phone', sa.String(20), nullable=False),
        sa.Column('city', sa.String(120), nullable=False),
        sa.Column('street', sa.String(255), nullable=False),
        sa.Column('building', sa.String(50), nullable=True),
        sa.Column('apartment', sa.String(50), nullable=True),
        sa.Column('postal_code', sa.String(20), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_address_user_id', 'address', ['user_id'])

    # ─── wishlist_collection ───────────────────────────────────────────────
    op.create_table(
        'wishlist_collection',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_wishlist_collection_user_id', 'wishlist_collection', ['user_id'])

    # ─── wishlist_item ─────────────────────────────────────────────────────
    op.create_table(
        'wishlist_item',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('collection_id', sa.BigInteger(), sa.ForeignKey('wishlist_collection.id'), nullable=False),
        sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('product.id'), nullable=False),
        sa.Column('added_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('collection_id', 'product_id', name='uq_wishlist_collection_product'),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_wishlist_item_collection_id', 'wishlist_item', ['collection_id'])

    # ─── product_view ──────────────────────────────────────────────────────
    op.create_table(
        'product_view',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('product.id'), nullable=False),
        sa.Column('viewed_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('user_id', 'product_id', name='uq_product_view_user_product'),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_product_view_user_id', 'product_view', ['user_id'])

    # ─── stock_movement ────────────────────────────────────────────────────
    op.create_table(
        'stock_movement',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('product.id'), nullable=False),
        sa.Column('variant_id', sa.BigInteger(), sa.ForeignKey('product_variant.id'), nullable=True),
        sa.Column('change', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(40), nullable=False),
        sa.Column('quantity_after', sa.Integer(), nullable=False),
        sa.Column('note', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_stock_movement_product_id', 'stock_movement', ['product_id'])

    # ─── flash_sale ────────────────────────────────────────────────────────
    op.create_table(
        'flash_sale',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('product.id'), nullable=False),
        sa.Column('shop_id', sa.BigInteger(), sa.ForeignKey('shop.id'), nullable=False),
        sa.Column('discount_percent', sa.Numeric(5, 2), nullable=False),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_flash_sale_product_id', 'flash_sale', ['product_id'])
    op.create_index('ix_flash_sale_shop_id', 'flash_sale', ['shop_id'])
    op.create_index('ix_flash_sale_active_window', 'flash_sale', ['is_active', 'starts_at', 'ends_at'])

    # ─── audit_log ─────────────────────────────────────────────────────────
    op.create_table(
        'audit_log',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('actor_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('action', sa.String(80), nullable=False),
        sa.Column('entity_type', sa.String(40), nullable=False),
        sa.Column('entity_id', sa.BigInteger(), nullable=True),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_audit_log_entity', 'audit_log', ['entity_type', 'entity_id'])
    op.create_index('ix_audit_log_actor_id', 'audit_log', ['actor_id'])
    op.create_index('ix_audit_log_created_at', 'audit_log', ['created_at'])

    # ─── feature_flag ──────────────────────────────────────────────────────
    op.create_table(
        'feature_flag',
        sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column('key', sa.String(80), nullable=False),
        sa.Column('description', sa.String(255), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('rollout_percent', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('key'),
        mysql_engine='InnoDB',
    )

    # ─── chat_template ─────────────────────────────────────────────────────
    op.create_table(
        'chat_template',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('shop_id', sa.BigInteger(), sa.ForeignKey('shop.id'), nullable=False),
        sa.Column('title', sa.String(120), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_chat_template_shop_id', 'chat_template', ['shop_id'])

    # ─── verification_code ─────────────────────────────────────────────────
    op.create_table(
        'verification_code',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('code', sa.String(8), nullable=False),
        sa.Column('purpose', sa.Enum('email', 'phone', name='verificationpurpose'), nullable=False),
        sa.Column('destination', sa.String(255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_verification_code_user_purpose', 'verification_code', ['user_id', 'purpose'])

    # ─── seller_requisites ─────────────────────────────────────────────────
    op.create_table(
        'seller_requisites',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('shop_id', sa.BigInteger(), sa.ForeignKey('shop.id'), nullable=False),
        sa.Column('tax_regime', sa.Enum('self_employed', 'individual', 'company', name='taxregime'), nullable=False),
        sa.Column('legal_name', sa.String(255), nullable=False),
        sa.Column('inn', sa.String(12), nullable=False),
        sa.Column('ogrn', sa.String(15), nullable=True),
        sa.Column('kpp', sa.String(9), nullable=True),
        sa.Column('legal_address', sa.String(500), nullable=True),
        sa.Column('vat_code', sa.Integer(), nullable=True),
        sa.Column('tax_system_code', sa.Integer(), nullable=True),
        sa.Column('bank_account', sa.String(20), nullable=True),
        sa.Column('bank_name', sa.String(255), nullable=True),
        sa.Column('bik', sa.String(9), nullable=True),
        sa.Column('corr_account', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('shop_id'),
        mysql_engine='InnoDB',
    )

    # ─── sms_log ───────────────────────────────────────────────────────────
    op.create_table(
        'sms_log',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('phone', sa.String(20), nullable=False),
        sa.Column('purpose', sa.String(40), nullable=False),
        sa.Column('text_preview', sa.String(255), nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('smsc_id', sa.String(40), nullable=True),
        sa.Column('cost', sa.Numeric(10, 2), nullable=True),
        sa.Column('sms_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('error', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_sms_log_created_at', 'sms_log', ['created_at'])
    op.create_index('ix_sms_log_purpose', 'sms_log', ['purpose'])
    op.create_index('ix_sms_log_status', 'sms_log', ['status'])

    # ─── fiscal_receipt ────────────────────────────────────────────────────
    op.create_table(
        'fiscal_receipt',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('order_id', sa.BigInteger(), sa.ForeignKey('order.id'), nullable=False),
        sa.Column('payment_id', sa.BigInteger(), sa.ForeignKey('payment.id'), nullable=True),
        sa.Column('type', sa.Enum('income', 'income_refund', name='fiscalreceipttype'), nullable=False),
        sa.Column('status', sa.Enum('pending', 'succeeded', 'canceled', 'failed', name='fiscalreceiptstatus'), nullable=False, server_default='pending'),
        sa.Column('customer_contact', sa.String(255), nullable=False),
        sa.Column('total', sa.Numeric(12, 2), nullable=False),
        sa.Column('tax_system_code', sa.Integer(), nullable=True),
        sa.Column('items_json', sa.Text(), nullable=False),
        sa.Column('fiscal_document_number', sa.String(32), nullable=True),
        sa.Column('fiscal_storage_number', sa.String(32), nullable=True),
        sa.Column('fiscal_attribute', sa.String(32), nullable=True),
        sa.Column('registered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error', sa.String(500), nullable=True),
        sa.Column('raw_response', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_fiscal_receipt_order_id', 'fiscal_receipt', ['order_id'])
    op.create_index('ix_fiscal_receipt_status', 'fiscal_receipt', ['status'])

    # ─── support_ticket / support_message ──────────────────────────────────
    op.create_table(
        'support_ticket',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('subject', sa.String(255), nullable=False),
        sa.Column('category', sa.String(40), nullable=True),
        sa.Column('status', sa.Enum('open', 'in_progress', 'pending_user', 'resolved', 'closed', name='supportticketstatus'), nullable=False, server_default='open'),
        sa.Column('priority', sa.Enum('low', 'normal', 'high', 'urgent', name='supportticketpriority'), nullable=False, server_default='normal'),
        sa.Column('assigned_to_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('escalation_level', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('first_response_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_support_ticket_user_id', 'support_ticket', ['user_id'])
    op.create_index('ix_support_ticket_status', 'support_ticket', ['status'])
    op.create_index('ix_support_ticket_assigned_to_id', 'support_ticket', ['assigned_to_id'])

    op.create_table(
        'support_message',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('ticket_id', sa.BigInteger(), sa.ForeignKey('support_ticket.id'), nullable=False),
        sa.Column('sender_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('is_staff', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('attachment_url', sa.String(512), nullable=True),
        sa.Column('read_by_user', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('read_by_staff', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_support_message_ticket_id', 'support_message', ['ticket_id'])

    # ─── paid_feature / promotion (paid placement & auction) ───────────────
    op.create_table(
        'paid_feature',
        sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column('key', sa.String(64), nullable=False, unique=True),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('placement', sa.String(40), nullable=False),
        sa.Column('pricing_mode', sa.Enum('fixed', 'auction', name='paidfeaturepricing'), nullable=False, server_default='fixed'),
        sa.Column('price', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('billing_period', sa.String(10), nullable=False, server_default='day'),
        sa.Column('slots', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )

    op.create_table(
        'promotion',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('shop_id', sa.BigInteger(), sa.ForeignKey('shop.id'), nullable=False),
        sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('product.id'), nullable=True),
        sa.Column('feature_id', sa.Integer(), sa.ForeignKey('paid_feature.id'), nullable=False),
        sa.Column('feature_key', sa.String(64), nullable=False),
        sa.Column('placement', sa.String(40), nullable=False),
        sa.Column('bid_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('status', sa.Enum('pending', 'active', 'outbid', 'expired', 'cancelled', name='promotionstatus'), nullable=False, server_default='pending'),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_charged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_spent', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('impressions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('clicks', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_promotion_shop_id', 'promotion', ['shop_id'])
    op.create_index('ix_promotion_placement', 'promotion', ['placement'])
    op.create_index('ix_promotion_status', 'promotion', ['status'])

    op.create_table(
        'ad_wallet_transaction',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('shop_id', sa.BigInteger(), sa.ForeignKey('shop.id'), nullable=False),
        sa.Column('change', sa.Numeric(12, 2), nullable=False),
        sa.Column('kind', sa.String(20), nullable=False),
        sa.Column('description', sa.String(255), nullable=True),
        sa.Column('balance_after', sa.Numeric(12, 2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_ad_wallet_transaction_shop_id', 'ad_wallet_transaction', ['shop_id'])

    op.create_table(
        'shop_follow',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('shop_id', sa.BigInteger(), sa.ForeignKey('shop.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('user_id', 'shop_id', name='uq_shop_follow'),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_shop_follow_user_id', 'shop_follow', ['user_id'])
    op.create_index('ix_shop_follow_shop_id', 'shop_follow', ['shop_id'])

    # ─── promo_rule / bundle / bundle_item (advanced promotions) ───────────
    op.create_table(
        'promo_rule',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('shop_id', sa.BigInteger(), sa.ForeignKey('shop.id'), nullable=False),
        sa.Column('title', sa.String(160), nullable=False),
        sa.Column('type', sa.Enum('nplus', 'volume', name='promotype'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('product.id'), nullable=True),
        sa.Column('category_id', sa.BigInteger(), sa.ForeignKey('category.id'), nullable=True),
        sa.Column('buy_quantity', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('free_quantity', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tiers_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_promo_rule_shop_id', 'promo_rule', ['shop_id'])

    op.create_table(
        'bundle',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('shop_id', sa.BigInteger(), sa.ForeignKey('shop.id'), nullable=False),
        sa.Column('title', sa.String(160), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('bundle_price', sa.Numeric(12, 2), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_bundle_shop_id', 'bundle', ['shop_id'])

    op.create_table(
        'bundle_item',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('bundle_id', sa.BigInteger(), sa.ForeignKey('bundle.id'), nullable=False),
        sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('product.id'), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_bundle_item_bundle_id', 'bundle_item', ['bundle_id'])

    # ─── dispute / dispute_message (arbitration) ───────────────────────────
    op.create_table(
        'dispute',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('order_id', sa.BigInteger(), sa.ForeignKey('order.id'), nullable=False),
        sa.Column('order_item_id', sa.BigInteger(), sa.ForeignKey('order_item.id'), nullable=True),
        sa.Column('buyer_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('shop_id', sa.BigInteger(), sa.ForeignKey('shop.id'), nullable=False),
        sa.Column('opened_by', sa.String(10), nullable=False, server_default='buyer'),
        sa.Column('subject', sa.String(200), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.Enum('open', 'in_mediation', 'resolved', 'cancelled', name='disputestatus'), nullable=False, server_default='open'),
        sa.Column('resolution', sa.Enum('none', 'buyer_favor', 'seller_favor', 'partial', name='disputeresolution'), nullable=False, server_default='none'),
        sa.Column('refund_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('resolution_note', sa.Text(), nullable=True),
        sa.Column('mediator_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_dispute_buyer_id', 'dispute', ['buyer_id'])
    op.create_index('ix_dispute_shop_id', 'dispute', ['shop_id'])
    op.create_index('ix_dispute_status', 'dispute', ['status'])

    op.create_table(
        'dispute_message',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('dispute_id', sa.BigInteger(), sa.ForeignKey('dispute.id'), nullable=False),
        sa.Column('sender_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('sender_role', sa.String(10), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('attachment_url', sa.String(512), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_dispute_message_dispute_id', 'dispute_message', ['dispute_id'])

    # ─── gift_certificate / promo_balance_transaction ──────────────────────
    op.create_table(
        'gift_certificate',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('code', sa.String(32), nullable=False, unique=True),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('status', sa.Enum('active', 'redeemed', 'cancelled', 'expired', name='giftcertificatestatus'), nullable=False, server_default='active'),
        sa.Column('purchaser_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('redeemed_by_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('recipient_email', sa.String(255), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('redeemed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_gift_certificate_code', 'gift_certificate', ['code'])
    op.create_index('ix_gift_certificate_status', 'gift_certificate', ['status'])

    op.create_table(
        'promo_balance_transaction',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('change', sa.Numeric(12, 2), nullable=False),
        sa.Column('kind', sa.String(20), nullable=False),
        sa.Column('description', sa.String(255), nullable=True),
        sa.Column('balance_after', sa.Numeric(12, 2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_promo_balance_transaction_user_id', 'promo_balance_transaction', ['user_id'])

    # ─── loyalty_tier (admin-configurable loyalty levels) ──────────────────
    op.create_table(
        'loyalty_tier',
        sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column('key', sa.String(40), nullable=False, unique=True),
        sa.Column('name', sa.String(80), nullable=False),
        sa.Column('level', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('min_spend', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('cashback_percent', sa.Numeric(5, 2), nullable=False, server_default='0.00'),
        sa.Column('free_shipping', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('perks', sa.Text(), nullable=True),
        sa.Column('color', sa.String(20), nullable=True),
        sa.Column('retention_days', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )

    # ─── settings ──────────────────────────────────────────────────────────
    op.create_table(
        'settings',
        sa.Column('key', sa.String(100), primary_key=True),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        mysql_engine='InnoDB',
    )


def downgrade() -> None:
    op.drop_table('settings')
    op.drop_table('loyalty_tier')
    op.drop_table('promo_balance_transaction')
    op.drop_table('gift_certificate')
    op.drop_table('dispute_message')
    op.drop_table('dispute')
    op.drop_table('bundle_item')
    op.drop_table('bundle')
    op.drop_table('promo_rule')
    op.drop_table('shop_follow')
    op.drop_table('ad_wallet_transaction')
    op.drop_table('promotion')
    op.drop_table('paid_feature')
    op.drop_table('support_message')
    op.drop_table('support_ticket')
    op.drop_table('fiscal_receipt')
    op.drop_table('sms_log')
    op.drop_table('seller_requisites')
    op.drop_table('verification_code')
    op.drop_table('chat_template')
    op.drop_table('feature_flag')
    op.drop_table('audit_log')
    op.drop_table('flash_sale')
    op.drop_table('stock_movement')
    op.drop_table('product_view')
    op.drop_table('wishlist_item')
    op.drop_table('wishlist_collection')
    op.drop_table('address')
    op.drop_table('currency_rate')
    op.drop_table('product_subscription')
    op.drop_table('return_request')
    op.drop_table('homepage_banner')
    op.drop_table('payout_request')
    op.drop_table('seller_coupon')
    op.drop_table('chat_message')
    op.drop_table('chat_thread')
    op.drop_table('notification')
    op.drop_table('review_photo')
    op.drop_table('password_reset_token')
    op.drop_table('seller_subscription')
    op.drop_table('seller_plan')
    op.drop_table('favorite')
    op.drop_table('review_vote')
    op.drop_table('review_reply')
    op.drop_table('review')
    op.drop_table('report')
    op.drop_table('balance_transaction')
    op.drop_table('referral_reward')
    op.drop_table('referral')
    op.drop_table('delivery_info')
    op.drop_table('transaction')
    op.drop_table('payment')
    op.drop_table('order_item')
    op.drop_table('sub_order')
    op.drop_table('order')
    op.drop_table('coupon')
    op.drop_table('cart_item')
    op.drop_table('product_image')
    op.drop_table('product_question')
    op.drop_table('product_attribute_value')
    op.drop_table('attribute')
    op.drop_table('product_variant')
    op.drop_table('product_co_purchase')
    op.drop_table('product')
    op.drop_table('category')
    op.drop_table('shop')
    op.drop_table('user')
