# Backend ↔ Frontend Bridging Plan

This document is the single source of truth for everything needed to connect the
FastAPI backend (`backend/`) to the React frontend (`frontend/`). It covers every
layer — from environment config to UX decisions — and flags the open questions
that require product input before implementation can begin.

Files produced during bridging live in this `bridging/` folder until they are
moved into their final locations in `backend/` or `frontend/`.

**Legend:** ✅ Done · 🔲 Pending · ⚠️ Blocked · ❓ Awaiting decision

---

## Current State Snapshot

### What the backend exposes

The backend is a production-grade FastAPI application. Its primary endpoint for
the frontend is:

```
GET /search?q={query}&detail={bool}
Authorization: Bearer {supabase_jwt}
```

**Response shape (`SearchResponse`):**
```json
{
  "query": "Samsung S24 Ultra",
  "results": {
    "fravega":        [ ProductResponse, ... ],
    "megatone":       [ ProductResponse, ... ],
    "cetrogar":       [ ProductResponse, ... ],
    "castillo":       [ ProductResponse, ... ],
    "oncity":         [ ProductResponse, ... ],
    "monteshermanos": [ ProductResponse, ... ]
  },
  "store_status": {
    "fravega": { "status": "ok", "result_count": 12, "duration_ms": 4200 },
    ...
  }
}
```

**`ProductResponse` fields:**
| Field | Type | Notes |
|---|---|---|
| `name` | `str` | Product name as listed by the store |
| `sku` | `str \| null` | Store SKU |
| `price` | `float \| null` | Final price in ARS |
| `currency` | `str` | Always `"ARS"` |
| `url` | `str` | Direct product page URL |
| `installments` | `InstallmentResponse[]` | Sin-interés options only |
| `free_shipping` | `bool` | Based on Buenos Aires postal code |
| `international` | `bool \| null` | `null` = concept doesn't apply to this store |
| `available` | `bool` | In-stock status |
| `image_url` | `str \| null` | Raw CDN URL from the store's search response (VTEX `items[].images[].imageUrl`, Megatone `image_link`, Magento `image_src`). Null when the store doesn't expose an image. Frontend resolves it as-is — no API base URL prefix. |

**`InstallmentResponse` fields:**
| Field | Type | Notes |
|---|---|---|
| `count` | `int` | Number of installments |
| `amount` | `float` | Amount per installment in ARS |
| `cards` | `str[]` | Card/bank names. Empty in fast mode (`detail=false`); full names in slow mode (`detail=true`) |

**Other available endpoints:**
- `GET /stores` — list of all configured stores with name, base_url, platform
- `GET /health` — public liveness probe (no auth)
- `GET /health/detail` — full system health (auth required)
- `GET /health/anomalies` — open monitoring anomalies (auth required)
- `POST /health/anomalies/{id}/acknowledge` — mark anomaly resolved (auth required)

**Auth:** Every endpoint except `GET /health` requires a valid Supabase JWT in the
`Authorization: Bearer {token}` header. The backend validates this via
`backend/electrodomestics_bot/auth.py`.

**Static files:** Product images are now passed through as raw CDN URLs from
each store's search response. Backend no longer downloads or proxies images —
the `/images/` static mount remains for the (currently unused) on-disk image
cache helper but is not part of the search response path. Stores that expose
an image: VTEX (Castillo, Cetrogar, OnCity, Montes Hermanos) via
`items[].images[].imageUrl`, Megatone via Doofinder's `image_link`. Fravega
returns `image_url: null` (its GQL search response does not include images).

**CORS:** Already configured on the backend. `allow_origins` is read from
`settings.cors_origins` in `backend/electrodomestics_bot/config.py`. As of the
env setup (Item 1), `http://localhost:8080` is configured for development.

---

### What the frontend has

The frontend is React 18 + TypeScript + Vite, using:
- **React Router v6** for routing
- **TanStack React Query v5** already instantiated in `App.tsx` but making zero
  real API calls
- **shadcn/ui + Radix UI** for all components
- **Recharts** for the price bar chart and price history line chart
- **Tailwind CSS** with a custom IBM Plex Sans/Serif/Mono typography stack

**Current routes:**
| Route | Component | Status |
|---|---|---|
| `/` | `Landing.tsx` | Functional UI, fake search (timeout + navigate) |
| `/producto?q=` | `ProductIntelligence.tsx` | Functional UI, 100% mock data |
| `/signin` | `SignIn.tsx` | Functional UI, form does nothing |
| `/*` | `NotFound.tsx` | Complete |

**Current mock data stores** (in `src/data/mockData.ts`):
- Mercado Libre, Fravega, Garbarino, Musimundo, Megatone

