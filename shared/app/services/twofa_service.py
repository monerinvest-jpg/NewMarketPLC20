"""
Two-factor authentication (TOTP) service.

Implements RFC 6238 TOTP without external dependencies (uses stdlib hmac/hashlib),
so it works even if pyotp isn't installed. Provides secret generation, the
otpauth:// provisioning URI, code verification with a small time window, and
single-use hashed backup codes.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import struct
import time
from urllib.parse import quote

from app.core.security import get_password_hash, verify_password

_B32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"


def generate_secret() -> str:
    """Generate a random base32 TOTP secret."""
    raw = os.urandom(20)
    return base64.b32encode(raw).decode("utf-8").rstrip("=")


def get_otpauth_url(secret: str, email: str, issuer: str = "Marketplace") -> str:
    """Build the otpauth:// URI for QR codes / authenticator apps."""
    label = quote(f"{issuer}:{email}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}"


def _hotp(secret: str, counter: int) -> str:
    # Pad base32 secret and decode
    padding = "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(secret + padding, casefold=True)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(binary % 1_000_000).zfill(6)


def verify_code(secret: str, code: str, window: int = 1) -> bool:
    """Verify a TOTP code, allowing +/- `window` 30-second steps for clock skew."""
    if not code or not code.isdigit():
        return False
    counter = int(time.time()) // 30
    for delta in range(-window, window + 1):
        if hmac.compare_digest(_hotp(secret, counter + delta), code.zfill(6)):
            return True
    return False


def generate_backup_codes(n: int = 8) -> list[str]:
    """Generate n human-friendly single-use backup codes."""
    return [f"{secrets.randbelow(10**8):08d}" for _ in range(n)]


def hash_backup_codes(codes: list[str]) -> str:
    """Hash backup codes for storage (JSON list of bcrypt hashes)."""
    return json.dumps([get_password_hash(c) for c in codes])


def consume_backup_code(stored_json: str | None, code: str) -> tuple[bool, str | None]:
    """
    Check `code` against stored hashed backup codes. If it matches, return
    (True, new_stored_json_without_that_code). Otherwise (False, stored_json).
    """
    if not stored_json:
        return False, stored_json
    try:
        hashes = json.loads(stored_json)
    except Exception:
        return False, stored_json
    for h in hashes:
        if verify_password(code, h):
            hashes.remove(h)
            return True, json.dumps(hashes)
    return False, stored_json
