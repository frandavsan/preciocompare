"""
Collector — instruments adapter calls and persists run metadata.

Public API:
    classify_error(exc) -> tuple[str, str]
        Maps an exception to (error_class, error_msg).
        error_class: 'network' | 'auth' | 'timeout' | 'parse'

    make_run_callback(query) -> Callable
        Returns a callback suitable for passing as _on_run to search_all_stores().
        The callback records one adapter_runs row per call.

    summarize_results(results) -> dict
        Extracts quality metrics from a list[ProductResult] without writing to DB.
        Used by anomaly.py to avoid duplicating the counting logic.

Error classification table:
    httpx.ConnectError / NetworkError     → 'network'
    httpx.TimeoutException                → 'timeout'
    asyncio.TimeoutError                  → 'timeout'
    httpx.HTTPStatusError 403             → 'auth'  (Cloudflare block if fingerprint present)
    httpx.HTTPStatusError other 4xx/5xx   → 'network'
    json.JSONDecodeError / ValueError /
      KeyError / AttributeError / IndexError → 'parse'
    Everything else                       → 'parse'  (safe default)
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Callable, Optional

import httpx

from ..models import ProductResult
from . import storage

logger = logging.getLogger(__name__)

# Cloudflare challenge page fingerprints (lower-cased substrings).
_CF_FINGERPRINTS = ("cloudflare", "cf-ray", "just a moment", "enable javascript")


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------


def classify_error(exc: Exception) -> tuple[str, str]:
    """
    Maps an exception to (error_class, human-readable message).
    Never raises — falls back to 'parse' for unrecognised exception types.
    """
    msg = str(exc)

    if isinstance(exc, (httpx.ConnectError, httpx.NetworkError, httpx.RemoteProtocolError)):
        return "network", msg

    if isinstance(exc, (httpx.TimeoutException, asyncio.TimeoutError)):
        return "timeout", msg

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 403:
            try:
                body = exc.response.text[:500].lower()
            except Exception:
                body = ""
            if any(fp in body for fp in _CF_FINGERPRINTS):
                return "auth", f"Cloudflare block (HTTP 403)"
            return "auth", f"HTTP 403 Forbidden"
        return "network", f"HTTP {status}: {msg}"

    if isinstance(exc, (json.JSONDecodeError, ValueError, KeyError,
                        AttributeError, IndexError, TypeError)):
        return "parse", f"{type(exc).__name__}: {msg}"

    # curl_cffi raises its own exception types that aren't httpx subclasses.
    # Classify by name so we don't hard-depend on curl_cffi being installed.
    exc_type = type(exc).__name__
    if any(t in exc_type for t in ("Connection", "Timeout", "Network", "SSL", "Cert")):
        return "network", f"{exc_type}: {msg}"

    return "parse", f"{exc_type}: {msg}"


# ---------------------------------------------------------------------------
# Result summarisation (shared logic used by collector and anomaly)
# ---------------------------------------------------------------------------


def summarize_results(results: list[ProductResult]) -> dict:
    """
    Returns a dict of quality metrics computed from a result list:
        result_count, null_price_count, zero_price_count,
        null_name_count, had_installments
    """
    null_price = sum(1 for r in results if r.price is None)
    zero_price = sum(1 for r in results if r.price is not None and r.price == 0.0)
    null_name  = sum(1 for r in results if not r.name)
    has_inst   = any(r.installments for r in results)
    return {
        "result_count":     len(results),
        "null_price_count": null_price,
        "zero_price_count": zero_price,
        "null_name_count":  null_name,
        "had_installments": has_inst,
    }


# ---------------------------------------------------------------------------
# Callback factory
# ---------------------------------------------------------------------------


def make_run_callback(query: str) -> Callable:
    """
    Returns a callback to pass as _on_run to search_all_stores().

    Callback signature (matches what core.py calls):
        (store, duration_ms, results, exc | None) -> None

    The callback is synchronous — SQLite writes are fast enough that
    blocking the event loop for < 1 ms is acceptable, consistent with
    how service.py already uses cache.py.
    """
    def _on_run(
        store: str,
        duration_ms: int,
        results: list[ProductResult],
        exc: Optional[Exception],
    ) -> None:
        try:
            error_class: Optional[str]
            error_msg: Optional[str]
            if exc is not None:
                error_class, error_msg = classify_error(exc)
            else:
                error_class = error_msg = None

            metrics = summarize_results(results)
            storage.record_run(
                store=store,
                query=query,
                duration_ms=duration_ms,
                result_count=metrics["result_count"],
                null_price_count=metrics["null_price_count"],
                zero_price_count=metrics["zero_price_count"],
                null_name_count=metrics["null_name_count"],
                had_installments=metrics["had_installments"],
                error_class=error_class,
                error_msg=error_msg,
            )
        except Exception:
            logger.debug("collector._on_run failed silently", exc_info=True)

    return _on_run
