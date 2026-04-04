"""
Cache layer — SQLite-backed product store.

Schema versioning: bump SCHEMA_VERSION and add a new entry to MIGRATIONS
whenever the data model changes. run_migrations() is called on every DB open
and applies any pending migrations in order, each inside its own transaction.

DB lives at data/cache.db (relative to the project root).

Freshness model
---------------
Caching is query-driven, not time-driven:
  - First time a query is searched → live fetch, results saved to DB.
  - Same query again → served entirely from DB (instant).
  - Daily refresh (refresh.py) → re-runs every known query and upserts
    all products, keeping data current without user interaction.

Per-product deduplication
-------------------------
When a new query returns results, each product is checked individually:
  - Already in DB (same store + URL) → DB version is used as-is.
  - Not in DB → live result is inserted.
This means richer data (e.g. card names from a previous detail search)
is never overwritten by a simpler live result for the same product.
"""
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from ..config import settings
from ..models import Installment, ProductResult

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

DB_PATH = os.path.join(settings.data_dir, "cache.db")

SCHEMA_VERSION = 2

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
        """
        CREATE TABLE products (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            store         TEXT    NOT NULL,
            sku           TEXT,
            name          TEXT    NOT NULL,
            price         REAL,
            currency      TEXT    NOT NULL DEFAULT 'ARS',
            available     INTEGER NOT NULL DEFAULT 1,
            free_shipping INTEGER NOT NULL DEFAULT 0,
            international INTEGER NOT NULL DEFAULT 0,
            url           TEXT    NOT NULL,
            fetched_at    TEXT    NOT NULL,
            UNIQUE(store, url)
        )
        """,
        """
        CREATE TABLE installments (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            count      INTEGER NOT NULL,
            amount     REAL    NOT NULL
        )
        """,
        """
        CREATE TABLE installment_cards (
            installment_id INTEGER NOT NULL REFERENCES installments(id) ON DELETE CASCADE,
            card           TEXT    NOT NULL
        )
        """,
        "CREATE INDEX idx_products_store     ON products(store)",
        "CREATE INDEX idx_products_store_url ON products(store, url)",
        "CREATE INDEX idx_products_name      ON products(name)",
        "CREATE INDEX idx_inst_product       ON installments(product_id)",
    ],
    2: [
        # Tracks every (store, query_text) that has been searched.
        """
        CREATE TABLE queries (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            store       TEXT    NOT NULL,
            query_text  TEXT    NOT NULL,   -- stored lowercase-normalised
            searched_at TEXT    NOT NULL,
            UNIQUE(store, query_text)
        )
        """,
        # Junction table: which products belong to which query result set.
        """
        CREATE TABLE query_products (
            query_id   INTEGER NOT NULL REFERENCES queries(id)   ON DELETE CASCADE,
            product_id INTEGER NOT NULL REFERENCES products(id)  ON DELETE CASCADE,
            PRIMARY KEY (query_id, product_id)
        )
        """,
        "CREATE INDEX idx_qp_query   ON query_products(query_id)",
        "CREATE INDEX idx_qp_product ON query_products(product_id)",
    ],
}


# ---------------------------------------------------------------------------
# DB lifecycle
# ---------------------------------------------------------------------------

