"""BNPL installment plans

Revision ID: 0013_installments
Revises: 0012_gift_options
Create Date: 2026-06-30

Adds the installment_plan table for pay-in-parts (BNPL) orders. Idempotent.
"""
from alembic import op

from app.core.database import Base
import app.models.models  # noqa: F401

revision = "0013_installments"
down_revision = "0012_gift_options"
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
    Base.metadata.create_all(bind=bind, tables=[Base.metadata.tables["installment_plan"]])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS installment_plan")
