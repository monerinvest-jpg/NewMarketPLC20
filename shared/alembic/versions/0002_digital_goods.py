"""digital goods: product_type, category.kind, digital_asset, entitlement

Revision ID: 0002_digital_goods
Revises: 0001_initial
Create Date: 2026-06-27

Adds support for digital products (instant delivery after payment):
  * product.product_type (physical|digital|course), default 'physical';
  * category.kind hint (nullable);
  * digital_asset table (private downloadable files of a digital product);
  * entitlement table (a buyer's access grant, created on payment success).

Written to be idempotent: on a fresh database 0001 already builds the full
current metadata (including these), so the column adds use IF NOT EXISTS and the
table creation uses create_all(checkfirst=True) — both no-ops when present.
"""
from alembic import op

from app.core.database import Base
import app.models.models  # noqa: F401 - registers all ORM models

revision = "0002_digital_goods"
down_revision = "0001_initial"
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
    # New columns on existing tables (the enums are stored as VARCHAR; the app
    # and Pydantic enforce valid values, so no CHECK is added here).
    op.execute("ALTER TABLE product ADD COLUMN IF NOT EXISTS product_type VARCHAR(20) NOT NULL DEFAULT 'physical'")
    op.execute("ALTER TABLE category ADD COLUMN IF NOT EXISTS kind VARCHAR(20)")
    # New tables only (checkfirst skips anything already created by 0001).
    _dedupe_indexes()
    Base.metadata.create_all(
        bind=bind,
        tables=[
            Base.metadata.tables["digital_asset"],
            Base.metadata.tables["entitlement"],
        ],
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS entitlement")
    op.execute("DROP TABLE IF EXISTS digital_asset")
    op.execute("ALTER TABLE product DROP COLUMN IF EXISTS product_type")
    op.execute("ALTER TABLE category DROP COLUMN IF EXISTS kind")
