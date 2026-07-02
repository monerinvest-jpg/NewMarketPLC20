"""
Shared base for the model modules: common imports, the Enum wrapper
(native_enum=False everywhere) and utcnow. Star-imported by every domain
module — keeps the split files as close to the original single-file layout
as possible.
"""
import enum
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, Enum as _SAEnum, ForeignKey, Index,
    Integer, Numeric, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def Enum(*args, **kwargs):
    """Enum column that is stored as a VARCHAR + CHECK constraint rather than a
    native database enum type.

    PostgreSQL native enums are painful here: several enums (CurrencyCode,
    ReferralType, DiscountType) are reused across tables, which would emit
    duplicate ``CREATE TYPE`` statements, and adding a value later requires
    ``ALTER TYPE`` outside a transaction. ``native_enum=False`` keeps the same
    string values while being fully portable between PostgreSQL and MySQL.
    """
    kwargs.setdefault("native_enum", False)
    return _SAEnum(*args, **kwargs)


def utcnow():
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────
