"""
Monitoring storage layer — manages data/monitoring.db.

Separate from data/cache.db so monitoring writes never interfere with
product data reads. Schema versioning follows the same pattern as cache.py:
bump SCHEMA_VERSION, add a new entry to MIGRATIONS, and run_migrations()
applies any pending ones on every DB open.

Public write API (called by collector and anomaly modules):
    record_run(store, query, duration_ms, result_count, null_price_count,
               zero_price_count, null_name_count, had_installments,
               error_class, error_msg) -> None
    record_anomaly(store, query, severity, anomaly_type, details) -> None
    record_canary_run(store, query, expected_min, actual_count, passed,
                      duration_ms, failure_reason) -> None
    record_refresh_run(started_at, finished_at, stores_attempted,
                       stores_succeeded, total_products_updated,
                       total_queries_attempted, total_queries_failed,
                       details) -> None

Public read API (called by anomaly module and /health endpoint):
    get_run_history(store, query, days) -> list[dict]
    get_open_anomalies() -> list[dict]
    get_last_canary_per_store() -> dict[str, dict]
    get_last_refresh() -> dict | None
    get_db_size_mb() -> float
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# Path and version
# ---------------------------------------------------------------------------

_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.path.join(_PROJECT_ROOT, "data", "monitoring.db")

SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------
# Migrations
# Each key is an integer version; the value is a list of SQL statements
# executed in order inside a single transaction when upgrading to that version.
# ---------------------------------------------------------------------------

MIGRATIONS: dict[int, list[str]] = {
    1: [
        """
        CREATE TABLE schema_version (
            version    INTEGER NOT NULL,
            applied_at TEXT    NOT NULL
        )
        """,
        # One row per live adapter call. Used for historical baseline computation
        # (7-day averages) and error-rate analysis.
        """
        CREATE TABLE adapter_runs (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            store            TEXT    NOT NULL,
            query            TEXT    NOT NULL,
            timestamp        TEXT    NOT NULL,
            duration_ms      INTEGER,
            result_count     INTEGER NOT NULL DEFAULT 0,
            null_price_count INTEGER NOT NULL DEFAULT 0,
            zero_price_count INTEGER NOT NULL DEFAULT 0,
            null_name_count  INTEGER NOT NULL DEFAULT 0,
            had_installments INTEGER NOT NULL DEFAULT 0,
            error_class      TEXT,
            error_msg        TEXT
        )
        """,
        "CREATE INDEX idx_ar_store_query_ts ON adapter_runs(store, query, timestamp)",
        "CREATE INDEX idx_ar_store_ts       ON adapter_runs(store, timestamp)",
        # Anomalies raised during result inspection or canary runs.
        """
        CREATE TABLE anomalies (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            store        TEXT    NOT NULL,
            query        TEXT    NOT NULL,
            timestamp    TEXT    NOT NULL,
            severity     TEXT    NOT NULL,
            anomaly_type TEXT    NOT NULL,
            details      TEXT,
            acknowledged INTEGER NOT NULL DEFAULT 0
        )
        """,
        "CREATE INDEX idx_anom_store_ts ON anomalies(store, timestamp)",
        "CREATE INDEX idx_anom_unacked  ON anomalies(acknowledged, timestamp)",
        # Canary health-check runs (component 4 — stored now, run later).
        """
        CREATE TABLE canary_runs (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            store          TEXT    NOT NULL,
            query          TEXT    NOT NULL,
            timestamp      TEXT    NOT NULL,
            expected_min   INTEGER NOT NULL,
            actual_count   INTEGER NOT NULL,
            passed         INTEGER NOT NULL,
            duration_ms    INTEGER,
            failure_reason TEXT
        )
        """,
        "CREATE INDEX idx_cr_store_ts ON canary_runs(store, timestamp)",
        # Summary row per nightly refresh run (component 5 enhancement).
        """
        CREATE TABLE refresh_runs (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at              TEXT    NOT NULL,
            finished_at             TEXT,
            stores_attempted        INTEGER,
            stores_succeeded        INTEGER,
            total_products_updated  INTEGER,
            total_queries_attempted INTEGER,
            total_queries_failed    INTEGER,
            details                 TEXT
        )
        """,
    ],
}

# ---------------------------------------------------------------------------
# DB lifecycle
# ---------------------------------------------------------------------------


def open_db(path: str = DB_PATH) -> sqlite3.Connection:
    """Opens (or creates) the monitoring DB, runs pending migrations, returns the connection."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA synchronous = NORMAL")
    run_migrations(conn)
    return conn


def run_migrations(conn: sqlite3.Connection) -> None:
    """Applies any pending schema migrations in ascending version order."""
    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    ).fetchone()

    current = 0
    if exists:
        row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        current = row[0] or 0

    for version in sorted(MIGRATIONS.keys()):
        if version <= current:
            continue
        with conn:
            for sql in MIGRATIONS[version]:
                conn.execute(sql)
            conn.execute(
                "INSERT INTO schema_version VALUES (?, ?)",
                (version, datetime.now(timezone.utc).isoformat()),
            )


@contextmanager
def _connect(path: str = DB_PATH):
    """Short-lived connection context manager for write operations."""
    conn = open_db(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


@contextmanager
def _read_conn(path: str = DB_PATH):
    """Short-lived connection context manager for read-only operations (no commit)."""
    conn = open_db(path)
    try:
        yield conn
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _days_cutoff(days: int) -> str:
    return f"-{days} days"


def _safe_json_load(text: Optional[str]):
    if not text:
        return text
    try:
        return json.loads(text)
    except Exception:
        return text


# ---------------------------------------------------------------------------
# Write API
# ---------------------------------------------------------------------------


def record_run(
    store: str,
    query: str,
    duration_ms: int,
    result_count: int,
    null_price_count: int,
    zero_price_count: int,
    null_name_count: int,
    had_installments: bool,
    error_class: Optional[str],
    error_msg: Optional[str],
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO adapter_runs
                (store, query, timestamp, duration_ms, result_count,
                 null_price_count, zero_price_count, null_name_count,
                 had_installments, error_class, error_msg)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                store, query, _now(), duration_ms, result_count,
                null_price_count, zero_price_count, null_name_count,
                1 if had_installments else 0,
                error_class, error_msg,
            ),
        )


