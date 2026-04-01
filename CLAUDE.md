# ElectrodomesticsBot — Project Reference

## What This Project Is

A Python CLI tool that searches multiple Argentine electronics/appliance ecommerce stores simultaneously and returns structured, comparable product data for a given model name or SKU. The user types a query (e.g. "S26", "G15", "heladera Samsung") and gets a unified view across all stores: price, interest-free installment options with card names, availability, free shipping, and whether the product is an international purchase.

## Ultimate Goal

Scale this to cover tens of Argentine ecommerce stores without needing to hand-craft a scraper for each one. Most stores run on one of a small number of platforms (VTEX, Magento 2, etc.), so the real leverage is implementing platform-level logic once and then onboarding each store with just its name and base URL. Store-specific workarounds should be the exception, not the rule.

## How to Run

```
python run.py
# then type a model name or SKU when prompted
```

The program can also be run as a module: `python -m electrodomestics_bot`

## Codebase Structure

```
ElectrodomesticsBot/
├── run.py                              ← entry point (thin wrapper)
├── refresh.py                          ← entry point for background cache refresh job
├── bench/                              ← benchmarks and one-off debug scripts (not production)
│   ├── bench_fravega.py                ← Fravega timing benchmark (unlimited vs semaphored concurrency)
│   ├── bench_ps5.py                    ← multi-store diagnostic benchmark for broad queries
│   ├── bench_s26.py                    ← comprehensive per-store timing benchmark with phase breakdown
│   ├── analyze_plans.py                ← offline analysis of Fravega plans API response
│   └── fetch_fravega_plans.py          ← one-off script to fetch raw plans GQL from Fravega
└── electrodomestics_bot/
    ├── __main__.py                     ← CLI: reads input, calls search, prints results
    ├── core.py                         ← http_get(), matches_query(), search_all_stores()
    ├── models.py                       ← ProductResult and Installment dataclasses
    ├── display.py                      ← formats and prints results to terminal
    ├── service.py                      ← search_products(): cache + live fetch, all stores in parallel
    ├── cache.py                        ← SQLite cache: products, queries, upsert/insert logic
    ├── platforms/                      ← INFRASTRUCTURE LAYER
    │   ├── fravega.py                  ← All Fravega Next.js + Apollo GraphQL logic
    │   ├── magento.py                  ← All Magento 2 + Summa Solutions logic
    │   ├── megatone.py                 ← All Megatone / Doofinder v6 logic
    │   └── vtex.py                     ← All VTEX Intelligent Search logic
    ├── monitoring/                     ← OBSERVABILITY LAYER
    │   ├── storage.py                  ← SQLite schema + read/write API for monitoring.db
    │   ├── collector.py                ← make_run_callback(): records adapter_runs rows
    │   ├── anomaly.py                  ← check(): detects quality issues, writes anomalies
    │   ├── alerts.py                   ← Telegram fire-and-forget notifications
    │   └── canary.py                   ← run_all(): post-refresh health probes
    └── adapters/                       ← STORE LAYER
        ├── base.py                     ← StoreAdapter ABC
        ├── __init__.py                 ← ADAPTERS list (edit this to add/remove stores)
        ├── castillo.py                 ← CastilloAdapter(VtexAdapter) — installment override + free shipping
        ├── cetrogar.py                 ← CetrogarAdapter(MagentoAdapter) — 5 lines
        ├── fravega.py                  ← FravegaStoreAdapter(FravegaAdapter) — 5 lines
        ├── megatone.py                 ← MegatoneAdapter(MegatonePlatform) — 4 lines
        └── oncity.py                   ← OncityAdapter(VtexAdapter) — 5 lines
```

## Data Model

`ProductResult` fields (defined in `models.py`):

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | Product name as returned by the store |
| `sku` | `str` | Store SKU or reference ID |
| `price` | `Optional[float]` | Final selling price in ARS |
| `currency` | `str` | Always `"ARS"` for now |
| `installments` | `list[Installment]` | Interest-free options only |
| `available` | `bool` | Whether the product is in stock |
| `free_shipping` | `bool` | Whether home delivery is free |
| `international` | `Optional[bool]` | "Compra Internacional" marketplace products; `None` when concept doesn't apply (e.g. regional stores) |
| `url` | `str` | Direct product page URL |

`Installment` fields: `count` (number of installments), `amount` (price per installment), `cards` (list of card/bank names offering this option).

## Current Stores

| Store | Platform | Adapter | Notes |
|---|---|---|---|
| Castillo | VTEX Intelligent Search | `adapters/castillo.py` | Regional store (Tucumán); `postal_code="4000"`, `_free_shipping_override=True`, hardcoded `_INSTALLMENT_CARDS` |
| Cetrogar | Magento 2 + Summa Solutions | `adapters/cetrogar.py` | |
| Fravega | Custom Next.js + Apollo GraphQL | `adapters/fravega.py` | Uses `curl_cffi` for Cloudflare bypass |
| Megatone | Doofinder v6 search + custom installments API | `adapters/megatone.py` | Individual `retornarplanes` calls per card network + bank promos, all in parallel |
| OnCity | VTEX Intelligent Search | `adapters/oncity.py` | `verify_ssl=False` due to cert issue |