def open_db(path: str = DB_PATH) -> sqlite3.Connection:
    """Opens (or creates) the cache DB, runs pending migrations, returns the connection."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -64000")
    conn.execute("PRAGMA mmap_size = 268435456")
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
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (version, _now()),
            )


# ---------------------------------------------------------------------------
# Query-level API
# ---------------------------------------------------------------------------

def has_query(conn: sqlite3.Connection, store: str, query: str) -> bool:
    """Returns True if this (store, query) pair has been searched and cached before."""
    return conn.execute(
        "SELECT 1 FROM queries WHERE store = ? AND query_text = ?",
        (store, _norm(query)),
    ).fetchone() is not None


def get_query_products(conn: sqlite3.Connection, store: str, query: str) -> list[ProductResult]:
    """Returns the cached product list for a previously searched (store, query) pair."""
    rows = conn.execute(
        """
        SELECT p.*
        FROM products p
        JOIN query_products qp ON qp.product_id = p.id
        JOIN queries q         ON q.id = qp.query_id
        WHERE q.store = ? AND q.query_text = ?
        """,
        (store, _norm(query)),
    ).fetchall()

    return [_row_to_product(conn, row) for row in rows]


def record_query(
    conn: sqlite3.Connection,
    store: str,
    query: str,
    product_urls: list[str],
) -> None:
    """
    Saves (or updates) a query record and links it to the given product URLs.
    Called after inserting new products so all IDs already exist in the DB.
    """
    norm = _norm(query)
    now = _now()
    with conn:
        conn.execute(
            """
            INSERT INTO queries (store, query_text, searched_at)
            VALUES (?, ?, ?)
            ON CONFLICT(store, query_text) DO UPDATE SET searched_at = excluded.searched_at
            """,
            (store, norm, now),
        )
        qid = conn.execute(
            "SELECT id FROM queries WHERE store = ? AND query_text = ?",
            (store, norm),
        ).fetchone()["id"]

        # Rebuild the product links for this query from scratch.
        conn.execute("DELETE FROM query_products WHERE query_id = ?", (qid,))
        for url in product_urls:
            row = conn.execute(
                "SELECT id FROM products WHERE store = ? AND url = ?", (store, url)
            ).fetchone()
            if row:
                conn.execute(
                    "INSERT OR IGNORE INTO query_products (query_id, product_id) VALUES (?, ?)",
                    (qid, row["id"]),
                )


# ---------------------------------------------------------------------------
# Product-level API
# ---------------------------------------------------------------------------

def get_product_by_url(
    conn: sqlite3.Connection, store: str, url: str
) -> Optional[ProductResult]:
    """Returns the cached ProductResult for a store+URL, or None if not found."""
    row = conn.execute(
        "SELECT * FROM products WHERE store = ? AND url = ?", (store, url)
    ).fetchone()
    return _row_to_product(conn, row) if row else None


def upsert_products(conn: sqlite3.Connection, store: str, results: list[ProductResult]) -> None:
    """
    Inserts or fully updates products (keyed on store+url).
    Used by the daily refresh, which always overwrites with fresh live data.
    """
    now = _now()
    with conn:
        for r in results:
            conn.execute(
                """
                INSERT INTO products
                    (store, sku, name, price, currency, available, free_shipping,
                     international, url, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(store, url) DO UPDATE SET
                    sku           = excluded.sku,
                    name          = excluded.name,
                    price         = excluded.price,
                    currency      = excluded.currency,
                    available     = excluded.available,
                    free_shipping = excluded.free_shipping,
                    international = excluded.international,
                    fetched_at    = excluded.fetched_at
                """,
                (
                    store, r.sku, r.name, r.price, r.currency,
                    int(r.available), int(r.free_shipping), 1 if r.international is True else 0,
                    r.url, now,
                ),
            )
            pid = conn.execute(
                "SELECT id FROM products WHERE store = ? AND url = ?", (store, r.url)
            ).fetchone()["id"]

            # Always replace installments so card data stays current.
            conn.execute("DELETE FROM installments WHERE product_id = ?", (pid,))
            for inst in r.installments:
                iid = conn.execute(
                    "INSERT INTO installments (product_id, count, amount) VALUES (?, ?, ?)",
                    (pid, inst.count, inst.amount),
                ).lastrowid
                for card in inst.cards:
                    conn.execute(
                        "INSERT INTO installment_cards (installment_id, card) VALUES (?, ?)",
                        (iid, card),
                    )


def insert_new_products(
    conn: sqlite3.Connection, store: str, results: list[ProductResult]
) -> None:
    """
    Inserts only products that don't already exist in the DB (keyed on store+url).
    Used during interactive queries: existing products keep their cached data intact.
    """
    now = _now()
    with conn:
        for r in results:
            existing = conn.execute(
                "SELECT id FROM products WHERE store = ? AND url = ?", (store, r.url)
            ).fetchone()
            if existing:
                continue  # already in DB — leave it untouched

            conn.execute(
                """
                INSERT INTO products
                    (store, sku, name, price, currency, available, free_shipping,
                     international, url, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    store, r.sku, r.name, r.price, r.currency,
                    int(r.available), int(r.free_shipping), 1 if r.international is True else 0,
                    r.url, now,
                ),
            )
            pid = conn.execute(
                "SELECT id FROM products WHERE store = ? AND url = ?", (store, r.url)
            ).fetchone()["id"]
            for inst in r.installments:
                iid = conn.execute(
                    "INSERT INTO installments (product_id, count, amount) VALUES (?, ?, ?)",
                    (pid, inst.count, inst.amount),
                ).lastrowid
                for card in inst.cards:
                    conn.execute(
                        "INSERT INTO installment_cards (installment_id, card) VALUES (?, ?)",
                        (iid, card),
                    )


def all_known_queries(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """Returns all (store, query_text) pairs that have been searched."""
    rows = conn.execute("SELECT store, query_text FROM queries ORDER BY store, query_text").fetchall()
    return [(row["store"], row["query_text"]) for row in rows]


def product_count(conn: sqlite3.Connection, store: str) -> int:
    """Returns the number of cached products for a store."""
    return conn.execute(
        "SELECT COUNT(*) FROM products WHERE store = ?", (store,)
    ).fetchone()[0]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _row_to_product(conn: sqlite3.Connection, row: sqlite3.Row) -> ProductResult:
    return ProductResult(
        name=row["name"],
        sku=row["sku"],
        price=row["price"],
        currency=row["currency"],
        available=bool(row["available"]),
        free_shipping=bool(row["free_shipping"]),
        international=bool(row["international"]),
        url=row["url"],
        installments=_load_installments(conn, row["id"]),
    )


def _load_installments(conn: sqlite3.Connection, product_id: int) -> list[Installment]:
    rows = conn.execute(
        "SELECT id, count, amount FROM installments WHERE product_id = ? ORDER BY count DESC",
        (product_id,),
    ).fetchall()
    result = []
    for row in rows:
        cards = [
            r["card"]
            for r in conn.execute(
                "SELECT card FROM installment_cards WHERE installment_id = ?", (row["id"],)
            ).fetchall()
        ]
        result.append(Installment(count=row["count"], amount=row["amount"], cards=cards))
    return result


def _norm(query: str) -> str:
    """Normalises a query string for consistent storage and lookup."""
    return query.strip().lower()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
