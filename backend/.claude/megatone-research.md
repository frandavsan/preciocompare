# Megatone (www.megatone.net) — Research & Onboarding Plan

> **Status:** Ready to implement — all critical unknowns resolved via DevTools inspection (2026-03-27)
> **Date:** 2026-03-26 | **Updated:** 2026-03-27

---

## 1. Platform Overview

| Property | Value |
|---|---|
| Store | Megatone |
| URL | https://www.megatone.net |
| Backend | ASP.NET WebForms (custom — NOT VTEX, Magento, or Shopify) |
| Frontend | Vue.js v2 + jQuery 3.5.1 |
| **Search engine** | **Doofinder** (third-party search-as-a-service) |
| CDN | Cloudflare + cdn.bzagroup.com (BZA Group) |
| SSL | DigiCert / Thawte |
| Server location | Argentina (Telefonica Argentina) |
| Bot protection | reCAPTCHA v3 on some pages; no Cloudflare bot challenge observed on search/listing pages |
| Language | Spanish (es-AR) |

This is a **new platform type** not yet supported by any existing platform module. Requires a new `platforms/megatone.py`.

**Key discovery:** Megatone uses **Doofinder** as its search engine. All product search goes through a Doofinder JSON API — no HTML scraping needed. The `GlobalListado` JS variable on listing pages is secondary and no longer the primary data source.

---

## 2. URL Structure

### Search results page (browser-facing)
```
https://www.megatone.net/resultados-busqueda/?q={query}&p={page}
```
Example:
```
https://www.megatone.net/resultados-busqueda/?q=samsung+s26&p=1
```

### Category listings
```
/listado/{top-category}/{sub-category}/{leaf-category}/
```
Examples:
```
/listado/tecnologia/celulares/smartphones-celulares/
/listado/tecnologia/videojuegos/
/listado/electrodomesticos/heladeras-freezers/heladeras-con-freezer/
```

### Product pages
```
/producto/{product-slug}_{SKU}/
```
Examples:
```
/producto/tv-qled-smart-50p-4k-q7fa-samsung_TEL5062SSG/
/producto/celular-galaxy-s26-ultra-sms948b-256gb-negro_KIT2653SSG/
```

### Category query parameters (faceted filters on listing pages)
| Parameter | Meaning | Example |
|---|---|---|
| `m_{brand}={id}` | Brand filter | `?m_samsung=1810` |
| `c_cuotasi={n}` | Installment count filter | `?c_cuotasi=15` |
| `e_={id}` | Free shipping filter | `?e_=1088` |
| `i_={n}` | International product filter | `?i_=1` |
| `pag={n}` | Pagination (page number) | `?pag=2` |

---

## 3. Search API — Doofinder (PRIMARY DATA SOURCE)

### Endpoint (CONFIRMED from DevTools, 2026-03-27)

```
https://us1-search.doofinder.com/6/7d78864dfd68192d967ce98f7af00970/_search
```

URL structure: `/{api_version}/{hashid}/_search` — not the `?hashid=` query-param style (that was v5; this is v6).

- Cluster: `us1-search.doofinder.com` (US cluster, not eu1)
- API version: `6`
- Hash ID: `7d78864dfd68192d967ce98f7af00970`

Full observed request (with facets):
```
https://us1-search.doofinder.com/6/7d78864dfd68192d967ce98f7af00970/_search?page=1&rpp=100&query=samsung+s26&facets[0][field]=category_name&facets[1][field]=brand&facets[2][field]=max_installments&facets[4][field]=amba_shipping&facets[5][field]=free_shipping&facets[6][field]=productointernacional
```

The `facets[]` parameters request aggregation buckets for filters (brand, category, etc.). They are optional for our use — omitting them returns the same `results[]` array without the `facets` section.

### Request parameters
| Parameter | Value | Notes |
|---|---|---|
| `query` | URL-encoded search term | e.g. `samsung+s26` |
| `rpp` | `100` | Results per page |
| `page` | `1`, `2`, ... | Pagination |

### Response structure
```json
{
    "count": 36,
    "total": 36,
    "results": [ /* array of product objects */ ],
    "facets": [ /* aggregations for filters */ ]
}
```

- `total` = total matching products (use for pagination: if `total > rpp`, fetch more pages)
- `facets` = filter counts for `category_name`, `brand`, `free_shipping`, `productointernacional`, `amba_shipping`, `max_installments`

---

## 4. Product Object Structure (Doofinder API)

Each item in `results[]` has the following fields (confirmed from live response):

