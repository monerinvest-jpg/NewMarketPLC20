"""
Thin async client for the VK API — OAuth (seller authorization) + market.*
methods used by the VK Market import.

Auth flow (classic web OAuth; enough for scaffold/testing — if the registered
VK app is VK-ID-only, swap the two URL builders for id.vk.com + PKCE, the rest
of this module stays the same):
  1. build_auth_url(state)  -> seller's browser goes to oauth.vk.com/authorize
  2. VK redirects to VK_REDIRECT_URI?code=...&state=...
  3. exchange_code(code)    -> {access_token, user_id, ...}

Rate limits: VK allows ~3 req/s per token — the import task sleeps between
pages, and preview requests are small.
"""
from typing import Any, Optional
from urllib.parse import urlencode

import httpx

from app.core.config import settings

OAUTH_BASE = "https://oauth.vk.com"
API_BASE = "https://api.vk.com/method"
SCOPE = "market,groups,offline"


class VkApiError(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        super().__init__(f"VK API error {code}: {message}")


def configured() -> bool:
    return bool(settings.VK_APP_ID and settings.VK_APP_SECRET and settings.VK_REDIRECT_URI)


def build_auth_url(state: str) -> str:
    """URL the seller opens to grant us market+groups access."""
    return OAUTH_BASE + "/authorize?" + urlencode({
        "client_id": settings.VK_APP_ID,
        "redirect_uri": settings.VK_REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "state": state,
        "v": settings.VK_API_VERSION,
        "display": "page",
    })


async def exchange_code(code: str) -> dict:
    """Exchange the OAuth code for an access token (server-side, uses the secret)."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(OAUTH_BASE + "/access_token", params={
            "client_id": settings.VK_APP_ID,
            "client_secret": settings.VK_APP_SECRET,
            "redirect_uri": settings.VK_REDIRECT_URI,
            "code": code,
        })
        data = resp.json()
    if "error" in data:
        raise VkApiError(0, f"{data.get('error')}: {data.get('error_description')}")
    return data  # {access_token, expires_in, user_id}


async def api_call(method: str, token: str, **params: Any) -> Any:
    """GET api.vk.com/method/<method>; raises VkApiError on an error payload."""
    params = {k: v for k, v in params.items() if v is not None}
    params.update({"access_token": token, "v": settings.VK_API_VERSION})
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{API_BASE}/{method}", params=params)
        data = resp.json()
    if "error" in data:
        err = data["error"]
        raise VkApiError(err.get("error_code", 0), err.get("error_msg", "unknown"))
    return data.get("response")


async def get_admin_communities(token: str) -> list[dict]:
    """Communities the seller administers (candidates for import)."""
    resp = await api_call("groups.get", token, filter="admin", extended=1, count=100)
    return [
        {"id": g["id"], "name": g.get("name", ""), "screen_name": g.get("screen_name", "")}
        for g in (resp or {}).get("items", [])
    ]


async def get_market_page(token: str, community_id: int, offset: int = 0, count: int = 200) -> tuple[list[dict], int]:
    """One page of the community's market items. Returns (items, total)."""
    resp = await api_call(
        "market.get", token,
        owner_id=-abs(int(community_id)),  # communities are negative owner ids
        offset=offset, count=min(count, 200), extended=1,
    )
    resp = resp or {}
    return resp.get("items", []), resp.get("count", 0)


def best_photo_url(item: dict) -> Optional[str]:
    """Largest photo URL of a market item (photos[0].sizes -> max width)."""
    photos = item.get("photos") or []
    if not photos:
        return None
    sizes = photos[0].get("sizes") or []
    if not sizes:
        return None
    return max(sizes, key=lambda s: s.get("width", 0)).get("url")


def all_photo_urls(item: dict, limit: int = 5) -> list[str]:
    urls = []
    for photo in (item.get("photos") or [])[:limit]:
        sizes = photo.get("sizes") or []
        if sizes:
            urls.append(max(sizes, key=lambda s: s.get("width", 0)).get("url"))
    return [u for u in urls if u]
