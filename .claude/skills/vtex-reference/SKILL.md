---
name: vtex-reference
description: VTEX Intelligent Search API reference for ElectrodomesticsBot. Use when working on VTEX adapters, debugging VTEX API responses, or adding a new VTEX store.
---

## VTEX API Patterns (ElectrodomesticsBot)

### Search Endpoint
`{base_url}/_v/api/intelligent-search/product_search/?query={q}&count=50&page={N}`
- Paginated, capped at 10 pages (500 results max)
- Pages fetched in parallel via ThreadPoolExecutor(max_workers=5)

### Shipping Simulation
`{base_url}/api/checkout/pub/orderForms/simulation` (POST)
- Payload: items[{id, quantity, seller}], postalCode, country="ARG"
- Free shipping: any slas[] with deliveryChannel=="delivery" and price==0
- Capped at max_workers=10, skipped for unavailable products

### Multi-Seller Resolution
ALWAYS use `_get_real_seller()`. International/marketplace products have:
- A dummy seller "1" with Price=0 and AvailableQuantity=0
- The real seller with actual data
NEVER index sellers[0] directly.

### International Detection
- categories containing `/Compra Internacional/`
- productClusters named "Compra Internacional"

### Price and Installments
- Read from `commertialOffer` in search response (no extra page fetch)
- Interest-free: InterestRate == 0 and NumberOfInstallments > 1
- Group by (count, amount), collect PaymentSystemName as cards

### Availability
- AvailableQuantity > 0 on any seller across all items