"""lifelong referral program: referral_balance, withdrawal_account, payout source, reward order

Revision ID: 0007_referral_program
Revises: 0006_certificate_customization
Create Date: 2026-06-29

Turns referrals into a lifelong, withdrawable loyalty programme:
  * user.referral_balance — accrued referral earnings (money);
  * payout_request.source — 'sales' | 'referral' (which balance a withdrawal draws from);
  * referral_reward.order_id + unique(referral_id, order_id) — recurring per-order rewards
    without double-paying;
  * withdrawal_account — a user's tax/bank details for referral payouts.
Idempotent.
"""
from alembic import op

from app.core.database import Base
import app.models.models  # noqa: F401

revision = "0007_referral_program"
down_revision = "0006_certificate_customization"
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
    op.execute("ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS referral_balance NUMERIC(12,2) NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE \"order\" ADD COLUMN IF NOT EXISTS referral_used NUMERIC(12,2) NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE payout_request ADD COLUMN IF NOT EXISTS source VARCHAR(20) NOT NULL DEFAULT 'sales'")
    op.execute("ALTER TABLE referral_reward ADD COLUMN IF NOT EXISTS order_id BIGINT")
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_referral_reward_referral_order') THEN "
        "ALTER TABLE referral_reward ADD CONSTRAINT uq_referral_reward_referral_order UNIQUE (referral_id, order_id); "
        "END IF; END $$;"
    )
    _dedupe_indexes()
    Base.metadata.create_all(bind=bind, tables=[Base.metadata.tables["withdrawal_account"]])


def downgrade() -> None:
    op.execute("ALTER TABLE \"order\" DROP COLUMN IF EXISTS referral_used")
    op.execute("DROP TABLE IF EXISTS withdrawal_account")
    op.execute("ALTER TABLE referral_reward DROP CONSTRAINT IF EXISTS uq_referral_reward_referral_order")
    op.execute("ALTER TABLE referral_reward DROP COLUMN IF EXISTS order_id")
    op.execute("ALTER TABLE payout_request DROP COLUMN IF EXISTS source")
    op.execute("ALTER TABLE \"user\" DROP COLUMN IF EXISTS referral_balance")