**Real backend stores:**
- fravega, megatone, cetrogar, castillo, oncity, monteshermanos

These two lists do not overlap completely. `mockData.ts` must be replaced or
retired once hooks are wired.

---

### Supabase project

- **Project URL:** `https://afoypmakehcuxydfmi.supabase.co`
- **Anon key:** configured in `frontend/.env.development` and `frontend/.env.production`
- **JWT secret:** configured in `backend/.env`
- **Public signup:** must be disabled in the Supabase dashboard
  (Authentication → Sign In / Providers → Email → toggle "Enable sign ups" OFF)
- **User management:** done manually via Authentication → Users → Add user.
  You create the email + password, hand credentials to the client.

---

## Bridging Work Items

Items are listed in dependency order.

---

### ✅ Item 1 — Environment & Vite proxy config

**Completed.** All env files created and gitignored. Vite proxy added.

**What was done:**
- Created `frontend/.env.development` with `VITE_SUPABASE_URL`,
  `VITE_SUPABASE_ANON_KEY`, and `VITE_API_BASE_URL=http://localhost:8000`
- Created `frontend/.env.production` with the same Supabase values and a
  `REPLACE_WITH_PRODUCTION_API_URL` placeholder for the API base URL
- Created `backend/.env` with `SUPABASE_JWT_SECRET` and
  `CORS_ORIGINS=["http://localhost:8080"]`
- Updated `frontend/vite.config.ts` to proxy `/api/*` → `http://localhost:8000/*`
  (strips the `/api` prefix so `/api/search` hits `GET /search` on the backend)
- Updated `backend/.gitignore` to block `.env`, `.env.local`, `.env.*.local`
- Updated `frontend/.gitignore` to block `.env`, `.env.development`,
  `.env.production`, `.env.local`, `.env.*.local`

**Note on the proxy:** In development the API client can call either the full URL
(`http://localhost:8000/search`) or the proxied path (`/api/search`). The proxy
exists as a fallback and for future use — the current plan uses the full URL via
`VITE_API_BASE_URL`.

---

### ✅ Item 2 — Auth bridge

**Completed.** Supabase auth is wired end-to-end. Typecheck and production build pass.

**What was done:**

- Installed `@supabase/supabase-js` (added to `frontend/package.json`)
- Created `frontend/src/lib/supabase.ts` — singleton client initialised from
  `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` (throws at import time if
  either is missing, surfacing config bugs immediately)
- Created `frontend/src/contexts/AuthContext.tsx` — `AuthProvider` wraps the
  tree; `useAuth()` exposes `{ session, token, isLoading, signOut }`. Subscribes
  to `onAuthStateChange` so updates propagate across tabs and post-refresh
- Created `frontend/src/components/ProtectedRoute.tsx` — shows a spinner while
  `isLoading`, then redirects to `/signin` (preserving the requested path in
  router state under `from`) if no session, otherwise renders children
- Updated `frontend/src/App.tsx` — `AuthProvider` mounted inside `BrowserRouter`;
  `/` (Landing) and `/producto` are wrapped in `ProtectedRoute`; `/signin` stays
  public; catch-all `*` (NotFound) stays public