```json
{
    "id": "KIT2654SSG",
    "gtin": "KIT2654SSG",
    "title": "Celular Galaxy S26 SM-S942B - 512GB, 12GB RAM, Cámara 50MP, 4300 mAh, Negro",
    "link": "https://www.megatone.net/producto/samsung-ung-s26-sm-s942b-512gb-ng_KIT2654SSG/",
    "image_link": "https://www.megatone.net/Images//Articulos/zoom/209/KIT2654SSG.jpg",
    "brand": "SAMSUNG",
    "description": "...",
    "categories": ["CELULARES LIBERADOS"],
    "category_name": "Smartphones y Celulares",
    "mpn": "CELULARES LIBERADOS",

    "price": 2699999.0,
    "sale_price": 2699999.0,
    "best_price": 2699999.0,
    "notax_price": "2231404.13",
    "calculated_discount": null,

    "availability": "in Stock",
    "free_shipping": "false",
    "amba_shipping": "false",
    "productointernacional": "false",

    "seller_name": "Megatone",

    "highlight_installments": "9 x $300000 Sin Interés",
    "valorcuotaweb": "300000",
    "max_installments": "9",

    "quantity_sold": "0",
    "score": "345",
    "dfscore": 538.3083,
    "dfid": "7d78864dfd68192d967ce98f7af00970@product@...",
    "df_grouping_id": "product@KIT2654SSG",
    "df_manual_boost": "20.0",
    "df_auto_boost": "1.92...",
    "group_leader": false,
    "color": null,
    "size": null,
    "tags": null,

    "plaquetas": {
        "p_bl": null, "p_br": null, "p_tl": null,
        "p_tr": { "element": "https://...plaquetaspromos/2180producto.png" }
    }
}
```

---

## 5. Field Mapping to ProductResult

| ProductResult field | Source field | Notes |
|---|---|---|
| `name` | `title` | Clean product name with proper accents |
| `sku` | `id` (= `gtin`) | e.g. `KIT2654SSG` |
| `price` | `sale_price` | **Use `sale_price`, not `price`** — `price` is the inflated list price; `sale_price` is what the customer pays |
| `currency` | Hardcoded `"ARS"` | All prices are ARS |
| `url` | `link` | Already a full URL — no prefix needed |
| `installments` | `highlight_installments` + `valorcuotaweb` | See installment section below |
| `available` | `availability == "in Stock"` | String comparison |
| `free_shipping` | `free_shipping == "true"` | String boolean |
| `international` | `productointernacional == "true"` | String boolean |

### Price notes
- `price` = original/list price (may be inflated for marketplace products)
- `sale_price` = actual selling price (always correct)
- `best_price` = same as `sale_price` in all observed cases
- `notax_price` = price excluding national tax (for display, not needed)
- `calculated_discount` = discount % relative to `price` (present only when discounted)

---

## 6. Installments

### How it works
The `highlight_installments` field contains a text label for the best installment option shown on the listing page. Two formats observed:

| Format | Example | Meaning |
|---|---|---|
| `"N x $AMOUNT Sin Interés"` | `"9 x $300000 Sin Interés"` | Interest-free — **include this** |
| `"N x $AMOUNT Rebajas"` | `"6 x $676473 Rebajas"` | With interest/rebate — **skip this** |

### Parsing rule
- Only produce an `Installment` entry when `highlight_installments` contains `"Sin Inter"` (handles encoding issues with the accent)
- Count = first number in the string (regex `(\d+)\s*x`)
- Amount = `int(valorcuotaweb)` if present, else parse from the string
- No card names available from this API — `cards=[]`
- `max_installments` field gives the max count as a string (or `null` for marketplace products without sin interés)

### Marketplace products
- Often have `max_installments: null` and show `"Rebajas"` in `highlight_installments`
- These are sold by third-party sellers (AFFARI, Multipoint, MAXIHOME, Al Click, Dinatech, etc.)
- Their `seller_name != "Megatone"`

---

## 7. Free Shipping

**RESOLVED.** The `free_shipping` field is a direct string boolean on every product object.

```json
"free_shipping": "true"   // has free shipping
"free_shipping": "false"  // does not
```

There is also an `amba_shipping` field (AMBA = Área Metropolitana de Buenos Aires) which is separate — it indicates same-day/next-day delivery to Buenos Aires metro area, not general free shipping. Use `free_shipping` for the `ProductResult.free_shipping` field.

---

## 8. International Products

**RESOLVED.** The `productointernacional` field is a direct string boolean.

```json
"productointernacional": "true"   // international purchase
"productointernacional": "false"  // local product
```

In the observed "samsung s26" response, all 36 results had `"false"`. The field exists and is always present.

---

## 9. Marketplace / Sellers