## Platform Details

### Fravega (`platforms/fravega.py`)
- Custom Next.js + Apollo GraphQL stack; **not** VTEX, Magento, or Shopify
- **HTTP client:** must use `curl_cffi` (`AsyncSession(impersonate="chrome120")`) — standard `httpx`/`aiohttp`/`requests` get blocked by Cloudflare. The session is module-level and shared across all calls.
- Search endpoint: `POST /api/v1/rest/search` (GraphQL, no build hash in the URL — stable)
- Pagination: offset-based, 50 results/page, capped at 10 pages (500 results); extra pages fetched in parallel via `asyncio.gather`
- **Installments (fast mode):** count parsed from label text in the search response (`"12 cuotas sin interés"` → regex `(\d+)\s+cuotas?\s+sin\s+inter`); amount = `price / count`; no card names available
- **Installments (detail mode):** per-SKU `plans(sku)` GQL query; card networks shown at their max no-interest count from generic (no-issuer) rows; an issuer (e.g. BNA) appears only when its count exceeds the base network count — see `_parse_plans()` docstring
- **Free shipping:** per-product `calculateDeliveryTermAndCost(sku, seller, postalCode)` GQL query; `cost == 0` means free. Skipped when matched products exceed `_MAX_SHIPPING_CHECKS` (100) — see gotcha #20
- **Availability:** always `True` — the API only returns listable products
- **International:** `sellerCondition == ["international_seller"]` in the search response item
- **GQL concurrency cap:** production adapter uses `asyncio.Semaphore(40)` on `_post_gql` to avoid connection resets under high concurrency
- **Shipping cache (disabled):** `_SHIPPING_CACHE_ENABLED = False` — TTL-based in-memory dict ready to flip on for v1 launch; see comment block above `_SHIPPING_CACHE_ENABLED` in `platforms/fravega.py`

### VTEX (`platforms/vtex.py`)
- Search: `/_v/api/intelligent-search/product_search/?query={}&count=50&page={N}` — paginated, capped at 10 pages (500 results)
- Pagination: response contains `pagination.count` (total pages); extra pages fetched in parallel via `asyncio.gather`
- Shipping simulation: `/api/checkout/pub/orderForms/simulation` (POST), unlimited concurrency via `asyncio.gather`; skipped for unavailable products and when `_free_shipping_override` is set
- Price and installments read from `commertialOffer` in the search response — no extra page fetch needed
- Installments filtered to `PaymentSystemGroupName == "creditCardPaymentGroup"` — excludes debit, cash, and other payment types that pollute the installment list
- Multi-seller products: always use `_get_real_seller()` — international/marketplace products have a dummy seller "1" with Price=0 alongside the real seller
- Availability: `AvailableQuantity > 0` on any seller
- International products: detected via `categories` containing `/Compra Internacional/` or `productClusters` named "Compra Internacional"; returns `Optional[bool]` — `None` when the concept doesn't apply
- Free shipping: detected via simulation API — any `slas[]` entry with `deliveryChannel == "delivery"` and `price == 0`
- `_free_shipping_override`: set to `True`/`False` in adapter to skip shipping simulation entirely (use for stores where all deliveries are free, or where the API is unreliable)

