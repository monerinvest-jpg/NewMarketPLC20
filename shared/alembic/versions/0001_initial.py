"""initial schema (PostgreSQL, built from SQLAlchemy metadata).

De-duplicates same-named indexes (some columns have both index=True and an
explicit Index() with the conventional name) and drops any partial schema from
a previously failed attempt, so this initial migration is self-healing.
"""
from alembic import op
from app.core.database import Base
import app.models.models  # noqa: F401

revision = '0001_initial'
down_revision = None
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
    Base.metadata.drop_all(bind=bind)
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
