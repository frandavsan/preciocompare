# Handoff — 2026-04-16

## What we're building
Automated pricing spreadsheet tool for El Gato (electronics store, Tucumán).
Fills columns E–H of an Excel template with competitor installment rates (Cetrogar=E, OnCity=F, Castillo=G, Montes=H).
Entry point: `python run_pricing.py` (or `python -m electrodomestics_bot pricing`).

---

## Status per column

### E — Cetrogar (Magento) ✅ DONE
Fetches from `/installments-plans/ajax/getplanbyproduct/productid/{pid}` JSON.
Falls back to HTML scraping. Working.

### F — OnCity (VTEX) ✅ MOSTLY DONE
Generic Visa/Mastercard/NaranjaX/MercadoPago plans work.
**Gap 2 (pending):** MercadoPago rows (3x/6x/9x/12x) — OnCity's VTEX API doesn't
emit MP plans in commertialOffer.Installments in a way that matches the template rows.
Proposed fix: synthesize MP sin-interés rows client-side with hardcoded tiers
(price/N amount, has_interest=False) when no MP plan is found.

### G — Castillo (VTEX) ✅ FIXED THIS SESSION
Root cause was that Castillo does NOT use per-product productClusters for bank
routing. Instead, every Visa card from any bank listed in
`/files/especific-cuotes-plp.json` is eligible for Visa plans store-wide.

Fix applied (commit 91b68ed):
- `pricing/platforms/vtex.py`: added `_CLUSTER_TO_ISSUER`, `_BANK_ELIGIBLE_CARDS`,
  `_extract_eligible_issuers()`, and `extra_issuers` param to `extract_all_plans()`.
  Now emits issuer-tagged PaymentPlan copies per eligible bank for
  Visa/Mastercard/Amex/Cabal plans.
- `pricing/service.py`: added `_STORE_EXTRA_ISSUERS` dict with Castillo's 15-bank set
  (macro, nacion, galicia, santander, bbva, hipotecario, credicoop, cordoba,
  ciudad, supervielle, patagonia, icbc, itau, hsbc, comafi). Passed to
  `extract_all_plans` when store.name == "castillo".
- `pricing/card_mapping.py`: added mercadopagopro / mercado pago pro aliases.

Rows now filling: VISA/MASTER MACRO 3/6/9/12 sin; VISA/MASTER NACION 3/6/9/12 sin
+ 15/18/20 con (and any other bank rows in _LABEL_MAP that Castillo's API returns).

### H — Montes Hermanos ❌ NOT STARTED
Platform not yet researched. URL: monteshermanos.com.ar
Need to: run store-researcher agent to identify platform + API endpoints.

---

## Key files

| File | Purpose |
|---|---|
| `electrodomestics_bot/pricing/service.py` | Orchestration: search → fetch plans → compute rates → Excel |
| `electrodomestics_bot/pricing/platforms/vtex.py` | VTEX plan extraction (all installments, bank expansion) |
| `electrodomestics_bot/pricing/platforms/magento.py` | Magento/Summa JSON endpoint + HTML fallback |
| `electrodomestics_bot/pricing/card_mapping.py` | Excel label → (card set, issuer) + plan matching |
| `electrodomestics_bot/pricing/excel_io.py` | Read template rows, write output .xlsx |
| `electrodomestics_bot/pricing/adapters/__init__.py` | PRICING_STORES list (name, column, platform, base_url) |

---

## Pending tasks (priority order)

1. **Gap 2 — OnCity MercadoPago rows**: synthesize 3x/6x/9x/12x sin-interés when
   no MP plan found in the VTEX response. Low effort.

2. **Montes Hermanos**: delegate to store-researcher agent, then write adapter.

3. **End-to-end smoke test**: run `python run_pricing.py` against a real product
   (e.g., "Samsung S26"), verify columns E/F/G fill correctly, check G has
   MACRO/NACION rows populated.

---

## Architecture note: VTEX bank expansion
`extract_all_plans(product, base_price, extra_issuers=None)` in vtex.py:
- Reads productClusters → set of canonical issuer keys (for OnCity and generic VTEX stores)
- Unions with `extra_issuers` if provided (for Castillo — store-wide bank set)
- For each Visa/MC/Amex/Cabal plan, emits one generic (issuer=None) + one per eligible bank
- `_STORE_EXTRA_ISSUERS` in service.py is the extension point for future VTEX stores
  that also don't use per-product productClusters

## Important discovery: Castillo bank routing
`/files/especific-cuotes-plp.json` is the store's BIN-to-bank routing table.
Structure: `{companies: [{code, name, banks: [{name, bin, icon, active}]}]}`
Visa has ~35 banks; Mastercard similar; Amex ~10; Naranja 1; Cabal 4.
This file is store-global — every product on Castillo accepts all listed banks.
No per-product filtering needed for the spreadsheet's sin-interés rows.
