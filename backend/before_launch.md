# Before Launch Checklist

Things to configure or verify before running this in a client-facing production environment.
None of these are show-stoppers for local dev or private betas — they are intentionally left at permissive defaults during development.

---

## 0. Re-enable the product cache

**File:** `electrodomestics_bot/fetching/cache.py` → `CACHE_DISABLED`

The SQLite product cache (`data/cache.db`) is currently **disabled** via `CACHE_DISABLED = True`. Every search hits the live store APIs, no rows are read from or written to `cache.db`, and the daily refresh job is not registered with the scheduler (`scheduler.py` skips it; `refresh.py` early-exits if invoked manually).

**Why it's off:** while iterating on shipping/postal-code logic, stale cached `free_shipping` values repeatedly masked bugs and made testing unreliable. Going live without caching gives accurate per-request results at the cost of latency.

**To re-enable:** set `CACHE_DISABLED = False` in `cache.py`. Nothing else needs to change — `service.py`, `refresh.py`, and `scheduler.py` all read this flag at runtime. After flipping it, also revisit:

- Rate limits (item 6) — caching dramatically reduces upstream load, so you may want lower per-IP limits without it.
- The daily refresh cron (item 4) — only meaningful with the cache on.
- The data directory (item 5) — `cache.db` is only created when the cache is enabled.

---

## 1. Set CORS origins (security)

**File:** `electrodomestics_bot/config.py` → env var `CORS_ORIGINS`

The default is now `[]` (block all cross-origin requests). Before launch, set the env var to the exact origin(s) your frontend will be served from:

```
CORS_ORIGINS=https://myapp.com,https://www.myapp.com
```

Do **not** use `*` in production unless you have a deliberate reason (e.g. a fully public, read-only API with no user authentication).

---

## 2. Configure Supabase JWT verification (auth)

**File:** `electrodomestics_bot/config.py` → env vars `SUPABASE_URL`, `SUPABASE_JWT_SECRET`

Auth supports two modes (see `auth.py`):

- **ES256/RS256 (current Supabase default):** the JWT is verified against the project's JWKS endpoint. Requires `SUPABASE_URL=https://<project>.supabase.co`.
- **HS256 (legacy shared-secret):** verified against `SUPABASE_JWT_SECRET` from the Supabase dashboard (Settings → API → JWT Secret).

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_JWT_SECRET=your-legacy-hs256-secret      # only needed for HS256 tokens
```

The following endpoints reject every call until at least one of these is configured for the algorithm of the incoming token: `/search`, `/stores`, `/health/detail`, `/health/anomalies`, `POST /health/anomalies/{id}/acknowledge`. The plain `/health` is a public liveness probe and stays open by design.

---

## 3. Configure Telegram alerts (monitoring)

**File:** `electrodomestics_bot/config.py` → env vars `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

Anomaly alerts and canary failure notifications are fire-and-forget Telegram messages. If these env vars are empty, alerts are silently skipped — you will not know when stores start returning bad data.

```
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
```

Optionally adjust `ALERT_MIN_SEVERITY` (default: `critical`) to also receive `warning`-level anomalies.

---

## 4. Tune the refresh schedule (scheduler)

**File:** `electrodomestics_bot/config.py` → env vars `REFRESH_CRON`, `CANARY_INTERVAL_HOURS`

Defaults:
- Cache refresh: `0 8 * * *` (daily at 08:00 UTC) — **inert while `CACHE_DISABLED=True`** (see item 0); the scheduler does not register the job.
- Canary health probes: every 4 hours — runs regardless of cache state, since canaries hit live store APIs and only write to `monitoring.db`.

Adjust these to match your expected traffic patterns and how stale you can tolerate the cache being. The refresh cron runs against all stores simultaneously, so make sure your host can handle the outbound HTTP load at the scheduled time.

---

## 5. Verify the data directory is writable (storage)

**File:** `electrodomestics_bot/config.py` → env var `DATA_DIR`

Default: `./data/` relative to the project root. While `CACHE_DISABLED=True` only `monitoring.db` and the on-disk image cache (`images/`) live here. Once the product cache is re-enabled (item 0), `cache.db` is also written here. In containerized deployments, make sure this path is a mounted volume — otherwise data is lost on container restart.

```
DATA_DIR=/var/data/electrodomesticsbot
```

---

## 6. Review rate limits (API)

**File:** `electrodomestics_bot/api.py`

Current limits (per IP, via `slowapi`):
- `GET /search` → 10 requests/minute
- `GET /stores` → 20 requests/minute
- All other endpoints (`/health`, `/health/detail`, `/health/anomalies`, `POST /health/anomalies/{id}/acknowledge`) → unlimited

These limits assume the cache is on. With `CACHE_DISABLED=True` (see item 0), every `/search` triggers live calls to all configured stores in parallel — consider lowering the per-IP cap until the cache is re-enabled.

