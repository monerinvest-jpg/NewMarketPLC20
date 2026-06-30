"""custom / made-to-order requests

Revision ID: 0015_custom_orders
Revises: 0014_seller_academy
Create Date: 2026-06-30

Etsy-style custom commissions: custom_request + custom_message. Idempotent.
"""
from alembic import op

from app.core.database import Base
import app.models.models  # noqa: F401

revision = "0015_custom_orders"
down_revision = "0014_seller_academy"
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
        Base.metadata.tables["custom_request"],
        Base.metadata.tables["custom_message"],
    ])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS custom_message")
    op.execute("DROP TABLE IF EXISTS custom_request")