### Magento 2 + Summa Solutions (`platforms/magento.py`)
- Search: `/catalogsearch/result/index/?q={}&p={N}` — full HTML search results, ~40 products/page, paginated, capped at 10 pages (~400 results)
- Pagination: max page number extracted from `?p=N` links in the response HTML; pages fetched in parallel via `ThreadPoolExecutor(max_workers=5)`
- Product data parsed from `<li class="product-item">` elements: name/SKU from `data-mage-init` `ajaxWishlist` JSON, price from `data-price-type="finalPrice"` `data-price-amount` attribute, URL from `<a class="product-item-info">`
- Installments: extracted directly from `div.installment-info` inside each search result `<li>` — no extra page fetches needed. Shows one option per product (best/featured, count + amount only, no card names). `_fetch_installments()` still exists for subclass use if full card data is needed.
- Card names: not available from search results page; only obtainable by fetching individual product pages via `_fetch_installments()`
- Free shipping: always `False` (Magento stores in scope don't offer it)
- Availability: always `True` (catalogsearch only surfaces in-stock products)

### Megatone / Doofinder v6 (`platforms/megatone.py`)
- Search engine: **Doofinder** (third-party SaaS); endpoint `https://us1-search.doofinder.com/6/{hashid}/_search`
- **HTTP client:** standard `httpx` via `get_client()` — no Cloudflare protection on Doofinder endpoint. Requires `Origin` and `Referer` headers matching the store domain (Doofinder enforces domain whitelisting; omitting headers returns 403).
- Pagination: `rpp=100` per page; `total` field in response used for pagination count; extra pages fetched in parallel via `asyncio.gather`; capped at 10 pages (1,000 results)
- Price: `sale_price` field (not `price` — `price` is the inflated list price; `sale_price` is what the customer pays)
- Availability: `availability == "in stock"` (string comparison, case-insensitive)
- Free shipping: `free_shipping == "true"` (string boolean)
- International: `productointernacional == "true"` (string boolean)
- **Installments:** `highlight_installments` field contains a text label; only products with `"Sin Inter"` in this field get installment detail. No card names from search API — full card/count data fetched from the store's own `retornarplanes` endpoint.
- **Installment strategy:** uses a single **representative SKU** (highest-priced eligible product) to query plans — avoids the API returning an empty intersection when a mixed list of SKUs is sent. The resulting tiers are applied to all eligible products.
- **Parallel calls:** all card/bank calls fire concurrently via `asyncio.gather` in three groups:
  1. **Individual card networks** (`_CARD_CALLS`): Visa(5), Mastercard(3), AmEx(2), Cabal(6), NaranjaX(7) — individual calls return correct counts; the comprehensive call understates them.
  2. **Special cards**: Directo/debit(18) — only lowest sin-interés tier shown; Comprehensive(0) — fallback for Mercado Pago (no dedicated IdTarjeta).
  3. **Bank promos** (`_BANK_PROMOS`): `IdTarjeta=5` + each bank ID — 8 Argentine banks (BNA, Galicia, BBVA, Santander, Santa Fe, Entre Rios, San Juan, Santa Cruz).
- **Amount calculation:** since all plans are 0% interest, amount = `price / count` (exact). The API's `valor` field is not used — avoids per-product calls.
- **Bank promos:** only appear in results when they exceed the base Visa count (mirrors website display logic).
- **Comprehensive call fallback:** `IdTarjeta=0` is kept only to catch cards without a dedicated call (e.g. Mercado Pago). Cards already populated by individual calls are skipped — the comprehensive call understates their counts.
- `_SUCURSAL = 104` (web store; override with 434 for MX stores)

## Monitoring System (`electrodomestics_bot/monitoring/`)

A lightweight observability layer backed by a separate SQLite DB (`data/monitoring.db`) — kept isolated from `data/cache.db` so monitoring writes never contend with product data reads.

### Components

| File | Role |
|---|---|
| `storage.py` | Schema, migrations, all read/write DB functions |
| `collector.py` | `make_run_callback()` — records every adapter call to `adapter_runs` |
| `anomaly.py` | `check()` — inspects live results for null prices, zero results, install drop; records to `anomalies` |
| `alerts.py` | `alert_anomalies()` / `alert_canary_failures()` — fire-and-forget Telegram notifications |
| `canary.py` | `run_all()` — runs 6 fixed (store, query) health-check probes post-refresh |

### DB Schema (`SCHEMA_VERSION = 1`)

| Table | Written by | Purpose |
|---|---|---|
| `adapter_runs` | `collector.py` via `record_run()` | One row per live adapter call; stores duration, result count, error info |
| `anomalies` | `anomaly.py` via `record_anomaly()` | Quality issues detected in live results; `acknowledged` flag for triage |
| `canary_runs` | `canary.py` via `record_canary_run()` | One row per canary probe; `passed` flag + optional `failure_reason` |
| `refresh_runs` | `refresh.py` via `record_refresh_run()` | Summary row per nightly refresh; stores/products/queries attempted vs succeeded |

Schema migrations follow the same version table pattern as `cache.py`: bump `SCHEMA_VERSION`, add entries to `MIGRATIONS`, `run_migrations()` applies them on every DB open.

### Integration Points

- **`fetching/core.py` → `search_all_stores()`**: accepts optional `on_run` callback; `collector.make_run_callback(query)` is passed here from `service.py` to record every adapter call.
- **`fetching/service.py` → `_fetch_one()`**: calls `anomaly.check()` on live results after each store fetch; schedules `alert_anomalies()` as a background task if anomalies are found.
- **`refresh.py` → `refresh_all()`**: calls `record_refresh_run()` after every nightly refresh, then calls `prune_old_runs()` to enforce 30-day retention.
- **`refresh.py` → `main()`**: runs `canary.run_all()` post-refresh and calls `alert_canary_failures()` if any probes fail.

### REST Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Store count, last canary per store, last refresh summary, `monitoring.db` size |
| `/health/anomalies` | GET | All unacknowledged anomalies, newest first |
| `/health/anomalies/{id}/acknowledge` | POST | Mark a single anomaly acknowledged (removes it from the open list) |

### Retention Policy

`prune_old_runs(days=30)` deletes rows older than 30 days from `adapter_runs`, `canary_runs`, and `refresh_runs`. Acknowledged anomalies are also pruned at 30 days; **unacknowledged anomalies are preserved indefinitely** so they can be triaged first. Called automatically by `refresh.py` after each nightly run.

---

## Golden Rule: Infrastructure First

**Before implementing any new feature or fix, always ask:**

> "Is this behavior determined by the platform (VTEX/Magento or any other), or is it unique to a specific store?"

- If it's **platform behavior** → implement in `platforms/vtex.py` or `platforms/magento.py`
- If it's truly **store-specific** (a quirk of one site) → implement as an override in the store's adapter file

The goal is that adding a new store requires nothing more than declaring its `name` and `base_url`. Every feature in `platforms/` is automatically inherited by all current and future stores on that platform.

### Decision table

| Feature | Where it lives | Why |
|---|---|---|
| Fravega GQL search + pagination | `platforms/fravega.py` | Fravega-platform contract |
| Fravega installment fast parsing (label text) | `platforms/fravega.py` | Same label format across all Fravega stores |
| Fravega installment detail (`plans` GQL) | `platforms/fravega.py` | Same GQL schema across all Fravega stores |
| Fravega free shipping (`calculateDelivery` GQL) | `platforms/fravega.py` | Same GQL schema across all Fravega stores |
| Fravega international detection (`sellerCondition`) | `platforms/fravega.py` | Same field across all Fravega stores |
| Fravega shipping threshold + cache | `platforms/fravega.py` | Performance concern affecting all Fravega stores |
| VTEX price extraction | `platforms/vtex.py` | Standard VTEX API contract |
| VTEX availability detection | `platforms/vtex.py` | Standard VTEX API contract |
| VTEX free shipping simulation | `platforms/vtex.py` | Standard VTEX checkout API |
| VTEX international product detection | `platforms/vtex.py` | Standard VTEX taxonomy fields |
| VTEX multi-seller / real seller resolution | `platforms/vtex.py` | Standard VTEX API structure |
| VTEX redirect → legacy API fallback | `platforms/vtex.py` | Redirect behavior is VTEX-platform-wide |
| Magento 2 price HTML parsing | `platforms/magento.py` | Standard Magento price widget |
| Summa Solutions installment scraping | `platforms/magento.py` | Scraped from `div.installment-info` on search page (no extra fetches); `_fetch_installments()` available for full card data |
| Summa card logo filename map | `platforms/magento.py` | Same CDN filenames across all Summa stores (used by `_fetch_installments` only) |
| OnCity SSL workaround (`verify_ssl=False`) | `adapters/oncity.py` | OnCity-specific certificate issue |
| Megatone Doofinder search + pagination | `platforms/megatone.py` | Doofinder platform contract |
| Megatone installment batching (`retornarplanes`) | `platforms/megatone.py` | All Doofinder-backed stores use same plans API |
| Megatone bank promo detection | `platforms/megatone.py` | Same logic across all Doofinder stores |
| Castillo `_INSTALLMENT_CARDS` override | `adapters/castillo.py` | Castillo shows a fixed card set the API doesn't reflect |
| Castillo `_free_shipping_override = True` | `adapters/castillo.py` | All Castillo deliveries are free; simulation would waste time |
| Castillo `postal_code = "4000"` | `adapters/castillo.py` | Tucumán-based store; Buenos Aires postal code returns no shipping SLAs |

## Adding a New Store

**VTEX store (most common case — 2 lines):**
```python
# adapters/newstore.py
from ..platforms.vtex import VtexAdapter

class NewStoreAdapter(VtexAdapter):
    name = "newstore"
    base_url = "https://www.newstore.com.ar"
```

**Magento store:**
```python
# adapters/newstore.py
from ..platforms.magento import MagentoAdapter

class NewStoreAdapter(MagentoAdapter):
    name = "newstore"
    base_url = "https://www.newstore.com.ar"
```

**Fravega-platform store:**
```python
# adapters/newstore.py
from ..platforms.fravega import FravegaAdapter

class NewStoreAdapter(FravegaAdapter):
    name = "newstore"
    base_url = "https://www.newstore.com.ar"
```

**Megatone/Doofinder store:**
```python
# adapters/newstore.py
from ..platforms.megatone import MegatoneAdapter as _MegatonePlatform

class NewStoreAdapter(_MegatonePlatform):
    name = "newstore"
    base_url = "https://www.newstore.com.ar"
    _doofinder_hashid = "..."   # find in DevTools: us1-search.doofinder.com/6/{hashid}/_search
```

Then add `NewStoreAdapter()` to the `ADAPTERS` list in `adapters/__init__.py`.

### Overridable class attributes

| Attribute | Default | Platform | When to override |
|---|---|---|---|
| `postal_code` | `"1425"` (Buenos Aires) | VTEX, Fravega | Different delivery region |
| `verify_ssl` | `True` | VTEX, Fravega, Megatone | Store has broken SSL cert |
| `card_keywords` | standard Summa map | Magento | Store uses non-standard card logo filenames |
| `_free_shipping_override` | `None` | VTEX | `True` = all free, `False` = none free; skips simulation entirely |
| `_SUCURSAL` | `104` (web/AR) | Megatone | `434` for MX stores |
| `_BANK_PROMOS` | 8 Argentine banks | Megatone | Add/remove bank promo IDs for different store's active promos |
| `_INSTALLMENT_CARDS` | _(none — use API data)_ | VTEX | Override to hardcode a store's card set when API returns extras the site doesn't show |

## Known Patterns and Gotchas

- **VTEX international products** have two sellers in the API: a dummy `seller="1"` with `Price=0` and `AvailableQuantity=0`, and the real marketplace seller. Always use `_get_real_seller()` — never index `sellers[0]` directly.
- **Cetrogar installments** require fetching every product page individually. This is inherently slow; parallelism via `asyncio.gather` is critical.
- **`matches_query()`** in `core.py` filters results so that only products containing all query words appear — compensates for stores returning loosely-related suggestions.
- **SSL warnings** are globally suppressed in `core.py` (`warnings.filterwarnings("ignore")`) because several stores have certificate issues.
- The `currency` field is hardcoded to `"ARS"` — all stores currently in scope are Argentine.
- **Fravega shipping is the dominant bottleneck**: broad queries (e.g., brand-only searches) return hundreds of products, each needing a GQL shipping call averaging ~14s. Wall time = slowest single call (~27s). Queries exceeding `_MAX_SHIPPING_CHECKS` skip shipping entirely (all products get `free_shipping=False`).
- **All stores are searched in parallel** via `asyncio.gather` in `service.py` — total response time ≈ slowest single store, not the sum.

---

## Lessons Learned — Field-Tested Gotchas

This section documents bugs, surprises, and non-obvious behaviors discovered through live testing. Read this before onboarding a new store or platform.

---

### Universal (applies to every ecommerce, every platform)

#### 1. Never cache a zero-result live fetch

If a live search returns 0 products, do **not** record the query in the DB. Zero results may be caused by a transient redirect, a network hiccup, or a platform-side quirk — not a genuine empty catalog. Caching it permanently blocks re-fetching for that query.

In `__main__.py`, `record_query` is only called when `final` is non-empty. Keep that guard in place. If you add a new code path that writes to the cache, apply the same rule.

#### 2. `matches_query` normalizes accents — but is not a stemmer

`matches_query` strips Unicode combining marks from both the query and the product name before comparing (via `unicodedata.NFD`). This means `"televisión"` matches `"Televisión"`, and `"telefono"` matches `"Teléfono"`.

What it does **not** do: stemming or synonym resolution. `"televisión"` will **not** match `"Televisor"` because they are different words after accent-stripping. This is intentional — the tool is designed for model-name and SKU searches, not natural-language browse. If a query returns 0 results from a store, the most likely explanation is that the store's search engine doesn't index that term, not a bug in `matches_query`.

#### 3. Short-token word-boundary rule exists for a reason

Tokens of ≤ 2 characters in a query use a word-boundary regex (`\b`) instead of substring matching. Without this, "TV" would match "VTEX", "LG" would match "ALGO", "4K" would match "4KHDR". Never weaken this guard when adding new platforms.

#### 4. `format_price` must round, not truncate

Use `round(price)` — not `int(price)` — when converting ARS prices to integer for display. VTEX stores return prices with fractional centavo components (e.g., `14558.99`). `int()` silently discards the decimal; `round()` gives the nearest peso. The displayed amount should never be less than what the store actually charges.

#### 5. JS-rendered placeholder `<li>` elements are not real products

Some stores (confirmed: Cetrogar via BrainDW) render empty `<li class="product-item">` elements on zero-result pages as placeholders for JavaScript-loaded recommendation carousels. These shells have no `href`, no `data-mage-init`, no price — they look like broken product rows but are actually recommendation widgets.

**How to tell it's a genuine no-results page vs a scraping gap:**
- Magento: check for `catalogsearch_result_index_noresults` in the HTML. If it's there, the store's own search found nothing — 0 is the correct answer. The JS placeholders are BrainDW/similar recommendations, not products.
- VTEX: the API returns `{"products": [], "redirect": "..."}` for redirect-configured queries (see below). Empty `products` array alone is not sufficient — always check for the `redirect` field.

#### 6. Cache query normalization is case-insensitive and whitespace-stripped

`_norm(query)` in `cache.py` does `.strip().lower()`. Searching "PS5", "ps5", and "  PS5  " all map to the same cache entry. This is intentional. When adding new cache-reading code, always pass the query through `_norm()` before any DB lookup.

#### 7. Product deduplication is keyed on `(store, url)`, not name

Two products with identical names but different URLs are treated as distinct. Two products from different stores with the same URL are also treated as distinct (cross-store deduplication is out of scope). Never deduplicate by name — product names across variants (colors, storage sizes) are often identical.

---

### VTEX (`platforms/vtex.py`)

#### 8. Intelligent Search can redirect queries to category pages — and return zero products

VTEX stores can configure "search redirects" in their admin: certain brand or model queries (e.g., "PS5", "PlayStation 5", "consola ps5") are redirected to a category page instead of returning search results. The API response is:

```json
{"products": [], "redirect": "https://store.com/some-category", "recordsFiltered": 0}
```

The `products` array is empty and a redirect URL is set. **This is not an error** — VTEX deliberately suppresses results when a redirect is configured. The fix is to fall back to the VTEX legacy catalog API, which ignores redirects entirely.

**Detection:** `data.get("redirect")` is a non-empty string AND `data.get("products") == []`.

**Workarounds that do NOT help:** `fuzzy=1`, `fuzzy=auto`, `operator=or` — the redirect takes priority regardless.

**Already implemented** in `_fetch_all_products()` → calls `_fetch_all_products_legacy()` on redirect detection.

#### 9. VTEX legacy catalog API: different format, same `commertialOffer`

The legacy API (`/api/catalog_system/pub/products/search?ft={query}&_from=0&_to=49`) returns the same `items → sellers → commertialOffer` structure as the intelligent search. All extraction methods (`_extract_price`, `_extract_installments`, `_is_available`, `_check_free_shipping`) work unchanged.

**Two format differences that must be normalized before reuse:**

| Field | Intelligent Search | Legacy API | Fix |
|---|---|---|---|
| `link` | Relative path (`/product-slug/p`) | Full URL (`https://store.com/product-slug/p`) | Strip `self.base_url` prefix |
| `productClusters` | List of dicts: `[{"id": "628", "name": "Full Catalogo"}]` | Dict: `{"628": "Full Catalogo"}` | Convert to list format |

`_normalize_legacy_product()` in `VtexAdapter` handles both. Always pass legacy results through this method before returning.

#### 10. VTEX legacy API pagination uses response headers, not response body

Unlike the intelligent search (which reports total pages in `pagination.count`), the legacy API signals total results in the `resources` response header:

```
resources: 0-49/100   →  total = 100 products
```

Parse it as `int(resp.headers["resources"].split("/")[-1])`. Cap at 500 (same as intelligent search cap). If the header is missing, fall back to `len(first_page_results)`.

#### 11. VTEX `productClusters` format differs between API versions

This tripped up `_is_international()`, which iterates `productClusters` and calls `.get("name")` on each item. In intelligent search the items are dicts; in the legacy API they are strings (dict keys are the IDs, dict values are the names). `_normalize_legacy_product()` converts the legacy format to the dict-list format so `_is_international()` works identically for both.

#### 12. VTEX custom pages are not searchable via the category API

When a VTEX store's redirect URL points to a path with route `vtex.store@2.x:store.custom#...` (visible in `window.__RUNTIME__` in the HTML), it is a custom storefront page — not a standard department or category. The `/_v/api/intelligent-search/product_search/{slug}?map=c` endpoint will **not** return the expected products for these pages. The correct fallback is the legacy full-text search API (`ft=` parameter), not a category browse.

#### 13. Never use `sellers[0]` directly on VTEX products

Multi-seller and marketplace products have a dummy seller at position 0 with `Price=0` and `AvailableQuantity=0`. The real seller is identified by `sellerDefault=True` with `AvailableQuantity > 0`. Use `_get_real_seller()` everywhere — it handles both the default case and the fallback to any seller with a non-zero price.

---

### Magento 2 + Summa Solutions (`platforms/magento.py`)

#### 14. Cetrogar (and likely other Magento stores) use two different `data-mage-init` patterns

When parsing `<li class="product-item">` elements, `data-mage-init` may contain either:

- `ajaxWishlist` → has `name` and `sku` fields. Use these directly.
- `Amasty_Label/js/initLabel` → label/badge widget. Contains no product data. Fall through to the `<img class="product-image-photo" alt="...">` fallback for the name. SKU will be `None`.

Both patterns appear on the same store, sometimes even on the same page. The parser already handles this: it checks all `data-mage-init` tags for `ajaxWishlist`, and falls back to `img.alt` if not found. Do not assume the `ajaxWishlist` key is always present.

#### 15. Magento search page installments vs product page installments

The search results page (`/catalogsearch/result/`) shows at most **one** installment option per product (the best/featured one), with count and amount but **no card names**. Full card data requires fetching each individual product page via `_fetch_installments()`.

This is the fast/detail mode tradeoff:
- `detail=False` (default): use search-page installment data. Fast, no extra network requests. One installment per product, no card names.
- `detail=True`: fetch every product page in parallel (`ThreadPoolExecutor(max_workers=10)`). Slow (~2× slower), but returns all installment options with full card names.

When adding a new Magento store, assume this same tradeoff applies unless the store has a significantly different Summa Solutions setup.

#### 16. Magento `catalogsearch_result_index_noresults` means genuine zero results

When the Magento search returns no matches, the HTML page contains the string `catalogsearch_result_index_noresults` in a script block (it's part of the Magento page handle set). The page also loads JavaScript-driven recommendation carousels (e.g., BrainDW) that inject `<li class="product-item">` placeholders — these look like product rows but have no `href`, no `data-mage-init` with product data, and no price attributes.

**The current scraper already handles this correctly** — `_parse_search_item()` returns `None` for any `<li>` that lacks `<a class="product-item-info">`, so the placeholders are silently skipped. Do not add special-case logic to detect or warn about them; the 0-result output is accurate.

#### 17. Magento stores may have genuine search gaps for natural-language queries

Cetrogar's search engine (and likely others) indexes product names and SKUs, not natural-language descriptions. Queries like "55 pulgadas" or "television" return zero results on Cetrogar because the catalog uses "televisor" and "UN55..." style naming. This is expected and correct — the tool is designed for model/SKU searches. Do not treat 0 results as evidence of a scraping bug without first verifying on the store's own website.

---

### Fravega (`platforms/fravega.py`)

#### 18. Fravega requires `curl_cffi` — standard HTTP clients get Cloudflare-blocked

Fravega's CDN applies Cloudflare bot protection. `httpx`, `aiohttp`, and `requests` are blocked with 403 or 503 responses. The only client that works reliably is `curl_cffi.requests.AsyncSession(impersonate="chrome120")`, which mimics a real browser's TLS fingerprint.

The session is a module-level singleton (`_session`) shared across all calls to avoid per-call TLS handshake overhead. Do not instantiate a new session per request or per adapter instance.

#### 19. Fravega's GQL endpoint handles three query types through the same URL

All three operations — product search, shipping calculation, and plans lookup — are POSTed to the same endpoint (`/api/v1/rest/search`) as GraphQL query strings. There is no separate endpoint per operation. When adding new data fields, always use the same `_post_gql()` method and the existing `_endpoint` property.

#### 20. Fravega shipping wall-time grows with result count — skip above threshold

Each matched product requires a separate `calculateDeliveryTermAndCost` GQL call. These run fully concurrently via `asyncio.gather`, so wall time = slowest individual call, not the sum. In practice, single GQL calls average ~14s under load; a broad query returning 365 matches produces a ~27s shipping phase even with unlimited concurrency.

`_MAX_SHIPPING_CHECKS = 100` is the safety valve: if more products match than this threshold, **all** shipping checks are skipped and `free_shipping=False` for all results. This keeps broad queries fast at the cost of missing shipping data. The threshold is intentionally conservative — raise it only after benchmarking the expected P99 call time at the new limit.

#### 21. Fravega `_parse_plans()` mirrors the store's own display logic, not raw API data

The `plans(sku)` GQL returns one row per card network × issuer × installment count combination. The website collapses these into a compact display: networks are shown at their max no-interest count from rows with no issuer; an issuer (e.g., BNA) only appears separately when its count exceeds the base network count, meaning the issuer is offering an exclusive better deal.

`_parse_plans()` replicates this exactly. Do not simplify it to "max count per network" — that would miss issuer-exclusive promotions. Do not include all counts — that would duplicate options the website doesn't show.

#### 22. Fravega `_post_gql` must keep its 2-attempt retry with `asyncio.sleep(2)`

The `_post_gql` method retries once on any exception, sleeping 2 seconds between attempts. This retry is **critical**: under high concurrency (50+ simultaneous GQL calls), Fravega's server sporadically resets connections on the first attempt. Without the retry, those calls fail permanently rather than succeeding on the second try.

If you override `_post_gql` in a subclass (e.g., for benchmarking instrumentation), you must preserve this retry loop. Dropping it causes "Recv failure: Connection was reset" crashes that abort the entire search.

#### 23. Fravega shipping cache is implemented but disabled — flip for v1 launch

`_SHIPPING_CACHE_ENABLED = False` in `platforms/fravega.py`. The cache is a TTL-based in-memory dict keyed on `(sku, seller_id, postal_code)` with a 24-hour expiry. When enabled, it eliminates the ~27s shipping wall-time on repeated queries by returning cached results.

It is left disabled during development so that live shipping data is always fetched and cache bugs cannot mask stale results. **Before going live (v1 launch), set `_SHIPPING_CACHE_ENABLED = True`.**

Note: the cache is process-local (not persisted to DB). It is cleared on restart and does not survive deployments. For a production deployment that restarts frequently, consider persisting shipping results to the SQLite DB instead.

#### 24. Importing `platforms.fravega` directly before `adapters/__init__.py` loads triggers a circular import

The normal import chain is: `service.py` → `adapters/__init__.py` → `adapters/fravega.py` → `platforms/fravega.py`. This works fine.

If you try to `from electrodomestics_bot.platforms.fravega import _session` (or any other symbol) **before** `adapters/__init__.py` has been imported in the same process, Python may encounter a circular import depending on load order. Always import the platform module through the adapter or the standard package entry point, not directly.

#### 25. Fravega search returns all variants under one item — first SKU/seller wins

Unlike VTEX (which returns one item per variant with its own `commertialOffer`), Fravega's search API bundles all SKU variants under a single result. The platform extracts `skus.results[0]` (first SKU) and `sellers[0]` (first seller). In practice this is the primary variant (the one shown by default on the product page), but it may not be the cheapest. This is consistent with how the store displays its own search results.

---

### Megatone / Doofinder v6 (`platforms/megatone.py`)

#### 26. Doofinder requires `Origin` header — bare requests return 403

Doofinder's v6 API enforces domain whitelisting: every request must include `Origin: {store_base_url}` (and optionally `Referer: {store_base_url}/`). A bare GET with no `Origin` header returns HTTP 403. Always pass `self._origin_headers` on every Doofinder request.

#### 27. Use a single representative SKU for `retornarplanes` — never call it per-product

The `Productos` field in the `retornarplanes` POST payload accepts a list of SKU strings. However, sending a mixed list of eligible SKUs causes the API to return only the **intersection** of plans valid for all of them — which collapses to nothing when products have different plan eligibility. The correct approach is to send a single representative SKU (the highest-priced eligible product), then apply the resulting tiers to all eligible products.

The calls fire in parallel via `asyncio.gather`: individual card network calls (`_CARD_CALLS`: Visa/5, Mastercard/3, AmEx/2, Cabal/6, NaranjaX/7), a Directo/debit call (18), a comprehensive fallback (0, for Mercado Pago), and `IdTarjeta=5` with each bank ID in `_BANK_PROMOS`.

#### 28. Megatone installment amounts are calculated, not read from the API

For 0% interest plans (`tasaDirecta == 0`), the installment amount is exactly `price / count`. The API's `valor` field is not needed and not used. This is intentional: the API returns a single `valor` per batch (computed from the `Capital` parameter), but each product has its own price. Calculating amounts locally (`price / count`) avoids per-product API calls.

#### 29. Bank promos only appear when they beat base Visa — mirrors website display

The `_BANK_PROMOS` entries (BNA, Galicia, BBVA, Santander, Santa Fe, Entre Rios, San Juan, Santa Cruz — 8 banks total) offer Visa-exclusive sin-interés tiers that exceed the generic Visa tier. `_fetch_card_counts()` adds a bank to the installment list only when its best count exceeds `visa_max`. If a bank only matches Visa (e.g., both 3x), it is suppressed — consistent with how the Megatone website collapses duplicate rows.

#### 30. VTEX `commertialOffer` installments include non-credit-card payment types

The `Installments[]` array from VTEX's `commertialOffer` includes boleto (bank slip), debit cards, and other payment methods alongside credit cards. These have `PaymentSystemGroupName != "creditCardPaymentGroup"` and appear as spurious multi-installment entries (e.g., "3x" for debit). The platform now filters to `creditCardPaymentGroup` only. Do not remove this filter — it was added because stores like Castillo were showing debit/boleto installments as if they were card promotions.

#### 31. `international` is `Optional[bool]` — `None` means "concept doesn't apply"

For regional stores that don't have international marketplace products (e.g., Castillo in Tucumán), `_is_international()` returns `None` instead of `False`. This is a semantic distinction: `False` means "we checked and it isn't international"; `None` means "this field is meaningless for this store." The display layer renders `None` as `-`, and the cache layer stores it as `0` (same as `False` for now). When adding a new regional store, override `_is_international()` to return `None` if the concept doesn't apply.

---

## Context Window Management Rules

- At the start of each session, check .claude/handoff.md for context from previous sessions.
- When working in multi-session mode, read .claude/shared-context.md at session start and update it when making architectural decisions.

### Compaction Rules
When running /compact on this project, always preserve:
- The full list of files modified in the current session and their paths
- The name, platform, and base_url of any adapter currently being worked on
- Any test commands or validation steps that are in progress
- The Golden Rule: platform logic in platforms/, store quirks in adapters/
- Any pending schema migrations or cache changes
- Error messages or debugging findings that have not yet been resolved

### Session Discipline
- Run /context at the start of every session to check token budget
- Compact proactively at 60% context usage, not at 80%+
- Use /clear when switching between unrelated tasks (e.g., VTEX work to Magento work)
- Use /btw for quick syntax or API lookups that do not need to persist in context
- Before /clear, always write session state to .claude/handoff.md

### Autonomous Tool Use — Non-Negotiable Rules

These rules apply in every session without waiting for user instruction:

**After writing code:**
- After writing or significantly modifying any file, invoke the `simplify` skill autonomously to review it for quality and efficiency. Do not skip this step.


**When exploring the codebase:**
- Whenever a task requires reading more than 3 files or doing open-ended search, spawn an `Explore` agent instead of reading files directly. This protects main context.

**When researching a new store:**
- Always delegate to a general-purpose agent for store research (platform detection, API discovery, URL fetching). Never fetch external URLs from the main context.

**Context management:**
- At 60% context usage, invoke `/handoff` to write `.claude/handoff.md`, then run `/compact`. Do not wait for the user to ask.

**Validation after refactors:**
- After completing any multi-step refactor, spawn a general-purpose agent to run the validation checklist (e.g., `python run.py`, import checks) and report results.

### Subagent Delegation
- Use subagents for any task that involves reading more than 3 files or fetching URLs
- Use subagents for researching new stores (platform detection, API exploration)
- Use subagents for running test queries across adapters
- Prompt pattern: "Use a subagent to investigate [specific question]"

### File Reading Discipline
- Never read an entire file if you only need a specific function. Use line ranges.
- Prefer Grep/Glob to locate code before reading files.
- After reading a file, extract the information you need and do not re-read it.

### Model Usage
- Use Sonnet for routine implementation (adapters, bug fixes, formatting)
- Use Opus only for architecture decisions (new platform support, cache redesign)
- Use UltraThink only for complex multi-file planning
