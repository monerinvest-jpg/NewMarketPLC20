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

    # Optimise raster images to WebP off the event loop (best-effort; raw bytes
    # come back unchanged for SVG/GIF or on any failure).
    import asyncio
    from app.services import image_service
    content, content_type, ext = await asyncio.to_thread(image_service.optimize, content, content_type)
    filename = f"{uuid.uuid4().hex}{ext}"

    if _s3_configured():
        return await _save_s3(content, content_type, filename)
    return _save_local(content, filename)


ALLOWED_VIDEO_TYPES = {"video/mp4", "video/webm", "video/quicktime"}
MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50 MB — short review clips


async def save_public_media(content: bytes, content_type: str, original_name: str) -> tuple[str, str]:
    """
    Persist a PUBLIC image or short video (e.g. a customer review photo/video).
    Images are optimised to WebP; videos are stored as-is. Returns (url, media_type)
    where media_type is 'image' | 'video'. Raises ValueError on validation failure.
    """
    ctype = (content_type or "").lower()
    if ctype in ALLOWED_VIDEO_TYPES:
        if len(content) > MAX_VIDEO_SIZE:
            raise ValueError(f"Видео слишком большое (максимум {MAX_VIDEO_SIZE // (1024 * 1024)} МБ).")
        ext = {"video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov"}.get(ctype, ".mp4")
        filename = f"{uuid.uuid4().hex}{ext}"
        if _s3_configured():
            return await _save_s3(content, ctype, filename), "video"
        return _save_local(content, filename), "video"
    # Fall back to the image path (validates + optimises to WebP).
    url = await save_file(content, content_type, original_name)
    return url, "image"


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
