"""seller academy (courses/lessons/progress)

Revision ID: 0014_seller_academy
Revises: 0013_installments
Create Date: 2026-06-30

Platform-authored seller education. Idempotent.
"""
from alembic import op

from app.core.database import Base
import app.models.models  # noqa: F401

revision = "0014_seller_academy"
down_revision = "0013_installments"
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
    Base.metadata.create_all(bind=bind, tables=[
        Base.metadata.tables["academy_course"],
        Base.metadata.tables["academy_lesson"],
        Base.metadata.tables["academy_progress"],
    ])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS academy_progress")
    op.execute("DROP TABLE IF EXISTS academy_lesson")
    op.execute("DROP TABLE IF EXISTS academy_course")