def record_anomaly(
    store: str,
    query: str,
    severity: str,
    anomaly_type: str,
    details: Optional[dict] = None,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO anomalies
                (store, query, timestamp, severity, anomaly_type, details)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (store, query, _now(), severity, anomaly_type,
             json.dumps(details) if details else None),
        )


def record_canary_run(
    store: str,
    query: str,
    expected_min: int,
    actual_count: int,
    passed: bool,
    duration_ms: Optional[int] = None,
    failure_reason: Optional[str] = None,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO canary_runs
                (store, query, timestamp, expected_min, actual_count,
                 passed, duration_ms, failure_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (store, query, _now(), expected_min, actual_count,
             1 if passed else 0, duration_ms, failure_reason),
        )


def record_refresh_run(
    started_at: str,
    finished_at: Optional[str],
    stores_attempted: int,
    stores_succeeded: int,
    total_products_updated: int,
    total_queries_attempted: int,
    total_queries_failed: int,
    details: Optional[dict] = None,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO refresh_runs
                (started_at, finished_at, stores_attempted, stores_succeeded,
                 total_products_updated, total_queries_attempted,
                 total_queries_failed, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (started_at, finished_at, stores_attempted, stores_succeeded,
             total_products_updated, total_queries_attempted,
             total_queries_failed, json.dumps(details) if details else None),
        )


# ---------------------------------------------------------------------------
# Read API
# ---------------------------------------------------------------------------


def get_run_history(store: str, query: str, days: int = 7) -> list[dict]:
    """
    Returns adapter_runs rows for the given (store, query) over the last N days.
    Only successful runs (error_class IS NULL) are returned — error runs are
    excluded so they don't drag down the historical average.
    """
    with _read_conn() as conn:
        rows = conn.execute(
            """
            SELECT result_count, had_installments, duration_ms
            FROM adapter_runs
            WHERE store = ?
              AND query = ?
              AND error_class IS NULL
              AND timestamp >= datetime('now', ?)
            ORDER BY timestamp DESC
            """,
            (store, query, _days_cutoff(days)),
        ).fetchall()
    return [dict(r) for r in rows]


def get_open_anomalies() -> list[dict]:
    """Returns all unacknowledged anomalies, newest first."""
    with _read_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, store, query, timestamp, severity, anomaly_type, details
            FROM anomalies
            WHERE acknowledged = 0
            ORDER BY timestamp DESC
            """,
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["details"] = _safe_json_load(d.get("details"))
        result.append(d)
    return result


def get_last_canary_per_store() -> dict[str, dict]:
    """
    Returns the most recent canary_run row per store.
    Used by the /health endpoint to show per-store health status.
    """
    with _read_conn() as conn:
        rows = conn.execute(
            """
            SELECT cr.*
            FROM canary_runs cr
            INNER JOIN (
                SELECT store, MAX(timestamp) AS latest
                FROM canary_runs
                GROUP BY store
            ) latest ON cr.store = latest.store AND cr.timestamp = latest.latest
            """
        ).fetchall()
    return {r["store"]: dict(r) for r in rows}


def get_last_refresh() -> Optional[dict]:
    """Returns the most recent refresh_run row, or None if no refreshes recorded."""
    with _read_conn() as conn:
        row = conn.execute(
            "SELECT * FROM refresh_runs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["details"] = _safe_json_load(d.get("details"))
    return d


def prune_old_runs(days: int = 30) -> dict[str, int]:
    """
    Removes time-series rows older than N days to prevent DB bloat.
    Acknowledged anomalies are also pruned; unacknowledged ones are preserved
    so users can triage them before expiry. Returns deleted row counts per table.
    """
    cutoff = _days_cutoff(days)
    # Table and column names come from this hardcoded dict — never user input.
    # The assertion guards against future refactors that might pass untrusted values.
    tables = {
        "adapter_runs": "timestamp",
        "canary_runs":  "timestamp",
        "refresh_runs": "started_at",
    }
    _valid_tables = frozenset(tables)
    _valid_cols   = frozenset(tables.values())
    deleted: dict[str, int] = {}
    with _connect() as conn:
        for table, ts_col in tables.items():
            assert table in _valid_tables and ts_col in _valid_cols
            cur = conn.execute(
                f"DELETE FROM {table} WHERE {ts_col} < datetime('now', ?)",
                (cutoff,),
            )
            deleted[table] = cur.rowcount
        cur = conn.execute(
            "DELETE FROM anomalies WHERE acknowledged = 1 AND timestamp < datetime('now', ?)",
            (cutoff,),
        )
        deleted["anomalies"] = cur.rowcount
    return deleted


def acknowledge_anomaly(anomaly_id: int) -> bool:
    """
    Marks a single anomaly as acknowledged.
    Returns True if a row was updated, False if the ID didn't exist.
    """
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE anomalies SET acknowledged = 1 WHERE id = ?",
            (anomaly_id,),
        )
        return cur.rowcount > 0


def get_db_size_mb(path: str = DB_PATH) -> float:
    """Returns the monitoring.db file size in megabytes."""
    try:
        return os.path.getsize(path) / (1024 * 1024)
    except OSError:
        return 0.0
