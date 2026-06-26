"""
Shared rate limiter instance, kept in its own module so both the service
factory and the auth endpoints can import it without a circular dependency.

Two things matter for this to actually work in production:

1. Real client IP behind the gateway. Every service runs behind Kong/nginx, so
   `request.client.host` is the gateway's address — keying on it would lump all
   users into a single bucket. We read the first hop of `X-Forwarded-For`
   instead (the same source IP logic the YooKassa webhook uses).

2. Shared counters across replicas. Each service is horizontally scaled, so an
   in-memory limiter would count per-process and let N replicas allow N× the
   limit. We point slowapi at Redis so all replicas share one counter. If
   REDIS_URL is unreachable, slowapi falls back to in-memory automatically.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.core.config import settings


def client_ip(request: Request) -> str:
    """Real client IP: first hop of X-Forwarded-For, else the socket peer."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(
    key_func=client_ip,
    default_limits=[],
    storage_uri=settings.REDIS_URL,
)