- Updated `frontend/src/pages/SignIn.tsx` — form is now controlled (email +
  password state), submit calls `supabase.auth.signInWithPassword()`, error
  banner shows on failure ("Invalid login credentials" → "Credenciales
  invalidas"), button disables + shows "INGRESANDO..." while in flight, on
  success navigates to the original `from` path (or `/`). If an already-
  authenticated user lands on `/signin`, they are redirected away
- Updated `frontend/src/components/TopNav.tsx` — calls `useAuth()`. When
  signed in, the third nav slot becomes a "Salir" button that calls `signOut()`
  and navigates to `/signin`. When signed out, it stays as the "Entrar" link

**Reminder for the user:** Before testing, disable public signups in the
Supabase dashboard → Authentication → Sign In / Providers → Email → toggle
"Enable sign ups" OFF. Then add a test user via Authentication → Users → Add
user.

**Not yet verified:** The auth flow was not exercised in a real browser — only
typecheck (`tsc --noEmit`) and the Vite production build pass. First user-facing
test: `npm run dev` in `frontend/`, navigate to `/`, expect redirect to
`/signin`, sign in with a Supabase-created user, expect redirect back to `/`.

---

### ✅ Item 3 — Typed API client

**Completed.** `frontend/src/lib/api.ts` exports the full backend response surface
plus `searchProducts()` and `listStores()`. Typecheck and lint pass.

**What was done:**

- Created `frontend/src/lib/api.ts` — single source for all backend calls
- TypeScript interfaces mirror the Pydantic models in
  `backend/electrodomestics_bot/models.py` exactly: `InstallmentResponse`,
  `ProductResponse`, `StoreStatus` (literal union), `StoreStatusResponse`,
  `SearchResponse`, `StoreInfo`
- `ApiError extends Error` carries `status` so callers (Item 12 error states,
  Item 13 rate-limiting) can distinguish 401, 429, 503 etc.
- Private `apiFetch<T>()` helper handles base URL prefix, `Authorization: Bearer`
  header, JSON parsing, and `ApiError` throwing on non-2xx (parses `detail` /
  `error` from the body when present, falls back to `statusText`)
- Module throws at import time if `VITE_API_BASE_URL` is unset (same pattern as
  `supabase.ts` — surfaces config bugs immediately)
- Public functions accept an optional `init?: RequestInit` so React Query in
  Item 6 can pass `signal` for cancellation

**Endpoints intentionally not yet wrapped:** `/health/detail`,
`/health/anomalies`, `POST /health/anomalies/{id}/acknowledge`. Add when the
admin panel work begins (no consumer exists today; adding now would be dead
code).

**File created:** `frontend/src/lib/api.ts`

---

### ✅ Item 4 — Product selection UX

**Completed.** Both pages now run on real API data via `useSearch`; the
Landing → ProductIntelligence URL contract uses `{store, url}[]` and
ProductIntelligence reconciles it against the live response with
`applySelection` (auto mode falls back to `autoSelectProducts`).

**How it works (already implemented structurally):**

`Landing.tsx` has a "Busqueda selectiva" checkbox (`selectiveSearch` state):

- **Checked (selective mode):** After search completes, the page reveals a
  per-store accordion list. Each store is collapsible and shows all matching
  products as checkbox rows (radio-like: one per store). User selects one product
  per store, then clicks "Comparar" → navigates to `/producto`.
- **Unchecked (auto mode):** After search completes, the page auto-selects the
  cheapest available product per store and navigates to `/producto` immediately.
  Intended for queries specific enough that result variance is low.

**The URL contract between Landing and ProductIntelligence:**

Currently the `selected` param carries `{store, name, price}[]` (mock-era format).
This must change to `{store: string, url: string}[]` — URL is the only guaranteed
non-null identifier on every real `ProductResponse`.

```
/producto?q=PlayStation%205%20Slim&selected=[{"store":"fravega","url":"https://..."},...]
```

`ProductIntelligence.tsx` reads `selected`, re-fetches `GET /search?q=`, then
filters each store's result array to the product whose `.url` matches. If no
`selected` param is present, it falls back to auto-select (cheapest available).

**Why re-fetch in ProductIntelligence rather than passing full data through URL:**
- URL-encoding a full `SearchResponse` is fragile and bloated
- React Query caches by key; if Landing already fetched `["search", q, false]`,
  ProductIntelligence's `useSearch(q)` call returns from cache instantly (no
  network round-trip)
- Works correctly on page refresh and direct URL navigation

**Current state of the selected param pipeline:**

`Landing.tsx` → `handleCompareSelection` → passes `{store, name, price}[]` in URL

`ProductIntelligence.tsx` → `parseSelectedComparisons()` → reads that format,
builds `SelectedComparisonPrice[]` (extends `StorePrice`), sets
`isSelectiveComparison = true`. Currently stubs three fields with placeholder values:
- `url: "#"` (no real link yet)
- `inStock: true` (always)
- `freeShipping: index % 2 === 0` (fake alternation)

The `comparisonPrices` memo switches between `selectedComparisonPrices` (selective
mode) and `product.prices` from mockData (fallback). The page renders correctly
end-to-end for the mock flow.

**What needs to change when wiring to the real API:**

The `{store, name, price}[]` URL format must be expanded to include all fields
needed for display. For real data, `handleCompareSelection` should encode:

```ts
type SelectedEntry = {
  store: string      // store key, e.g. "fravega"
  name: string       // product name
  price: number
  url: string        // real product page URL (always non-null from API)
  available: boolean
  freeShipping: boolean
  bestPromo: string | null  // pre-formatted, e.g. "12x sin interés"
}
```

`parseSelectedComparisons()` in `ProductIntelligence.tsx` must be updated to parse
this richer format and stop stubbing the placeholder values.