If you expect higher traffic or want to differentiate limits by client (e.g. per API key instead of per IP), the `slowapi` limiter will need a different `key_func`.

---

## 7. Decide on the Fravega shipping check threshold

**File:** `electrodomestics_bot/fetching/platforms/fravega.py` → `_MAX_SHIPPING_CHECKS`

Current value: `50`. Broad queries (e.g. brand-only searches like "Samsung") can return hundreds of Fravega products — shipping is skipped for all of them when the count exceeds this threshold, and `free_shipping=False` is returned for every product.

If accurate shipping data matters for your use case, lower the threshold (narrower queries get shipping, broader ones don't) or raise it (more coverage, slower broad queries). See CLAUDE.md gotcha #20 for the performance tradeoff.

---

## 8. OnCity SSL certificate

**File:** `electrodomestics_bot/fetching/adapters/oncity.py` → `verify_ssl = False`

OnCity has a broken SSL certificate, so TLS verification is disabled for that adapter. This suppresses a real security check. Before launch, re-test whether OnCity's certificate has been fixed (`curl -v https://www.oncity.com.ar`) and remove the override if it has.

---

---

## [PRICING TOOL] Known Gaps in Payment Plan Coverage

These are data completeness limitations specific to the pricing spreadsheet tool (`run_pricing.py`). They are not bugs — the code correctly reads what the stores' APIs provide — but they cause some Excel cells to remain empty even when a plan is visible on the store's website.

### VTEX stores: con-interés plans may be missing for some card brands

**Affected stores:** OnCity (and potentially any future VTEX store)

**What happens:** For certain card brands (confirmed: NaranjaX on OnCity), the VTEX search API's `commertialOffer.Installments` only includes the **promotional** rates configured in the store's VTEX admin — typically the sin-interés promos. Standard con-interés bank rates are computed by VTEX's payment engine at checkout time and are **not** included in `commertialOffer`. As a result, Excel rows for e.g. "NARANJAX 10 c/i" or "NARANJAX 12 c/i" may stay empty even though those options are visible on the product page.

**Example:** For TCL 85P8K on OnCity, the website shows NaranjaX at 10x and 12x con-interés, but the VTEX API only returns Naranja at 1x/6x/9x/11x/12x all sin-interés. Row 31 (NARANJAX 10x con) is left blank as a result.

**Why it's not trivially fixable:** The con-interés rates are dynamic (set by the card issuer, not the store) and aren't exposed in the search API. A correct fix would require querying VTEX's checkout simulation API for each product, which is a significant architectural change.

**Workaround available for sin-interés gaps:** For cards where the store has promotions but the API omits them (e.g. MercadoPago sin-interés on OnCity), we already synthesize plans via `_STORE_MP_SIN_TIERS` in `pricing/service.py`. A similar approach could be used for other known sin-interés gaps if the tier counts are stable. Con-interés gaps cannot be synthesized because the interest rates are dynamic.

### Montes Hermanos: most Visa/MC template rows stay blank (no bank-specific promos)

**Affected store:** Montes Hermanos (column H)

**What happens:** The template's Visa/Mastercard rows are all bank-qualified — every row is either "VISA/MASTER MACRO" or "VISA/MASTER NACION". Montes Hermanos does not differentiate by issuing bank: their installment endpoint returns a single generic Visa plan and a single generic Mastercard plan with no bank issuer. Because no plan has `card_issuer="macro"` or `card_issuer="nacion"`, none of those rows match and column H stays blank for them.

**What does fill:** NARANJAX rows where Montes has a matching count and interest type. For the Philips 55PUD7309 (727,999 ARS), rows 29 (NARANJAX 9x con, 18.75%) and 33 (NARANJAX 12x con, 25.0%) fill. Montes' Visa installments are 1x sin interés and 3x/6x/12x con interés — the template has no generic (non-bank-qualified) Visa rows for those counts.

**Why it's correct behavior, not a bug:** Montes simply doesn't offer Banco Macro or Banco Nación promotions. An empty cell accurately means "this promo is not available at this store." Filling those cells with the generic Visa rate would misrepresent the situation.

**How to add more Montes coverage:** Add new template rows in the Excel file with a label like `"VISA/MASTER"` (no bank qualifier) for the counts Montes covers (3x, 6x, 12x con interés), then add `"VISA/MASTER": (frozenset({"visa", "mastercard"}), None)` to `_LABEL_MAP` in `pricing/card_mapping.py`. Those new rows would then fill automatically.

---

## Notes

- SSL warnings are globally suppressed in `fetching/core.py` (`warnings.filterwarnings("ignore")`). This is intentional (several stores have cert issues) but means certificate errors from unexpected sources will also be silent.
- The `currency` field is hardcoded to `"ARS"`. If you ever expand beyond Argentine stores, this needs to be made per-adapter.
