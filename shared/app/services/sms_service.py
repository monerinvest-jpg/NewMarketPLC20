"""
SMSC.ru SMS gateway integration.

All functions are gated by the `sms_enabled` setting — when SMS is disabled in
admin, send attempts short-circuit without calling the provider. Credentials
(login/password or apikey) and sender come from settings, so they're managed
entirely from the admin panel.

API reference: https://smsc.ru/api/http/
- send:    https://smsc.ru/sys/send.php
- balance: https://smsc.ru/sys/balance.php
- status:  https://smsc.ru/sys/status.php
Responses are requested as JSON (fmt=3).
"""
from decimal import Decimal
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import SmsLog
from app.services.settings_service import get_setting

SMSC_BASE = "https://smsc.ru/sys"


async def _creds(db: AsyncSession) -> dict:
    """Read SMSC credentials/config from settings."""
    return {
        "enabled": (await get_setting(db, "sms_enabled")).lower() == "true",
        "login": await get_setting(db, "smsc_login"),
        "password": await get_setting(db, "smsc_password"),
        "sender": await get_setting(db, "smsc_sender"),
        "use_apikey": (await get_setting(db, "smsc_use_apikey")).lower() == "true",
    }


def _auth_params(creds: dict) -> dict:
    """Build auth query params: either apikey, or login+psw."""
    if creds["use_apikey"]:
        return {"apikey": creds["password"]}
    return {"login": creds["login"], "psw": creds["password"]}


async def is_enabled(db: AsyncSession) -> bool:
    return (await get_setting(db, "sms_enabled")).lower() == "true"


async def send_sms(
    db: AsyncSession,
    phone: str,
    text: str,
    purpose: str = "manual",
    *,
    force: bool = False,
) -> dict:
    """
    Send an SMS via SMSC.ru. Returns a result dict:
      {"ok": bool, "smsc_id": str|None, "cost": float|None, "count": int,
       "balance": float|None, "error": str|None}
    Logs every attempt to sms_log. When SMS is disabled and force is False,
    returns ok=False with a clear reason and does NOT log (nothing was sent).
    Caller commits.
    """
    creds = await _creds(db)
    if not creds["enabled"] and not force:
        return {"ok": False, "error": "SMS отключены в настройках", "smsc_id": None,
                "cost": None, "count": 0, "balance": None}
    if not (creds["login"] or creds["use_apikey"]) and not creds["password"]:
        return {"ok": False, "error": "Не заданы учётные данные SMSC", "smsc_id": None,
                "cost": None, "count": 0, "balance": None}

    params = {
        **_auth_params(creds),
        "phones": phone,
        "mes": text,
        "fmt": 3,            # JSON response
        "charset": "utf-8",
        "cost": 3,           # also return cost + new balance in the response
    }
    if creds["sender"]:
        params["sender"] = creds["sender"]

    result = {"ok": False, "smsc_id": None, "cost": None, "count": 1,
              "balance": None, "error": None}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{SMSC_BASE}/send.php", params=params)
            resp.raise_for_status()
            data = resp.json()
        if "error" in data:
            result["error"] = f"SMSC: {data.get('error')} (code {data.get('error_code')})"
        else:
            result["ok"] = True
            result["smsc_id"] = str(data.get("id"))
            result["count"] = int(data.get("cnt", 1) or 1)
            result["cost"] = float(data.get("cost")) if data.get("cost") is not None else None
            result["balance"] = float(data.get("balance")) if data.get("balance") is not None else None
    except Exception as e:  # noqa: BLE001
        result["error"] = f"Ошибка соединения с SMSC: {e}"

    # Log the attempt
    db.add(SmsLog(
        phone=phone,
        purpose=purpose,
        text_preview=text[:255],
        status="sent" if result["ok"] else "failed",
        smsc_id=result["smsc_id"],
        cost=Decimal(str(result["cost"])) if result["cost"] is not None else None,
        sms_count=result["count"] or 1,
        error=result["error"],
    ))
    return result


async def get_balance(db: AsyncSession) -> dict:
    """
    Query the SMSC.ru account balance. Returns {"ok", "balance", "currency", "error"}.
    Does not require sms_enabled (admin may want to check before enabling).
    """
    creds = await _creds(db)
    if not (creds["login"] or creds["use_apikey"]) and not creds["password"]:
        return {"ok": False, "balance": None, "currency": None, "error": "Не заданы учётные данные SMSC"}
    params = {**_auth_params(creds), "cur": 1, "fmt": 3}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{SMSC_BASE}/balance.php", params=params)
            resp.raise_for_status()
            data = resp.json()
        if "error" in data:
            return {"ok": False, "balance": None, "currency": None,
                    "error": f"SMSC: {data.get('error')} (code {data.get('error_code')})"}
        return {"ok": True, "balance": float(data.get("balance", 0)),
                "currency": data.get("currency", "RUB"), "error": None}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "balance": None, "currency": None, "error": f"Ошибка соединения: {e}"}


async def get_cost(db: AsyncSession, phone: str, text: str) -> dict:
    """Estimate the cost of a message without sending it (cost=1)."""
    creds = await _creds(db)
    params = {**_auth_params(creds), "phones": phone, "mes": text,
              "cost": 1, "fmt": 3, "charset": "utf-8"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{SMSC_BASE}/send.php", params=params)
            resp.raise_for_status()
            data = resp.json()
        if "error" in data:
            return {"ok": False, "cost": None, "count": None,
                    "error": f"SMSC: {data.get('error')}"}
        return {"ok": True, "cost": float(data.get("cost", 0)),
                "count": int(data.get("cnt", 1)), "error": None}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "cost": None, "count": None, "error": f"Ошибка: {e}"}
