"""
Slug generation with Cyrillic-to-Latin transliteration for SEO-friendly URLs.
"""
import re

_TRANSLIT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '',
    'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
}


def slugify(text: str, max_length: int = 80) -> str:
    """Convert text to a URL-safe slug, transliterating Cyrillic to Latin."""
    text = (text or "").lower().strip()
    out = []
    for ch in text:
        if ch in _TRANSLIT:
            out.append(_TRANSLIT[ch])
        elif ch.isalnum() and ch.isascii():
            out.append(ch)
        elif ch in (' ', '-', '_'):
            out.append('-')
    slug = ''.join(out)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug[:max_length] or "item"


def product_slug(title: str, product_id: int) -> str:
    """Build a product slug suffixed with its id for uniqueness."""
    return f"{slugify(title)}-{product_id}"
