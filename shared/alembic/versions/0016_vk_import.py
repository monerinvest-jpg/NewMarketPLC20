"""VK Market import: shop_integration table + product provenance columns

Revision ID: 0016_vk_import
Revises: 0015_custom_orders
Create Date: 2026-07-01

Idempotent: create_all for the new table, ADD COLUMN IF NOT EXISTS for product.
"""
from alembic import op

from app.core.database import Base
import app.models.models  # noqa: F401

revision = "0016_vk_import"
down_revision = "0015_custom_orders"
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
        Base.metadata.tables["shop_integration"],
    ])
    op.execute("ALTER TABLE product ADD COLUMN IF NOT EXISTS source VARCHAR(20)")
    op.execute("ALTER TABLE product ADD COLUMN IF NOT EXISTS external_id VARCHAR(64)")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_product_shop_source_external "
        "ON product (shop_id, source, external_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_product_shop_source_external")
    op.execute("ALTER TABLE product DROP COLUMN IF EXISTS external_id")
    op.execute("ALTER TABLE product DROP COLUMN IF EXISTS source")
    op.execute("DROP TABLE IF EXISTS shop_integration")
