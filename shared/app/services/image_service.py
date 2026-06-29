"""
Image optimisation: downscale + re-encode raster uploads to WebP, which cuts
payload size dramatically (typically 60–80%) with no visible quality loss.

Used by storage_service on upload. Vector/animated formats (SVG/GIF) are passed
through untouched. Fully best-effort: if Pillow is missing or an image can't be
processed, the original bytes are returned so uploads never fail because of this.
"""
import io
import logging
from typing import Tuple

logger = logging.getLogger("marketplace.image")

# Formats we re-encode to WebP. SVG (vector) and GIF (often animated) are left alone.
_OPTIMIZABLE = {"image/jpeg", "image/jpg", "image/png", "image/webp"}

MAX_DIMENSION = 1600   # longest side, px — plenty for product photos
WEBP_QUALITY = 82
THUMB_DIMENSION = 320


def optimize(content: bytes, content_type: str) -> Tuple[bytes, str, str]:
    """
    Return (new_bytes, new_content_type, extension) for a raster image, re-encoded
    to WebP and downscaled to MAX_DIMENSION. Non-raster or failures pass through
    with their original type (extension derived from the content type).
    """
    if (content_type or "").lower() not in _OPTIMIZABLE:
        return content, content_type, _ext_for(content_type)
    try:
        from PIL import Image  # type: ignore
        img = Image.open(io.BytesIO(content))
        img = _flatten(img)
        img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="WEBP", quality=WEBP_QUALITY, method=4)
        return out.getvalue(), "image/webp", ".webp"
    except Exception as exc:  # noqa: BLE001 — never block an upload on optimisation
        logger.warning("Image optimisation skipped: %s", exc)
        return content, content_type, _ext_for(content_type)


def make_thumbnail(content: bytes) -> bytes | None:
    """A small square-ish WebP thumbnail (for grids/lists). None on failure."""
    try:
        from PIL import Image  # type: ignore
        img = _flatten(Image.open(io.BytesIO(content)))
        img.thumbnail((THUMB_DIMENSION, THUMB_DIMENSION), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="WEBP", quality=80, method=4)
        return out.getvalue()
    except Exception:  # noqa: BLE001
        return None


def _flatten(img):
    """Drop alpha onto white when needed so WebP encodes cleanly from PNG/RGBA."""
    if img.mode in ("RGBA", "LA", "P"):
        from PIL import Image  # type: ignore
        bg = Image.new("RGB", img.size, (255, 255, 255))
        rgba = img.convert("RGBA")
        bg.paste(rgba, mask=rgba.split()[-1])
        return bg
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def _ext_for(content_type: str) -> str:
    return {
        "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png",
        "image/webp": ".webp", "image/gif": ".gif", "image/svg+xml": ".svg",
    }.get((content_type or "").lower(), ".bin")
