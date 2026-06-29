"""quizzes + certificates: course_lesson.quiz_json, quiz_attempt, certificate

Revision ID: 0004_quizzes_certificates
Revises: 0003_courses
Create Date: 2026-06-29

Adds quiz lessons (LessonType.quiz + course_lesson.quiz_json answer key),
quiz attempt history, and completion certificates. Idempotent.
"""
from alembic import op

from app.core.database import Base
import app.models.models  # noqa: F401 - registers all ORM models

revision = "0004_quizzes_certificates"
down_revision = "0003_courses"
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
    op.execute("ALTER TABLE course_lesson ADD COLUMN IF NOT EXISTS quiz_json TEXT")
    _dedupe_indexes()
    Base.metadata.create_all(
        bind=bind,
        tables=[
            Base.metadata.tables["quiz_attempt"],
            Base.metadata.tables["certificate"],
        ],
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS certificate")
    op.execute("DROP TABLE IF EXISTS quiz_attempt")
    op.execute("ALTER TABLE course_lesson DROP COLUMN IF EXISTS quiz_json")
