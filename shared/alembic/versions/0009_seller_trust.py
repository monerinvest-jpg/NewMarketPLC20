"""seller KYC verification + trust badges

Revision ID: 0009_seller_trust
Revises: 0008_shop_members
Create Date: 2026-06-30

Adds shop.kyc_verified + shop.vip_until and the seller_verification table.
Idempotent.
"""
from alembic import op

from app.core.database import Base
import app.models.models  # noqa: F401

revision = "0009_seller_trust"
down_revision = "0008_shop_members"
branch_labels = None
depends_on = None


def _dedupe_indexes() -> None:
    for table in Base.metadata.tables.values():
        seen = set()
        for idx in list(table.indexes):
            if idx.name in seen:
                table.indexes.discard(idx)
            else:
                seen.add(idx.name)


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("ALTER TABLE shop ADD COLUMN IF NOT EXISTS kyc_verified BOOLEAN NOT NULL DEFAULT false")
    op.execute("ALTER TABLE shop ADD COLUMN IF NOT EXISTS vip_until TIMESTAMPTZ")
    _dedupe_indexes()
    Base.metadata.create_all(bind=bind, tables=[Base.metadata.tables["seller_verification"]])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS seller_verification")
    op.execute("ALTER TABLE shop DROP COLUMN IF EXISTS vip_until")
    op.execute("ALTER TABLE shop DROP COLUMN IF EXISTS kyc_verified")
