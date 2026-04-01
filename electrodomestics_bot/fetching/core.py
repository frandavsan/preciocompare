import asyncio
import logging
import re
import time
import unicodedata
import warnings
from typing import Callable, Optional

import httpx

from ..models import ProductResult

logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore", ".*SSL.*")
warnings.filterwarnings("ignore", ".*ssl.*")
warnings.filterwarnings("ignore", ".*certificate.*")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
}

# Module-level clients — instantiated once, reused across all requests.
# httpx.AsyncClient can be created at module level; I/O only requires an event loop.
_client = httpx.AsyncClient(headers=HEADERS, verify=True, timeout=25)
_client_no_ssl = httpx.AsyncClient(headers=HEADERS, verify=False, timeout=25)


def get_client(verify_ssl: bool = True) -> httpx.AsyncClient:
    return _client if verify_ssl else _client_no_ssl


async def http_get(url: str, verify_ssl: bool = True) -> httpx.Response:
    resp = await get_client(verify_ssl).get(url)
    resp.raise_for_status()
    return resp


async def http_post(url: str, verify_ssl: bool = True, **kwargs) -> httpx.Response:
    """POST using the shared client. SSL is baked into the client; do not pass verify= in kwargs."""
    return await get_client(verify_ssl).post(url, **kwargs)


def _normalize(s: str) -> str:
    """Lowercases and strips Unicode combining marks (accents) from a string."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s.lower())
        if unicodedata.category(c) != "Mn"
    )


def matches_query(product_name: str, query: str) -> bool:
    """
    Returns True only if every word in the query appears in the product name.
    Both sides are normalized (lowercased, accent-stripped, spaces collapsed) so
    that e.g. '512gb' matches '512 Gb' and 'televisión' matches 'Televisor'.
    Short tokens (≤2 chars) require a word-boundary match to avoid false positives
    (e.g. "A" matching every product, "TV" matching "VTEX").
    """
    norm_name = _normalize(product_name)
    name_compact = re.sub(r"\s+", "", norm_name)
    name_spaced = norm_name
    for word in query.split():
        w = re.sub(r"\s+", "", _normalize(word))
        if len(w) <= 2:
            if not re.search(rf"\b{re.escape(w)}\b", name_spaced):
                return False
        else:
            if w not in name_compact:
                return False
    return True


async def search_all_stores(
    query: str,
    adapters: list,
    detail: bool = False,
    check_shipping: bool = True,
    on_run: Optional[Callable] = None,
) -> dict[str, list[ProductResult]]:
    """
    Queries every store concurrently and returns filtered results per store.
    Stores that fail are logged and returned as empty lists.
    Result order matches the order of the adapters list.
    When detail=True, adapters may perform extra requests for richer data (e.g. card names).
    When check_shipping=False, all shipping simulation calls are skipped and free_shipping
    is forced to False for every product.

    on_run: optional callback invoked once per adapter after each call completes.
             Signature: (store: str, duration_ms: int, results: list[ProductResult],
                         exc: Exception | None) -> None
             Exceptions from on_run are suppressed — monitoring never crashes a search.
    """
    for adapter in adapters:
        if check_shipping:
            if hasattr(adapter, "postal_code"):
                adapter.postal_code = "1428"
        else:
            if hasattr(adapter, "_free_shipping_override"):
                adapter._free_shipping_override = False

    async def _fetch(adapter):
        t0 = time.perf_counter()
        exc_captured: Optional[Exception] = None
        results: list[ProductResult] = []
        try:
            raw = await adapter.search(query, detail)
            results = [r for r in raw if r.name and matches_query(r.name, query)]
        except Exception as e:
            logger.warning("%s failed — %s", adapter.name, e)
            exc_captured = e
        finally:
            if on_run is not None:
                try:
                    on_run(
                        adapter.name,
                        int((time.perf_counter() - t0) * 1000),
                        results,
                        exc_captured,
                    )
                except Exception:
                    pass
        return adapter.name, results

    pairs = await asyncio.gather(*[_fetch(a) for a in adapters])
    results = dict(pairs)

    if not check_shipping:
        for store_results in results.values():
            for product in store_results:
                product.free_shipping = False

    return results
