"""
Moderation service. Computes auto-flags and a priority score for pending
products so moderators can triage the queue. Heuristics are intentionally
conservative — they raise attention, they don't auto-reject.
"""
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Product, ProductStatus

# Words that commonly indicate prohibited or scam listings (RU + EN samples).
STOP_WORDS = [
    "оружие", "наркотик", "взрывчат", "поддельн", "контрафакт",
    "реплика", "фальшив", "weapon", "drugs", "counterfeit", "fake",
]


async def compute_flags(
    product: Product,
    db: AsyncSession,
    avg_category_price: Optional[Decimal] = None,
) -> list[str]:
    """
    Return a list of human-readable flag reasons for a product. Empty list means
    nothing suspicious was detected by the heuristics.
    """
    flags: list[str] = []
    text = f"{product.title} {product.description or ''}".lower()

    # 1) Stop-words in title/description
    hit = [w for w in STOP_WORDS if w in text]
    if hit:
        flags.append(f"Стоп-слова: {', '.join(hit)}")

    # 2) Duplicate title within the same shop (possible spam re-listing)
    dup_count = (await db.execute(
        select(func.count()).select_from(Product).where(
            Product.shop_id == product.shop_id,
            Product.title == product.title,
            Product.id != product.id,
        )
    )).scalar_one()
    if dup_count > 0:
        flags.append(f"Дубликат названия ({dup_count})")

    # 3) Anomalous price vs category average (>5x or <1/5x)
    if avg_category_price and avg_category_price > 0:
        ratio = product.price / avg_category_price
        if ratio > 5:
            flags.append("Цена аномально высокая для категории")
        elif ratio < Decimal("0.2"):
            flags.append("Цена аномально низкая для категории")

    # 4) Suspiciously empty listing
    if not product.description or len(product.description.strip()) < 10:
        flags.append("Очень короткое описание")

    return flags


def priority_from_flags(flags: list[str], created_at) -> int:
    """
    Higher priority = review sooner. Stop-words dominate; otherwise more flags
    and older submissions rank higher.
    """
    score = 0
    for f in flags:
        if f.startswith("Стоп-слова"):
            score += 100
        elif "аномально" in f:
            score += 30
        elif "Дубликат" in f:
            score += 20
        else:
            score += 5
    return score


async def category_avg_price(db: AsyncSession, category_id: int) -> Optional[Decimal]:
    """Average price of active products in a category (for anomaly detection)."""
    avg = (await db.execute(
        select(func.avg(Product.price)).where(
            Product.category_id == category_id,
            Product.status == ProductStatus.active,
        )
    )).scalar_one()
    return Decimal(str(avg)) if avg is not None else None
