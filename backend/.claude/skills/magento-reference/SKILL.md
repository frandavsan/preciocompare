---
name: magento-reference
description: Magento 2 + Summa Solutions scraping reference for ElectrodomesticsBot. Use when working on Magento adapters, debugging HTML parsing, or adding a new Magento store.
---

## Magento 2 + Summa Patterns (ElectrodomesticsBot)

### Search Endpoint
`{base_url}/catalogsearch/result/index/?q={q}&p={N}` (HTML)
- ~40 products/page, capped at 10 pages (~400 results)
- Pages fetched in parallel via ThreadPoolExecutor(max_workers=5)

### Product Data Extraction (from search HTML)
- Product container: `<li class="product-item">`
- Name/SKU: from `data-mage-init` attribute, `ajaxWishlist` JSON
- Price: `data-price-type="finalPrice"` -> `data-price-amount` attribute
- URL: `<a class="product-item-info">` href

### Installments (Search Page)
- Container: `div.installment-info` inside each `<li>`
- One option per product (best/featured), count + amount, NO card names
- Must contain "sin inter" text (interest-free check)
- Count extracted via regex from installment-count element
- Amount: strip $, replace . with nothing, replace , with .

### Installments (Product Page — detail mode)
- Container: `div.payment-info.pdp_logo`
- Full card names from logo image filenames via card_keywords map
- Requires fetching each product page individually (slow, parallelized)

### Card Logo Mapping
Ordered keyword matching on image src filenames:
naranja_x->NaranjaX, visa->Visa, master->Mastercard, cabal->Cabal, etc.

### Defaults
- free_shipping: always False (Magento stores in scope don't offer it)
- available: always True (catalogsearch only shows in-stock)