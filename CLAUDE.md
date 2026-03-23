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
└── electrodomestics_bot/
    ├── __main__.py                     ← CLI: reads input, calls search, prints results
    ├── core.py                         ← http_get(), matches_query(), search_all_stores()
    ├── models.py                       ← ProductResult and Installment dataclasses
    ├── display.py                      ← formats and prints results to terminal
    ├── platforms/                      ← INFRASTRUCTURE LAYER
    │   ├── magento.py                  ← All Magento 2 + Summa Solutions logic
    │   └── vtex.py                     ← All VTEX Intelligent Search logic
    └── adapters/                       ← STORE LAYER
        ├── base.py                     ← StoreAdapter ABC
        ├── __init__.py                 ← ADAPTERS list (edit this to add/remove stores)
        ├── cetrogar.py                 ← CetrogarAdapter(MagentoAdapter) — 5 lines
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
| `international` | `bool` | "Compra Internacional" marketplace products |
| `url` | `str` | Direct product page URL |

`Installment` fields: `count` (number of installments), `amount` (price per installment), `cards` (list of card/bank names offering this option).

## Current Stores

| Store | Platform | Adapter | Notes |
|---|---|---|---|
| Cetrogar | Magento 2 + Summa Solutions | `adapters/cetrogar.py` | |
| OnCity | VTEX Intelligent Search | `adapters/oncity.py` | `verify_ssl=False` due to cert issue |

## Platform Details

### VTEX (`platforms/vtex.py`)
- Search: `/_v/api/intelligent-search/product_search/?query={}&count=50&page={N}` — paginated, capped at 10 pages (500 results)
- Pagination: response contains `pagination.count` (total pages); pages fetched in parallel via `ThreadPoolExecutor(max_workers=5)`
- Shipping simulation: `/api/checkout/pub/orderForms/simulation` (POST), capped at `max_workers=10`; skipped for unavailable products
- Price and installments read from `commertialOffer` in the search response — no extra page fetch needed
- Multi-seller products: always use `_get_real_seller()` — international/marketplace products have a dummy seller "1" with Price=0 alongside the real seller
- Availability: `AvailableQuantity > 0` on any seller
- International products: detected via `categories` containing `/Compra Internacional/` or `productClusters` named "Compra Internacional"
- Free shipping: detected via simulation API — any `slas[]` entry with `deliveryChannel == "delivery"` and `price == 0`

### Magento 2 + Summa Solutions (`platforms/magento.py`)
- Search: `/catalogsearch/result/index/?q={}&p={N}` — full HTML search results, ~40 products/page, paginated, capped at 10 pages (~400 results)
- Pagination: max page number extracted from `?p=N` links in the response HTML; pages fetched in parallel via `ThreadPoolExecutor(max_workers=5)`
- Product data parsed from `<li class="product-item">` elements: name/SKU from `data-mage-init` `ajaxWishlist` JSON, price from `data-price-type="finalPrice"` `data-price-amount` attribute, URL from `<a class="product-item-info">`
- Installments: extracted directly from `div.installment-info` inside each search result `<li>` — no extra page fetches needed. Shows one option per product (best/featured, count + amount only, no card names). `_fetch_installments()` still exists for subclass use if full card data is needed.
- Card names: not available from search results page; only obtainable by fetching individual product pages via `_fetch_installments()`
- Free shipping: always `False` (Magento stores in scope don't offer it)
- Availability: always `True` (catalogsearch only surfaces in-stock products)

## Golden Rule: Infrastructure First

**Before implementing any new feature or fix, always ask:**

> "Is this behavior determined by the platform (VTEX/Magento or any other), or is it unique to a specific store?"

- If it's **platform behavior** → implement in `platforms/vtex.py` or `platforms/magento.py`
- If it's truly **store-specific** (a quirk of one site) → implement as an override in the store's adapter file

The goal is that adding a new store requires nothing more than declaring its `name` and `base_url`. Every feature in `platforms/` is automatically inherited by all current and future stores on that platform.

### Decision table

| Feature | Where it lives | Why |
|---|---|---|
| VTEX price extraction | `platforms/vtex.py` | Standard VTEX API contract |
| VTEX availability detection | `platforms/vtex.py` | Standard VTEX API contract |
| VTEX free shipping simulation | `platforms/vtex.py` | Standard VTEX checkout API |
| VTEX international product detection | `platforms/vtex.py` | Standard VTEX taxonomy fields |
| VTEX multi-seller / real seller resolution | `platforms/vtex.py` | Standard VTEX API structure |
| Magento 2 price HTML parsing | `platforms/magento.py` | Standard Magento price widget |
| Summa Solutions installment scraping | `platforms/magento.py` | Scraped from `div.installment-info` on search page (no extra fetches); `_fetch_installments()` available for full card data |
| Summa card logo filename map | `platforms/magento.py` | Same CDN filenames across all Summa stores (used by `_fetch_installments` only) |
| OnCity SSL workaround (`verify_ssl=False`) | `adapters/oncity.py` | OnCity-specific certificate issue |

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

Then add `NewStoreAdapter()` to the `ADAPTERS` list in `adapters/__init__.py`.

### Overridable class attributes

| Attribute | Default | Platform | When to override |
|---|---|---|---|
| `postal_code` | `"1425"` (Buenos Aires) | VTEX | Different delivery region |
| `verify_ssl` | `True` | VTEX | Store has broken SSL cert |
| `card_keywords` | standard Summa map | Magento | Store uses non-standard card logo filenames |

## Known Patterns and Gotchas

- **VTEX international products** have two sellers in the API: a dummy `seller="1"` with `Price=0` and `AvailableQuantity=0`, and the real marketplace seller. Always use `_get_real_seller()` — never index `sellers[0]` directly.
- **Cetrogar installments** require fetching every product page individually. This is inherently slow; parallelism via `ThreadPoolExecutor` is critical.
- **`matches_query()`** in `core.py` filters results so that only products containing all query words appear — compensates for stores returning loosely-related suggestions.
- **SSL warnings** are globally suppressed in `core.py` (`warnings.filterwarnings("ignore")`) because several stores have certificate issues.
- The `currency` field is hardcoded to `"ARS"` — all stores currently in scope are Argentine.

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
