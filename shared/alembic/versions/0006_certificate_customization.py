"""certificate customization: course.cert_instructor + cert_logo_key

Revision ID: 0006_certificate_customization
Revises: 0005_hls
Create Date: 2026-06-29

Lets sellers personalise the completion certificate (instructor/signatory name
and a logo image). Idempotent (ADD COLUMN IF NOT EXISTS).
"""
from alembic import op

revision = "0006_certificate_customization"
down_revision = "0005_hls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE course ADD COLUMN IF NOT EXISTS cert_instructor VARCHAR(255)")
    op.execute("ALTER TABLE course ADD COLUMN IF NOT EXISTS cert_logo_key VARCHAR(512)")


def downgrade() -> None:
    op.execute("ALTER TABLE course DROP COLUMN IF EXISTS cert_logo_key")
    op.execute("ALTER TABLE course DROP COLUMN IF EXISTS cert_instructor")