**What needs to be built:**
1. In `Landing.tsx`:
   - Replace `MOCK_STORE_RESULTS` with real data from `useSearch(q)` (see Item 6)
   - Enrich `handleCompareSelection` to include `url`, `available`, `freeShipping`,
     `bestPromo` in the selected entries
   - Auto-select logic: when `selectiveSearch=false`, pick cheapest available per
     store from real API response and navigate immediately
   - Wire the fake timeout/progress bar to real React Query `isLoading` state
2. In `ProductIntelligence.tsx`:
   - Update `parseSelectedComparisons()` to parse and validate the richer format
   - Remove the three stubbed placeholder fields once real data flows through
   - Replace the `findProduct()` + mockData fallback path with `useSearch(q)` +
     auto-select from real response (for the non-selective / direct URL nav case)

---

### ✅ Item 5 — Data model transformation layer

**Completed.** `frontend/src/lib/transforms.ts` exists with `formatPrice`,
`bestSinInteresCount`, `formatBestPromo`, `searchToStoreGroups`,
`autoSelectProducts`, `applySelection`, and `resolveImageUrl`. Both Landing
and ProductIntelligence shape data exclusively through these helpers — no
component touches `SearchResponse` directly. The shape diverges slightly from
the original sketch below (`SelectedProduct` instead of `PerStoreProduct`, no
`deriveMetrics` since the consumer that needed it was retired).

**What:** `frontend/src/lib/transforms.ts` — all data shaping in one place.
No component touches `SearchResponse` directly.

**Functions to implement:**

```ts
// Landing: convert API response to per-store display groups
export function searchToStoreGroups(
  response: SearchResponse,
  storeKeys: string[]   // from selectedStores state
): StoreGroup[]

// StoreGroup shape (what Landing's accordion renders)
export type StoreGroup = {
  storeKey: string          // e.g. "fravega"
  displayName: string       // e.g. "Fravega"  (from stores.ts)
  results: StoreResult[]
}
export type StoreResult = {
  url: string               // product identifier
  name: string
  detail: string            // "12x sin interés · envío gratis" or similar
  price: number
  available: boolean
}

// Landing auto-mode: pick cheapest available per store
export function autoSelectProducts(response: SearchResponse): Selection[]

// ProductIntelligence fallback: auto-select if no selection param
// (used when user navigates to /producto directly or selectiveSearch=false)
export function autoSelectProducts(response: SearchResponse): PerStoreProduct[]

export type PerStoreProduct = {
  storeKey: string
  displayName: string
  product: ProductResponse
  bestPromo: string | null  // e.g. "12x sin interés"
}

// ProductIntelligence: derive stat cards from selected products
export function deriveMetrics(products: PerStoreProduct[]): Metrics

// Shared: format price in ARS
export function formatPrice(price: number): string  // "$1.234.567"

// Shared: resolve image URL
export function resolveImageUrl(imageUrl: string | null, apiBase: string): string
```

**Auto-select logic:** per store, filter `available: true`, sort by `price ASC`,
take first. If no available product, take first result regardless.

**`detail` string for Landing results:** derived from the product's installment
plan (best count + "sin interés" if applicable) plus free_shipping flag.
Example: `"12x sin interés · envío gratis"` or `"Stock disponible"`.

**File to create:** `frontend/src/lib/transforms.ts`

---

### ✅ Item 6 — React Query hooks

**Completed.** `frontend/src/hooks/useSearch.ts` exists, dedupes by
`["search", q, detail, postalCode]` with a 5 min staleTime, and is consumed
by both Landing and ProductIntelligence. `useStores` was intentionally
skipped — the doc flagged it as optional future use, and there is no store
filter consumer today (would be dead code). Re-add when needed.

**Hooks to create** (in `frontend/src/hooks/`):

```ts
// Primary search hook — used by BOTH Landing and ProductIntelligence
// React Query key: ["search", q, detail]
// Only fires when q is non-empty and enabled=true
useSearch(q: string, detail?: boolean, options?: { enabled?: boolean }): UseQueryResult<SearchResponse>

// Store list hook — used by Landing for the store filter (optional future use)
useStores(): UseQueryResult<StoreInfo[]>

// Health hook — for future admin panel
useHealthDetail(): UseQueryResult<HealthResponse>
```

**Important:** `useSearch` must use `enabled: false` as default and only be
triggered on explicit form submit. This is enforced via the `enabled` option
(tied to a submit counter or a boolean flag in the calling component), not by
query key change. This prevents the 10 req/min rate limit from being hit by
keystrokes or re-renders.

**Files to create:**
- `frontend/src/hooks/useSearch.ts`
- `frontend/src/hooks/useStores.ts`

