"""order gift options (wrap + message)

Revision ID: 0012_gift_options
Revises: 0011_review_media
Create Date: 2026-06-30

Adds order.is_gift / gift_wrap / gift_message. Idempotent.
"""
from alembic import op

revision = "0012_gift_options"
down_revision = "0011_review_media"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE \"order\" ADD COLUMN IF NOT EXISTS is_gift BOOLEAN NOT NULL DEFAULT false")
    op.execute("ALTER TABLE \"order\" ADD COLUMN IF NOT EXISTS gift_wrap BOOLEAN NOT NULL DEFAULT false")
    op.execute("ALTER TABLE \"order\" ADD COLUMN IF NOT EXISTS gift_message VARCHAR(500)")


def downgrade() -> None:
    op.execute("ALTER TABLE \"order\" DROP COLUMN IF EXISTS gift_message")
    op.execute("ALTER TABLE \"order\" DROP COLUMN IF EXISTS gift_wrap")
    op.execute("ALTER TABLE \"order\" DROP COLUMN IF EXISTS is_gift")