- `seller_name` = `"Megatone"` → sold directly by Megatone
- `seller_name` = anything else → marketplace third-party seller (AFFARI, Multipoint, MAXIHOME, Al Click, Dinatech, etc.)
- Marketplace products typically have inflated `price` vs lower `sale_price`, `calculated_discount` set, and often `max_installments: null`

---

## 10. Pagination

- Response `total` field = total matching products
- `rpp=100` per page
- If `total > 100`: fetch pages 2, 3, ... in parallel
- Cap at 10 pages (1,000 products) max
- Formula: `total_pages = ceil(total / rpp)`, capped at 10

---

## 11. GlobalListado (listing page JS variable — secondary, no longer primary)

Product data is also embedded in listing page HTML as a JavaScript variable. This was the originally planned data source before the Doofinder API was discovered.

```javascript
var GlobalListado = {
    Productos: [
        {
            SKU: "HEL1400TFK",
            Nombre: "Heladera Con Freezer ...",
            URL: "/producto/slug_SKU/",
            Precios: { WEB: { Lista: 582999, Promocional: 439999 } },
            Stock: { Sucursal: 200, COL: 192 },
            Leyendas: [{ Clave: "12", Texto: "36667", TextoSecundario: " Sin Interés" }],
            Extras: { IdSellerMKT: 0, Seller: { Nombre: "MEGATONE" } }
        }
    ]
}
```

**This is no longer needed for implementation** — the Doofinder API provides cleaner, more complete data directly as JSON. `GlobalListado` may be useful as a fallback if the Doofinder endpoint becomes unavailable or requires authentication.

---

## 12. Product Page Schema (JSON-LD)

Product pages include schema.org structured data — not needed for search, but useful for reference:

```json
{
    "@type": "Product",
    "name": "Celular Galaxy S26 Ultra SM-S948B - 256GB, 12GB RAM, ...",
    "sku": "KIT2653SSG",
    "offers": {
        "priceCurrency": "ARS",
        "price": "3399999.00",
        "availability": "https://schema.org/InStock"
    }
}
```

---

## 13. Implementation Plan

### Phase 1: ~~Confirm Doofinder endpoint URL~~ — DONE
- Confirmed: `https://us1-search.doofinder.com/6/7d78864dfd68192d967ce98f7af00970/_search`
- API version 6, US cluster, path-based hashid (not query-param style)

### Phase 2: Create platform module
- New file: `platforms/megatone.py`
- Class: `MegatoneAdapter(StoreAdapter)`
- HTTP client: `httpx.AsyncClient` (Doofinder endpoint, no Cloudflare protection expected)
- Search: `GET {doofinder_endpoint}?hashid=...&query={query}&rpp=100&page=1`
- Pagination: if `total > 100`, fetch remaining pages in parallel via `asyncio.gather`
- Product parsing: map Doofinder `results[]` fields to `ProductResult` per section 5 above
- Installments: parse `highlight_installments` — only "Sin Interés" entries; amount from `valorcuotaweb`

### Phase 3: Create store adapter
- New file: `adapters/megatone.py`
- Minimal: just `name`, `base_url`, and Doofinder `hashid`

### Phase 4: Register and test
- Add to `ADAPTERS` list in `adapters/__init__.py`
- Test with `"samsung s26"`, `"heladera samsung"`, `"ps5"`
- Validate prices, installments, free_shipping against website

### Key architectural decisions
| Decision | Rationale |
|---|---|
| New platform module (not reusing VTEX/Magento) | Completely different tech stack and API format |
| Use Doofinder API (not `GlobalListado` HTML parse) | Clean JSON, all fields present, no regex fragility |
| `httpx` as HTTP client | No Cloudflare bot protection on Doofinder endpoint |
| `sale_price` not `price` | `price` is inflated list price; `sale_price` is actual |
| Skip non-"Sin Interés" installments | "Rebajas" entries are with interest — not what we display |

---

## 14. Risks and Remaining Unknowns

| Risk / Unknown | Impact | Mitigation |
|---|---|---|
| ~~Doofinder endpoint URL not yet confirmed~~ | RESOLVED — `us1-search.doofinder.com/6/{hashid}/_search` | — |
| Doofinder may require auth headers (e.g. `Authorization` or `Origin`) | Requests blocked | Test with bare `GET`; add headers only if needed |
| Installment card names not available | No card-level breakdown | Acceptable — same as Fravega fast mode |
| Installment detail endpoint (VER CUOTAS Y FORMAS DE PAGO) unknown | No detail mode | Low priority — fast mode is sufficient for v1 |
| `httpx` may be blocked on Doofinder CDN | All searches fail | Switch to `curl_cffi` if needed |
| Large result sets (1,000+ products for broad queries) | Slow fetching | Cap at 10 pages; `matches_query()` filters irrelevant results |