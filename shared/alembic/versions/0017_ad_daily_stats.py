"""Ad cabinet 2.0: per-day promotion stats (impressions/clicks/spend)

Revision ID: 0017_ad_daily_stats
Revises: 0016_vk_import
Create Date: 2026-07-02

Idempotent create_all for the new promotion_stat_daily table.
"""
from alembic import op

from app.core.database import Base
import app.models.models  # noqa: F401

revision = "0017_ad_daily_stats"
down_revision = "0016_vk_import"
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
        Base.metadata.tables["promotion_stat_daily"],
    ])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS promotion_stat_daily")
