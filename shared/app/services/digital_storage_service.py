"""
Private storage for digital-product files.

Unlike storage_service (public images under /uploads), digital assets must NOT be
publicly reachable: only an entitled buyer may fetch them. Files are stored in a
private object-storage prefix or a private local directory (outside the /uploads
static mount). Delivery is either:
  * S3/MinIO  -> a short-lived presigned GET URL (bandwidth offloaded to storage);
  * local     -> streamed by an authenticated endpoint after an entitlement check.

The `storage_key` saved on DigitalAsset is an opaque private key (e.g.
"digital/ab12...zip"), never a public URL.
"""
import os
import uuid
from typing import Optional, Tuple

from app.core.config import settings

# Digital goods can legitimately be many formats; keep a permissive allowlist and
# fall back to a generic type. Moderation handles abuse. Executable installers are
# allowed (software is a valid digital good) — the file is never executed by us.
ALLOWED_DIGITAL_TYPES = {
    "application/pdf", "application/zip", "application/x-zip-compressed",
    "application/epub+zip", "application/x-rar-compressed", "application/x-7z-compressed",
    "application/octet-stream", "application/json", "text/plain",
    "image/jpeg", "image/png", "image/webp", "image/gif", "image/svg+xml",
    "audio/mpeg", "audio/wav", "audio/ogg",
    "video/mp4", "video/webm", "video/quicktime",
    "font/ttf", "font/otf", "application/font-sfnt",
    "application/postscript",  # .ai/.eps
    "application/vnd.android.package-archive",
}

_MAX_BYTES = getattr(settings, "MAX_DIGITAL_UPLOAD_MB", 500) * 1024 * 1024

# Local private base lives next to (not inside) the public uploads dir, so it is
# never exposed by the /uploads StaticFiles mount.
_PRIVATE_BASE = os.path.join(
    os.path.dirname(os.path.normpath(getattr(settings, "UPLOAD_DIR", "/app/uploads"))),
    "private",
)


def _safe_key(original: str) -> str:
    ext = os.path.splitext(original)[1].lower()[:12]
    return f"digital/{uuid.uuid4().hex}{ext}"


def _s3_configured() -> bool:
    return bool(
        getattr(settings, "S3_ENDPOINT", "")
        and getattr(settings, "S3_BUCKET", "")
        and getattr(settings, "S3_ACCESS_KEY", "")
    )


def _s3_client():
    import boto3  # type: ignore
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=getattr(settings, "S3_SECRET_KEY", ""),
    )


def _priv_bucket() -> str:
    """The PRIVATE bucket for digital goods / HLS / KYC. Falls back to the main
    bucket when S3_PRIVATE_BUCKET isn't configured (single-bucket mode)."""
    return getattr(settings, "S3_PRIVATE_BUCKET", "") or settings.S3_BUCKET


async def save_digital_asset(content: bytes, content_type: str, original_name: str) -> Tuple[str, int]:
    """
    Validate and persist a digital file privately. Returns (storage_key, size).
    Raises ValueError on validation failure.
    """
    size = len(content)
    if size == 0:
        raise ValueError("Файл пустой.")
    if size > _MAX_BYTES:
        raise ValueError(f"Файл слишком большой (максимум {_MAX_BYTES // (1024 * 1024)} МБ).")
    if content_type and content_type not in ALLOWED_DIGITAL_TYPES:
        # Be lenient: many tools send octet-stream; only block nothing hard here,
        # but normalise unknown types so we still store them.
        content_type = "application/octet-stream"

    key = _safe_key(original_name)

    if _s3_configured():
        try:
            _s3_client().put_object(
                Bucket=_priv_bucket(), Key=key, Body=content,
                ContentType=content_type or "application/octet-stream",
            )
            return key, size
        except Exception:
            pass  # fall through to local on storage error
    _save_local(content, key)
    return key, size


def _save_local(content: bytes, key: str) -> None:
    path = os.path.join(_PRIVATE_BASE, key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)


def local_path(key: str) -> str:
    """Absolute path of a privately stored digital file (local mode)."""
    return os.path.join(_PRIVATE_BASE, key)


def save_bytes(key: str, content: bytes, content_type: str = "application/octet-stream") -> None:
    """Store raw bytes at a SPECIFIC private key (used by the HLS packager for
    playlists/segments/keys). S3 when configured, else local."""
    if _s3_configured():
        try:
            _s3_client().put_object(Bucket=_priv_bucket(), Key=key, Body=content, ContentType=content_type)
            return
        except Exception:
            pass
    path = os.path.join(_PRIVATE_BASE, key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)


def read_bytes(key: str) -> Optional[bytes]:
    """Read a privately stored object's bytes (for gated proxy serving / packaging)."""
    if _s3_configured():
        try:
            obj = _s3_client().get_object(Bucket=_priv_bucket(), Key=key)
            return obj["Body"].read()
        except Exception:
            return None
    path = os.path.join(_PRIVATE_BASE, key)
    if os.path.isfile(path):
        with open(path, "rb") as f:
            return f.read()
    return None


def presigned_url(key: str, file_name: str, expires: int = 300) -> Optional[str]:
    """Short-lived presigned GET URL forcing an attachment download. S3 only."""
    if not _s3_configured():
        return None
    try:
        return _s3_client().generate_presigned_url(
            "get_object",
            Params={
                "Bucket": _priv_bucket(),
                "Key": key,
                "ResponseContentDisposition": f'attachment; filename="{file_name}"',
            },
            ExpiresIn=expires,
        )
    except Exception:
        return None


def delete_digital_asset(key: str) -> None:
    """Best-effort removal of a stored digital file."""
    if _s3_configured():
        try:
            _s3_client().delete_object(Bucket=_priv_bucket(), Key=key)
            return
        except Exception:
            pass
    try:
        p = local_path(key)
        if os.path.isfile(p):
            os.remove(p)
    except Exception:
        pass
