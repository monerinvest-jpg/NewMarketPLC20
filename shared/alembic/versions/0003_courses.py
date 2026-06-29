"""courses / LMS: course, course_module, course_lesson, lesson_progress

Revision ID: 0003_courses
Revises: 0002_digital_goods
Create Date: 2026-06-29

Adds the on-platform learning structure for course-type products. Access is
governed by the existing Entitlement (purchase of a course product), so no new
purchase plumbing is needed. Idempotent: create_all(checkfirst=True) only makes
the missing tables.
"""
from alembic import op

from app.core.database import Base
import app.models.models  # noqa: F401 - registers all ORM models

revision = "0003_courses"
down_revision = "0002_digital_goods"
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
    Base.metadata.create_all(
        bind=bind,
        tables=[
            Base.metadata.tables["course"],
            Base.metadata.tables["course_module"],
            Base.metadata.tables["course_lesson"],
            Base.metadata.tables["lesson_progress"],
        ],
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS lesson_progress")
    op.execute("DROP TABLE IF EXISTS course_lesson")
    op.execute("DROP TABLE IF EXISTS course_module")
    op.execute("DROP TABLE IF EXISTS course")