**Files to modify:**
- `frontend/src/pages/Landing.tsx` — wire search submit to trigger `useSearch`;
  replace fake timeout with query loading state; replace `MOCK_STORE_RESULTS`
  with transformed real data; fix `selected` URL param format
- `frontend/src/pages/ProductIntelligence.tsx` — replace `findProduct()` +
  mockData with `useSearch(q)` + `applySelection()`; wire payment analysis button
- `frontend/src/components/StatsCards.tsx` — replace direct mockData reads

---

### ✅ Item 7 — Store metadata alignment

**Completed.** `frontend/src/lib/stores.ts` exports `STORES`, `STORE_KEYS`, and
lookup helpers. Typecheck and lint pass.

**What was done:**

- Created `frontend/src/lib/stores.ts` — single source for store display metadata
- `StoreKey` literal union mirrors backend response keys exactly: `fravega`,
  `megatone`, `cetrogar`, `castillo`, `oncity`, `monteshermanos`
- `StoreMeta` carries `key`, `displayName`, `color` (HSL string), and `regional`
  flag (true for Castillo only — Tucumán)
- Fravega and Megatone keep their original colors from `mockData.ts` for visual
  continuity. New stores get distinct hues with no collisions: Cetrogar red,
  OnCity orange, Montes Hermanos magenta, Castillo green
- Helper functions: `getStore(key)`, `getStoreDisplayName(key)`,
  `getStoreColor(key)`, `isKnownStoreKey(key)` — all accept the wider `string`
  type so callers can pass raw API keys without casts
- `STORE_BY_KEY` lookup map built once at module load; helpers are O(1)

**`mockData.ts` retirement:** Not yet removed. Keep until hooks (Item 6) are
wired so `ProductIntelligence.tsx` and `StatsCards.tsx` continue to render
during the transition. Delete once nothing imports from it.

**File created:** `frontend/src/lib/stores.ts`

---

### ✅ Item 8 — Image handling

**Status:** Done.

**What was done:**

- Backend now passes raw CDN image URLs straight from each store's search
  response — no proxying, no on-disk download. Implemented in the platform
  layer so every current and future store on that platform inherits it:
  - `platforms/vtex.py` → new `_extract_image()` reads
    `items[].images[].imageUrl` (covers Castillo, Cetrogar, OnCity, Montes
    Hermanos automatically).
  - `platforms/megatone.py` → `_parse_product()` now reads `image_link` from
    the Doofinder response.
  - `platforms/magento.py` → already had `image_src`, unchanged.
  - `platforms/fravega.py` → unchanged; Fravega's GQL search does not return
    image URLs, so it stays `None` (the frontend fallback chain handles it).
- `service.py` no longer downloads or rewrites images — the `download_image`
  call and the per-result rewrite block were removed. `image_cache.py` and the
  `/images/` static mount remain in place but are no longer hit by the search
  path.
- `models.py` docstrings updated to reflect that `image_url` is now a raw
  external URL (no API base prefix needed).
- `frontend/src/pages/ProductIntelligence.tsx` — hero image is now a
  priority-sorted candidate chain with browser-side fallback:
  - Priority order: Cetrogar → OnCity → Castillo → Montes Hermanos → Fravega
    → Megatone (VTEX CDNs first, then everything else).
  - Loading state: spinner overlay shown while the current candidate's
    `<img>` is fetching; image fades in via `opacity` transition once
    `onLoad` fires.
  - Fallback chain: `onError` advances to the next candidate (`key={url}`
    forces React to remount the `<img>` so the browser fetches the new src).
  - When all candidates fail (or none exist), the existing "Sin imagen
    disponible" placeholder is shown.
  - Page renders with all data populated immediately; the image slot loads
    independently in parallel — never blocks navigation or other UI.
- `resolveImageUrl()` already handled both raw `http(s)://` URLs and
  API-relative paths (`/images/...`), so no transform-layer change was
  needed.

---

### ✅ Item 9 — "Solicitar análisis de medios de pago" button

**Status:** Done — scope changed mid-implementation.

**What was done (revised scope):** The original spec wired the button to
`GET /search?q=&detail=true` and refreshed installment cells in-place. We
pivoted to a different deliverable: the button now triggers the existing
pricing-spreadsheet pipeline (separate from `/search`), generates the filled
`.xlsx`, and downloads it directly in the browser.

**Implementation:**
- Backend: new `generate_pricing_excel(query)` non-interactive entry point in
  `pricing/__init__.py`, plus `GET /pricing/excel?q=...` endpoint
  (auth-gated, 5 req/min/IP) that returns the `.xlsx` as a `FileResponse`
  with a proper `Content-Disposition` filename. The interactive CLI
  `run_pricing()` workflow is unchanged.
