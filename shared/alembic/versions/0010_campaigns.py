"""marketing campaigns + marketing opt-out

Revision ID: 0010_campaigns
Revises: 0009_seller_trust
Create Date: 2026-06-30

Adds user.marketing_opt_out and the campaign table. Idempotent.
"""
from alembic import op

from app.core.database import Base
import app.models.models  # noqa: F401

revision = "0010_campaigns"
down_revision = "0009_seller_trust"
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
    op.execute("ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS marketing_opt_out BOOLEAN NOT NULL DEFAULT false")
    _dedupe_indexes()
    Base.metadata.create_all(bind=bind, tables=[Base.metadata.tables["campaign"]])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS campaign")
    op.execute("ALTER TABLE \"user\" DROP COLUMN IF EXISTS marketing_opt_out")
