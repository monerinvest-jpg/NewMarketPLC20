"""shop staff accounts (shop_member)

Revision ID: 0008_shop_members
Revises: 0007_referral_program
Create Date: 2026-06-30

Multi-user shop accounts: a shop owner can attach staff (manager/staff) with
granular per-area permissions. Idempotent.
"""
from alembic import op

from app.core.database import Base
import app.models.models  # noqa: F401

revision = "0008_shop_members"
down_revision = "0007_referral_program"
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
    _dedupe_indexes()
    Base.metadata.create_all(bind=bind, tables=[Base.metadata.tables["shop_member"]])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS shop_member")
