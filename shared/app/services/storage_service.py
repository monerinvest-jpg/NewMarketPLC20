"""
Storage service. Abstracts file uploads behind a simple interface: when S3/MinIO
is configured (via settings) files go to object storage; otherwise they're saved
to a local uploads directory and served as static files. Includes basic
validation (type + size) and a safe filename.
"""
import os
import uuid
from typing import Optional

from app.core.config import settings

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

LOCAL_UPLOAD_DIR = getattr(settings, "UPLOAD_DIR", os.path.join(os.getcwd(), "uploads"))


def _safe_name(original: str) -> str:
    ext = os.path.splitext(original)[1].lower()[:10]
    return f"{uuid.uuid4().hex}{ext}"


def _s3_configured() -> bool:
    return bool(
        getattr(settings, "S3_ENDPOINT", "")
        and getattr(settings, "S3_BUCKET", "")
        and getattr(settings, "S3_ACCESS_KEY", "")
    )


async def save_file(content: bytes, content_type: str, original_name: str) -> str:
    """
    Validate and persist a file, returning a public URL. Uses S3/MinIO when
    configured, otherwise the local uploads directory.
    Raises ValueError on validation failure.
    """
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError("Недопустимый тип файла. Разрешены JPEG, PNG, WEBP, GIF.")
    if len(content) > MAX_FILE_SIZE:
        raise ValueError("Файл слишком большой (максимум 5 МБ).")

    filename = _safe_name(original_name)

    if _s3_configured():
        return await _save_s3(content, content_type, filename)
    return _save_local(content, filename)


def _save_local(content: bytes, filename: str) -> str:
    os.makedirs(LOCAL_UPLOAD_DIR, exist_ok=True)
    path = os.path.join(LOCAL_UPLOAD_DIR, filename)
    with open(path, "wb") as f:
        f.write(content)
    # Served via the /uploads static mount (configured in main.py)
    return f"/uploads/{filename}"


async def _save_s3(content: bytes, content_type: str, filename: str) -> str:
    """
    Upload to S3/MinIO. boto3 is imported lazily so the dependency is only
    needed when object storage is actually configured.
    """
    try:
        import boto3  # type: ignore
    except ImportError:
        # Fall back to local if the dependency isn't installed
        return _save_local(content, filename)

    client = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=getattr(settings, "S3_SECRET_KEY", ""),
    )
    client.put_object(
        Bucket=settings.S3_BUCKET,
        Key=filename,
        Body=content,
        ContentType=content_type,
        # Product images are public; the bucket is otherwise private (digital
        # goods stay private and are served via presigned URLs / gated proxy).
        ACL="public-read",
    )
    public_base = getattr(settings, "S3_PUBLIC_URL", "").rstrip("/")
    if public_base:
        return f"{public_base}/{filename}"
    return f"{settings.S3_ENDPOINT.rstrip('/')}/{settings.S3_BUCKET}/{filename}"
