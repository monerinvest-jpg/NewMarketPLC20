"""
Currency service. Prices are stored in the base currency (RUB); this converts
to display currencies using admin-managed rates from the currency_rate table.
"""
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import CurrencyRate


# Sensible fallback rates/symbols used when the DB has no row yet.
DEFAULT_RATES = {
    "RUB": {"rate": Decimal("1.000000"), "symbol": "₽"},
    "USD": {"rate": Decimal("0.011000"), "symbol": "$"},
    "EUR": {"rate": Decimal("0.010000"), "symbol": "€"},
}


async def get_rates(db: AsyncSession) -> dict:
    """Return all known currency rates, merging DB rows over defaults."""
    rows = (await db.execute(select(CurrencyRate))).scalars().all()
    result = {code: {"rate": d["rate"], "symbol": d["symbol"]} for code, d in DEFAULT_RATES.items()}
    for r in rows:
        result[r.code.value] = {"rate": r.rate, "symbol": r.symbol}
    return result


async def convert(amount_rub: Decimal, code: str, db: AsyncSession) -> Decimal:
    """Convert a base-currency (RUB) amount to the target currency."""
    rates = await get_rates(db)
    rate = rates.get(code, {}).get("rate", Decimal("1"))
    return (amount_rub * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
