"""hls: course_lesson.hls_ready

Revision ID: 0005_hls
Revises: 0004_quizzes_certificates
Create Date: 2026-06-29

Flags video lessons that have been packaged into encrypted HLS (AES-128).
Idempotent (ADD COLUMN IF NOT EXISTS).
"""
from alembic import op

revision = "0005_hls"
down_revision = "0004_quizzes_certificates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE course_lesson ADD COLUMN IF NOT EXISTS hls_ready BOOLEAN NOT NULL DEFAULT false")


def downgrade() -> None:
    op.execute("ALTER TABLE course_lesson DROP COLUMN IF EXISTS hls_ready")
