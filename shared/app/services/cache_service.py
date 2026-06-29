"""
Lightweight Redis cache for hot read paths (categories, currency rates, homepage).

Design goals:
  * Transparent fallback — if Redis is down or CACHE_ENABLED is false, reads go
    straight to the source and writes are no-ops. Caching must never break a request.
  * JSON values only (with Decimal support), so cached payloads are exactly what
    the API returns. Don't cache ORM objects.
  * Namespaced keys so a whole group can be invalidated on mutation.
"""
import json
import logging
from decimal import Decimal
from functools import wraps
from typing import Any, Callable, Optional

from app.core.config import settings

logger = logging.getLogger("marketplace.cache")

_client = None
_unavailable = False


def _get_client():
    """Lazily create a redis.asyncio client; returns None if caching is off/broken."""
    global _client, _unavailable
    if not settings.CACHE_ENABLED or _unavailable:
        return None
    if _client is None:
        try:
            import redis.asyncio as aioredis  # type: ignore
            _client = aioredis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cache disabled — cannot init Redis: %s", exc)
            _unavailable = True
            return None
    return _client


class _JSONEnc(json.JSONEncoder):
    def default(self, o: Any):
        if isinstance(o, Decimal):
            return str(o)
        return super().default(o)


async def cache_get(key: str) -> Optional[Any]:
    client = _get_client()
    if client is None:
        return None
    try:
        raw = await client.get(key)
        return json.loads(raw) if raw is not None else None
    except Exception:  # noqa: BLE001 — cache misses must be silent
        return None


async def cache_set(key: str, value: Any, ttl: Optional[int] = None) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        await client.set(key, json.dumps(value, cls=_JSONEnc), ex=ttl or settings.CACHE_DEFAULT_TTL)
    except Exception:  # noqa: BLE001
        pass


async def cache_delete(*keys: str) -> None:
    client = _get_client()
    if client is None or not keys:
        return
    try:
        await client.delete(*keys)
    except Exception:  # noqa: BLE001
        pass


async def invalidate_prefix(prefix: str) -> None:
    """Delete every key under a namespace (e.g. 'categories:'). Uses SCAN."""
    client = _get_client()
    if client is None:
        return
    try:
        async for k in client.scan_iter(match=f"{prefix}*", count=200):
            await client.delete(k)
    except Exception:  # noqa: BLE001
        pass


def cached(prefix: str, ttl: Optional[int] = None, key: Callable[..., str] = lambda *a, **k: ""):
    """Cache an async function returning JSON-able data. `key` builds the suffix
    from the call args (default: single shared key under the prefix)."""
    def decorator(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            ck = f"{prefix}:{key(*args, **kwargs)}"
            hit = await cache_get(ck)
            if hit is not None:
                return hit
            result = await fn(*args, **kwargs)
            await cache_set(ck, result, ttl)
            return result
        return wrapper
    return decorator
