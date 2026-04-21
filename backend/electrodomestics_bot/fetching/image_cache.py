"""
Image cache — downloads product images from CDN URLs and saves them locally.

Files are named <store>_<sku>.jpg (or <store>_<hash>.jpg when SKU is unavailable)
and overwritten on each search. Images are served by the API at /images/<filename>.
Callers receive the API-relative path (e.g. "/images/cetrogar_UN55DU7000GCZB.jpg")
stored in ProductResult.image_url.
"""

import hashlib
from pathlib import Path

import httpx

from ..config import settings

# Reuse a single client across calls — avoids repeated SSL context + pool setup.
_client = httpx.AsyncClient(timeout=10, follow_redirects=True)

# Module-level path; created once so every download_image() call skips the mkdir syscall.
images_dir: Path = Path(settings.data_dir) / "images"
images_dir.mkdir(parents=True, exist_ok=True)


def _filename(store: str, sku: str | None, cdn_url: str) -> str:
    if sku:
        safe_sku = sku.replace("/", "_").replace("\\", "_")
        return f"{store}_{safe_sku}.jpg"
    url_hash = hashlib.md5(cdn_url.encode()).hexdigest()[:10]
    return f"{store}_{url_hash}.jpg"


async def download_image(store: str, sku: str | None, cdn_url: str) -> str | None:
    """Downloads cdn_url and saves it to data/images/. Returns the API-relative
    path (/images/<filename>) on success, None on any failure."""
    filename = _filename(store, sku, cdn_url)
    try:
        resp = await _client.get(cdn_url)
        resp.raise_for_status()
        (images_dir / filename).write_bytes(resp.content)
        return f"/images/{filename}"
    except Exception:
        return None