- Frontend: new `downloadPricingExcel(q, token)` helper in `lib/api.ts`
  parses the filename header and returns `{ blob, filename }`.
  `ProductIntelligence.tsx`'s click handler triggers a real fetch + browser
  download via a transient `<a download>` anchor; the synthetic 2-5s timer,
  fake `%` progress and three timer refs were removed.
- Inline error chip next to the button (`role="alert"`, destructive color,
  same typography as the loading row) localizes `ApiError` for this context:
  `Sin coincidencias en las tiendas.` (404), `Demasiadas solicitudes (429).
  Esperá un momento.`, `Sesión expirada.` (401, also triggers signOut),
  `Sin conexión.` (network), `No se pudo generar el Excel.` (5xx / unknown).
- The `detail=true` toggle on `/search` is still untouched; no consumer
  needs it now that the table is populated by the fast call.

**Not yet surfaced:** partial-store failures (e.g. one of the four pricing
stores erroring while the others succeed) are written as `"-"` cells in the
output — not communicated separately to the UI. Add later if needed via a
custom response header.

---

### ❓ Item 10 — Price history chart

**Status:** Awaiting decision (open question #3).

**The problem:** `ProductIntelligence.tsx` has a 7-month price history line chart.
The backend has no price history data — the monitoring DB tracks operational
health, not per-product prices over time.

**Option A — Add price history tracking (recommended long-term)**

Add a `price_snapshots` table to the backend's monitoring DB. Record
`(store, product_name, sku, price, recorded_at)` on every search run. Build a
`GET /products/{sku}/history` endpoint. Chart fills up over 30+ days of use.

**Option B — Hide the chart until history exists**

Render the chart section only when real data is available. Show a placeholder:
"El historial de precios se irá construyendo con el tiempo."

**Option C — Keep as illustrative placeholder at launch**

Leave mock data powering the chart. Label it "Historial simulado". Replace when
Option A is implemented. Simplest path to launch.

---

### ✅ Item 11 — Postal code support (formerly "Remove CABA filter")

**Status:** Done.

**What:** The `Landing.tsx` search form has a "Shopping from CABA" checkbox.
Checked → backend uses its CABA default (`1425`). Unchecked → user-provided
postal code in an adjacent input is sent to the backend for shipping simulation.

**Implementation:**
- Backend: `/search` accepts `postal_code` query param, validated by FastAPI
  with regex `^[A-Z]?\d{4}[A-Z]{0,3}$` (4-digit or 8-char CPA). Threaded
  through `service.search_products` → `core.search_all_stores` → adapter
  `search(..., postal_code)`. VTEX `_check_free_shipping` and Fravega
  `_fetch_free_shipping` consume it. Magento/Megatone accept the param for
  signature consistency but ignore it (they don't run shipping simulation).
- Cache: custom postal codes bypass both read and write paths
  (`bypass_cache_for_custom_postal`) — the cache stores CABA-default shipping
  per product; serving non-CABA from cache would return stale data and writing
  non-CABA would pollute the CABA cache.
- Frontend: `Landing.tsx` sends `postal_code` URL param only when `!fromCABA`
  and the input is non-empty; `ProductIntelligence.tsx` reads the param and
  shows a `CP {code}` badge mirroring the existing `CABA` badge.
- GQL safety: Fravega interpolates `postal_code` into a GQL query string; the
  FastAPI regex at the API boundary is the only guard keeping that path safe
  from injection. Documented in both `platforms/fravega.py` and `api.py`.

---

### ✅ Item 12 — Loading and error states

**Status:** Done — three tiers shipped.

**Tier 1 — deployment-blocker fixes:**
- New `classifyError(err)` helper in `lib/api.ts` maps `ApiError`/network
  faults to `{ kind, title, body }` for `auth | rate_limit | server |
  network | unknown`.
- `Landing.tsx` and `ProductIntelligence.tsx` consume the helper for inline
  copy; a side-effect `useEffect` triggers `signOut()` on 401 (AuthContext
  clears session, ProtectedRoute routes to `/signin`) and surfaces a sonner
  toast for 429/network.
- Per-store coverage gaps are now visible in the comparison table:
  `unavailableStoreRows` adds muted rows for stores the user *intended* to
  compare that errored, timed out, or returned no products.
- Top-level `ErrorBoundary` (new `components/ErrorBoundary.tsx`) wraps the
  router; render exceptions show a recovery panel with a "Volver al inicio"
  button instead of blanking the screen.

**Tier 2 — quality:**
- React Query retry policy in `useSearch.ts`: one retry on 5xx and network
  faults with exponential backoff (`min(1000 * 2^attempt, 4000)`); never on
  4xx so auth/rate-limit/bad-query surface immediately.
- Dropped the duplicate shadcn toast system — `<Toaster />` mount removed
  from `App.tsx` and `hooks/use-toast.ts`, `components/ui/toast.tsx`,
  `components/ui/toaster.tsx`, `components/ui/use-toast.ts` deleted. Sonner
  is the single toast library.
- Replaced Landing's synthetic 9-second progress ramp with a real
  elapsed-seconds counter (`{N}s`) + indeterminate `animate-pulse` bar.
  Removed `loadingProgress` state, `completionRef`, the ramp/completion
  timeouts and the 350ms post-fill delay (no bar to fill anymore).

**Tier 3 — nice-to-haves:**
- `ConnectionBanner` in `App.tsx` — fixed-position destructive banner driven
  by `navigator.onLine` + `online`/`offline` events. Cheap pre-click
  feedback for hard offline; the post-fetch network toast still catches
  captive-portal cases.
- `StatusDot` (green/gray/red) inserted into every comparison row's "Tienda"
  cell, plus a count summary above the table (`X consultadas · Y con
  resultados · Z sin respuesta · W sin coincidencias`, errored/empty parts
  hidden when zero).

---

### ✅ Item 13 — Rate limiting awareness

**Status:** Done.

**Backend:**
- `api.py` 429 handler now sets `Retry-After: 60` (both rate-limited
  endpoints use 1-minute windows; 60s is the safe upper bound) and includes
  `retry_after` in the JSON body for proxies that strip custom headers.

**Frontend:**
- `ApiError` carries optional `retryAfterSeconds`; `apiFetch` parses the
  header on 429 with the JSON body as fallback.
- `Landing.tsx` tracks a cooldown deadline in state — when 429 fires, sets
  `cooldownEndsAt = now + retryAfterSeconds * 1000`, ticks `cooldownSec`
  every 250 ms, disables the submit button while active, and renders
  `Esperá Ns` on the button label. `handleSubmit` early-returns while the
  cooldown is non-zero.

The submit-on-explicit-action requirement was already covered in Tier 2 of
Item 12 via the `submitToken > 0` gate and the React Query `enabled` flag.

---

## Open Questions

| # | Question | Status | Blocks |
|---|---|---|---|
| 1 | Supabase credentials | ✅ Resolved — project set up, keys in env files | Item 2 |
| 2 | Product selection UX | ✅ Resolved — hybrid approach: selective mode (user picks per store) + auto mode (cheapest available). Landing UX already built; needs API wiring. | Items 4, 5, 6 |
| 3 | Price history: track in backend / hide chart / keep as placeholder? | ❓ Open | Item 10 |
| 4 | Payment analysis button: wire to `detail=true`? | Recommended yes — no blocker once Items 3+6 done | Item 9 |

---

## Implementation Order

```
✅  1  Env config + Vite proxy + gitignores
✅  2  Auth bridge (Supabase client, AuthContext, ProtectedRoute, SignIn wiring)
✅  3  Typed API client (api.ts)
✅  4  Landing + ProductIntelligence wired to real API; {store,url}[] URL contract
✅  5  Data model transformation (transforms.ts)
✅  6  React Query hooks (useSearch — useStores skipped as no consumer)
✅  7  Store metadata constants (stores.ts)
✅ 11  Postal code support (CABA default or user-provided CP)
✅  8  Image handling (raw CDN URLs + frontend priority+fallback chain)
✅ 12  Loading/error states
✅ 13  Rate limiting handling
✅  9  Payment analysis button wiring
─── optional / phased ───
❓ 10  Price history tracking (decision pending — chart currently rendered
       inline in ProductIntelligence with blur+grayscale to indicate "unavailable")
```

Items 1–8 and 11 are complete. Items 9, 12, 13 remain; item 10 is awaiting the Q3 decision.

---

## Nice-to-haves — Non-critical but still important

These items surfaced during the Codex adversarial-review pass on Item 11's
postal-code wiring. None are blocking launch and none represent concrete bugs,
but each is real design debt that will bite later if left indefinitely. Listed
in rough priority order.

### 🔲 N1 — Unified typed Location model across frontend/backend

**Why:** The UI models location as two values (`fromCABA` boolean + optional
`postalCode` string), the URL/route encodes it as `caba=1` OR `postal_code=…`,
and `searchProducts()` in `api.ts` only takes a raw `postalCode?: string`.
There are three representations of one concept. A caller that sends
`postal_code=1425` (CABA's default) triggers different backend behavior (cache
bypass, non-CABA lock-key bucket) than omitting the param, even though the
user intent is identical.

**Shape to add:** one typed `Location` discriminated union used in route
state, URL serialization, the API client, and the backend request schema:

```ts
type Location =
  | { mode: "caba" }
  | { mode: "postal"; postalCode: string }  // validated before construction
```

Plus a shared `serializeLocation()` / `parseLocation()` pair so `Landing.tsx`
doesn't duplicate the `fromCABA ? set("caba") : set("postal_code")` branch in
`handleSubmit` and `handleCompareSelection`, and so `ProductIntelligence.tsx`
parses it through the same helper instead of reading two raw URL params.

**Scope:** ~1 new file (`frontend/src/lib/location.ts`), 3 call sites updated.

### 🔲 N2 — Per-store `postal_code_applied` in `StoreStatusResponse`

**Why:** Today's `StoreStatusResponse` doesn't tell the client whether a
given store actually honored the requested postal code. Magento stores and
Megatone silently ignore the param (they don't run shipping simulation), and
VTEX stores with `_free_shipping_override` also ignore it. When the user sets
a non-CABA postal and sees a mixed result set, some stores ran a real postal-
specific simulation and some returned their store-wide constant — the UI has
no way to distinguish. For a cross-store comparison tool this is honesty
debt.

**Shape to add:** extend `StoreStatusResponse` with:

```py
postal_code_applied: Optional[str]   # echoes the postal actually used, or None
                                     # if the store doesn't honor postal codes
```

Frontend renders a subtle marker in stores that returned `None` ("Envío no
depende del CP en este local" or similar).

**Scope:** model change + each platform's search path sets the field; frontend
UI tweak in the comparison table.

### 🔲 N3 — VTEX postal-aware shipping cache or hard cap

**Why:** `_check_free_shipping` in `platforms/vtex.py` fans out one checkout-
simulation POST per available product, unbounded. Fravega has
`_MAX_SHIPPING_CHECKS = 100` as a safety valve; VTEX doesn't. Since custom
postal codes bypass the DB cache entirely, every non-default-postal query for
a broad term (e.g. "heladera") will reissue the full simulation burst against
every VTEX store. A user repeatedly toggling a postal code could create a
request storm.

**Mitigation options:**
- **Minimum:** add `_MAX_SHIPPING_CHECKS` to `platforms/vtex.py` mirroring
  Fravega's threshold. Above the cap, skip simulation and return
  `free_shipping=False` for all products.
- **Better:** in-memory TTL cache keyed by `(sku_id, seller_id, postal_code)`
  with a 24 h expiry. Fravega has a disabled version already
  (`_SHIPPING_CACHE_ENABLED`); port the same pattern to VTEX and flip both on
  together for v1 launch.

**Scope:** ~30 lines in `platforms/vtex.py`. Non-urgent until we see real
traffic volume on non-default postals.

### 🔲 N4 — DRY helper for URL-param construction in Landing

**Why:** `Landing.tsx` currently writes the `fromCABA ? caba=1 : postal_code`
branch twice — once in `handleCompareSelection` (~line 149) and once in
`handleSubmit`'s `completionRef.current` setTimeout (~line 224). Both paths
also re-build the base `URLSearchParams({ q })` from scratch. Subsumed by N1
if that lands (the shared `serializeLocation()` would handle it), but worth
flagging as a standalone minor cleanup if N1 gets deferred further.

**Scope:** single helper in `Landing.tsx` or `lib/location.ts` (if N1 lands).

---

## Files This Folder Will Contain

| File | Final location | Status |
|---|---|---|
| `bridging_to_do.md` | (stays here) | ✅ This document |
| `api.ts` | `frontend/src/lib/api.ts` | ✅ Created in place |
| `transforms.ts` | `frontend/src/lib/transforms.ts` | ✅ Created in place |
| `stores.ts` | `frontend/src/lib/stores.ts` | ✅ Created in place |
| `supabase.ts` | `frontend/src/lib/supabase.ts` | ✅ Created in place |
| `AuthContext.tsx` | `frontend/src/contexts/AuthContext.tsx` | ✅ Created in place |
| `ProtectedRoute.tsx` | `frontend/src/components/ProtectedRoute.tsx` | ✅ Created in place |
| `useSearch.ts` | `frontend/src/hooks/useSearch.ts` | ✅ Created in place |
| `useStores.ts` | `frontend/src/hooks/useStores.ts` | ⏭️ Skipped — no consumer today |
| `usePriceHistory.ts` | `frontend/src/hooks/usePriceHistory.ts` | ❓ Pending Q3 decision |
