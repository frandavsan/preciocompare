"""
Anomaly detector — inspects live result sets for data quality issues.

Public API:
    check(query, results) -> list[dict]
        Inspects a {store: [ProductResult]} dict returned by a live fetch.
        Persists any anomalies found to monitoring.db and returns them as a list
        so callers can log or act on them.

Anomaly types and when they fire:
    all_prices_null         — every result has price=None                   (critical)
    price_dropped_to_zero   — every result has price=0.0                    (critical)
    zero_results            — 0 results and historical avg > 0              (warning)
    result_count_drop       — count < 30 % of 7-day avg (min 3 samples)    (warning)
    installments_disappeared— store normally has installments but none now  (warning)
    high_null_price_fraction— > 25 % of results have null price             (warning)

Historical checks (zero_results, result_count_drop, installments_disappeared)
are skipped when fewer than MIN_HISTORY_SAMPLES successful runs exist for
the same (store, query) — avoids false positives on new stores or new queries.
"""

from __future__ import annotations

import logging
from typing import Optional

from ..models import ProductResult
from . import storage
from .collector import summarize_results

logger = logging.getLogger(__name__)

# Minimum historical runs required before enabling average-based checks.
MIN_HISTORY_SAMPLES = 3

# Fraction of 7-day average below which result_count_drop fires.
RESULT_COUNT_DROP_THRESHOLD = 0.30

# Fraction of results with null price above which high_null_price_fraction fires.
NULL_PRICE_FRACTION_THRESHOLD = 0.25

# Fraction of historical runs that had installments above which
# installments_disappeared fires when current run has none.
INSTALLMENTS_EXPECTED_THRESHOLD = 0.60


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _historical_stats(store: str, query: str) -> Optional[dict]:
    """
    Returns {'avg_count': float, 'inst_fraction': float, 'sample_count': int}
    from the last 7 days of successful runs, or None if below MIN_HISTORY_SAMPLES.
    """
    history = storage.get_run_history(store, query, days=7)
    if len(history) < MIN_HISTORY_SAMPLES:
        return None
    avg_count    = sum(r["result_count"]     for r in history) / len(history)
    inst_fraction = sum(r["had_installments"] for r in history) / len(history)
    return {
        "avg_count":      avg_count,
        "inst_fraction":  inst_fraction,
        "sample_count":   len(history),
    }


def _emit(anomalies: list[dict], store: str, query: str,
          severity: str, anomaly_type: str, details: dict) -> None:
    """Records to DB and appends to the in-memory list."""
    try:
        storage.record_anomaly(store, query, severity, anomaly_type, details)
    except Exception:
        logger.debug("anomaly.record failed silently", exc_info=True)
    anomalies.append({
        "store": store, "query": query,
        "severity": severity, "anomaly_type": anomaly_type,
        "details": details,
    })


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check(
    query: str,
    results: dict[str, list[ProductResult]],
) -> list[dict]:
    """
    Inspect a live result set for quality anomalies.

    Returns a list of anomaly dicts (may be empty). Anomalies are also
    persisted to monitoring.db. Never raises — all exceptions are caught
    so monitoring never disrupts the main search path.
    """
    found: list[dict] = []
    try:
        _check_inner(query, results, found)
    except Exception:
        logger.debug("anomaly.check failed silently", exc_info=True)
    return found


def _check_inner(
    query: str,
    results: dict[str, list[ProductResult]],
    anomalies: list[dict],
) -> None:
    for store, products in results.items():
        metrics = summarize_results(products)
        count   = metrics["result_count"]

        # --- Checks that require at least 1 result ---

        if count > 0:
            # All prices null → extraction is completely broken.
            if metrics["null_price_count"] == count:
                _emit(anomalies, store, query, "critical", "all_prices_null", {
                    "result_count": count,
                })

            # All prices zero → price field maps to wrong API key.
            elif metrics["zero_price_count"] == count:
                _emit(anomalies, store, query, "critical", "price_dropped_to_zero", {
                    "result_count": count,
                })

            # High fraction of null prices (but not all) — partial extraction failure.
            elif count >= 4:
                null_fraction = metrics["null_price_count"] / count
                if null_fraction > NULL_PRICE_FRACTION_THRESHOLD:
                    _emit(anomalies, store, query, "warning", "high_null_price_fraction", {
                        "null_price_count": metrics["null_price_count"],
                        "result_count": count,
                        "fraction": round(null_fraction, 2),
                    })

        # --- History-based checks (require enough past samples) ---

        hist = _historical_stats(store, query)
        if hist is None:
            # Not enough history — skip average-based checks.
            continue

        avg   = hist["avg_count"]
        inst_f = hist["inst_fraction"]

        if count == 0 and avg > 0:
            _emit(anomalies, store, query, "warning", "zero_results", {
                "historical_avg": round(avg, 1),
                "samples": hist["sample_count"],
            })

        elif count > 0 and avg > 0:
            drop_ratio = count / avg
            if drop_ratio < RESULT_COUNT_DROP_THRESHOLD:
                _emit(anomalies, store, query, "warning", "result_count_drop", {
                    "current_count": count,
                    "historical_avg": round(avg, 1),
                    "ratio": round(drop_ratio, 2),
                    "samples": hist["sample_count"],
                })

        # Installments disappeared: store normally returns them but this run has none.
        if (
            count > 0
            and not metrics["had_installments"]
            and inst_f >= INSTALLMENTS_EXPECTED_THRESHOLD
        ):
            _emit(anomalies, store, query, "warning", "installments_disappeared", {
                "historical_inst_fraction": round(inst_f, 2),
                "samples": hist["sample_count"],
            })
