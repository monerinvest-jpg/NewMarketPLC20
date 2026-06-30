"""review media type (photo/video)

Revision ID: 0011_review_media
Revises: 0010_campaigns
Create Date: 2026-06-30

Adds review_photo.media_type so reviews can carry videos as well as photos.
Idempotent.
"""
from alembic import op

revision = "0011_review_media"
down_revision = "0010_campaigns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE review_photo ADD COLUMN IF NOT EXISTS media_type VARCHAR(10) NOT NULL DEFAULT 'image'")


def downgrade() -> None:
    op.execute("ALTER TABLE review_photo DROP COLUMN IF EXISTS media_type")
