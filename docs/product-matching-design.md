# Product Matching Design Notes

## The Problem

Different stores name the same physical product differently. After fetching results from all stores,
we need to group them by actual product identity so the user can compare prices/installments/shipping
for the same product across stores — rather than seeing a flat list of 30+ differently-named entries.

---

## Core Insight: Two Types of Products

Research across Fravega, Megatone, OnCity, and Cetrogar (800+ product names sampled) confirmed two naming patterns:

### Type 1 — Products with unique model codes (majority)
A single alphanumeric code that uniquely identifies the product within its brand.
The rest of the name is noise.

Examples from real data:
```
Fravega:  Smart TV Philips 58" LED 4K UHD 58PUD7310/77 Google TV WiFi
Megatone: Smart TV LED UN55U8000FGCZB - 55" 4K Crystal Processor, Tizen OS
Cetrogar: Heladera con freezer RT32 Samsung 318 lt Inverter plata      → RT32
OnCity:   Lavarropas Automatico Inverter Drean Lcfdr0814sb 8 Blanco    → LCFDR0814SB
Fravega:  Heladera Gafa No Frost Inverter HGNF251P 262Lts Plata        → HGNF251P
Cetrogar: Cocina Drean Gas Natural 56cm CD5602AI0 Inox                  → CD5602AI0
```

For these, `brand + model_code` is a complete and unambiguous identity key. No spec parsing needed.

### Type 2 — Products with generic model names (minority)
The "model" is a product line name, not a unique code. Variants require specs to differentiate.

Examples:
```
Drean Concept (washer line) → differentiated by: capacity (5kg/6.5kg/8kg), RPM, color
Samsung Galaxy S26+ (phone) → differentiated by: storage (256/512GB), color
Motorola G15 (phone)        → differentiated by: storage (128/256GB), color
BGH BS26WCDW (AC)           → model code present, so actually Type 1
```

These are genuinely less common in the data. Most appliances have unambiguous model codes.

---

## Proposed Algorithm

### Step 0 — Instant Match Bypass
If the user's query is specific enough that every store returns 0 or 1 result,
skip grouping entirely — go straight to comparison.
```
all(len(products) <= 1 for products in results.values()) → skip grouping
```
This handles model-code searches like "58PUD7310" or "SM-S936B".

### Step 1 — Normalize
- Lowercase, strip accents (already done by `_normalize()` in core.py)
- Collapse unit spellings: `"12 Gb"` → `"12gb"`, `"5 Kg"` → `"5kg"`, `"362 Lts"` → `"362l"`,
  `"512/12GB"` → extract both `"512gb"` and `"12gb"` separately
- Strip /suffix on model codes: `"58PUD7310/77"` → `"58PUD7310"` (trailing slash + 1-2 chars)
  NOTE: This is only needed for matching keys, not for display.

### Step 2 — Brand Gate
Match brand against a known brands set (~60-80 entries). Position-independent scan of all tokens.
Products with different brands never match (fast O(n) filter before any set comparison).

```python
_BRANDS = {
    "samsung", "lg", "philips", "motorola", "apple", "lenovo", "hp", "asus",
    "whirlpool", "drean", "philco", "electrolux", "gafa", "bgh", "tcl",
    "hisense", "noblex", "rca", "carrier", "sansei", "siam", "midea",
    "candy", "codini", "longvie", "admiral", "enova", "eslabón",
    "florencia", "escorial", "atma", "kanji", "yelmo", "gadnic",
    "xiaomi", "hitachi", "toshiba", "aoc", "bgh", "exo", "zenit",
    "acer", "sony", "huawei", "realme", "oneplus",
    # appliance-specific
    "smartlife", "telefunken", "admiral", "midea", "columbia",
}
```

### Step 3 — Extract Keys via Spanish Dictionary Filter
Tokenize the normalized name. Keep only tokens that are NOT in a Spanish dictionary.
What survives = model codes, brand names, spec values, English feature words.
What gets filtered = Spanish nouns/adjectives/verbs = category words, color names, feature descriptors.

```
"Celular Motorola Moto G15 4G 4 Gb 128 Gb Nfc Dual Sim Azul"
  tokens:  celular, motorola, moto, g15, 4g, 4gb, 128gb, nfc, dual, sim, azul
  spanish: celular✓  motorola✗  moto✓  g15✗  4g✗  4gb✗  128gb✗  nfc✗  dual✓  sim✓  azul✓
  keys:    {motorola, g15, 4gb, 128gb, nfc}
```

Why dictionary over stop-list: a stop-list is a blacklist that requires manual maintenance for every
new noise word. A dictionary automatically handles any Spanish category/color/feature word without
any code changes. A reduced Spanish dictionary (10-15K words, ~1MB as a Python set) has O(1)
lookup and negligible memory footprint.

Implementation: use the `hunspell` es_AR word list, or `pyspellchecker` with Spanish corpus.

### Step 4 — Match by Subset Relationship
Two products A and B are the same if the keys of the shorter set are all contained in the longer set
(or they're equal). This tolerates one store including more info than another.

```
A keys: {motorola, g15, 4gb, 128gb}          (Cetrogar — terse)
B keys: {motorola, g15, 4gb, 128gb, nfc}     (OnCity — verbose)
A ⊆ B → MATCH
```

```
A keys: {drean, concept, 5.05, v1, 5kg}      (Cetrogar)
B keys: {drean, concept, 8.12, eco, 8kg}     (OnCity)
Neither ⊆ the other → NO MATCH (different variants — correct)
```

```
A keys: {philips, 58pud7310, 4k}             (Fravega, after /77 strip)
B keys: {philips, 58pud7310, 4k, 58}         (Megatone)
A ⊆ B → MATCH
```

### Step 5 — Ambiguity Handling
If a product matches multiple groups (its key set is a subset of two different groups),
it is genuinely ambiguous. Options:
- Assign to the group with the highest overlap count (most keys in common)
- If tied, leave it ungrouped (display it separately rather than force-merge)

The "ungrouped" fallback is safer: showing a product twice is less bad than merging two different ones.

---

## Observations from Real Data

### What stays consistent across all stores
1. **Brand names** — always present, always recognizable, always the same string
2. **Model codes** — always present for Type 1 products; usually match or have trivial variation (/77 suffix)
3. **Storage/capacity** — always present as `NGB`, `NKG`, `NL`, `NLTS`
4. **RPM** — always present for washers as `NRPM` or `N RPM`

### What varies between stores
1. **Category prefix** — "Celular" vs "Smartphone" vs absent
2. **Product line name** — "Moto G15" vs "Galaxy G15" vs just "G15" (some stores include "Moto", others don't)
3. **Color** — Spanish ("Azul", "Gris", "Violeta") vs English ("Blue", "Grey", "Violet")
   → Dictionary handles Spanish colors automatically; English colors survive as keys
   → This is actually fine: if one store uses English color names, they differentiate variants
     correctly. If another omits color, the subset match still works.
4. **Feature noise** — NFC, Dual SIM, 5G, Inverter, No Frost — varies per store
5. **Spec format** — "4 Gb 128 Gb" vs "4GB/128GB" vs "128GB 4GB RAM"
   → Unit normalization in Step 1 handles this

### Cross-store same-product example (confirmed in data)
```
Fravega:  "Celular Motorola G15 4GB 128GB Gravity Grey"
          keys: {motorola, g15, 4gb, 128gb, gravity}  (grey→Spanish? No, grey≠gris, keeps)
OnCity:   "Celular Motorola Moto G15 4G 4 Gb 128 Gb Nfc Gris"
          keys: {motorola, g15, 4gb, 128gb, nfc}  (gris filtered by dictionary)
Megatone: "Celular Galaxy S26 SM-S942B - 512GB, 12GB RAM, Negro"  (different product)

Fravega keys ⊆ OnCity keys? {motorola, g15, 4gb, 128gb, gravity} vs {motorola, g15, 4gb, 128gb, nfc}
→ "gravity" not in OnCity keys → NOT a subset → no direct match
→ BUT: "gravity" is an English word (color modifier), would it survive Spanish dictionary? Yes.
→ Solution: also try intersection-based threshold: if |A∩B| / min(|A|,|B|) ≥ 0.8 → match
```

This reveals a **known edge case**: English color names like "Gravity Grey", "Sunrise Orange", "Midnight Blue"
survive the Spanish dictionary filter and become differentiating keys. Stores that use Spanish colors
("Gris", "Naranja", "Negro") have those filtered out. This asymmetry means the same product can have
different key sets across stores if colors are expressed in different languages.

**Mitigation options:**
1. Add an English color stop-list: `{"grey", "gray", "blue", "green", "black", "white", "red", "violet", ...}`
   augmenting the Spanish dictionary filter
2. Accept the asymmetry — if a product can't be matched due to color language mismatch, it appears
   as a separate entry, which is acceptable behavior

### Washer/appliance model code vs generic name (confirmed in data)
```
Fravega:  "Lavarropas Automatico Inverter Drean 6Kg 1000 RPM LCFDR0610LB0"  → code: LCFDR0610LB0
Cetrogar: "Lavarropas Drean LCFDR0814SG IA 8kg 1400RPM gris"               → code: LCFDR0814SG
OnCity:   "Lavarropas Automatico Drean Concept Neo 6.5 Blanco"              → NO code (Type 2)
```

Cetrogar often includes the model code explicitly. OnCity sometimes doesn't.
→ The algorithm should handle this gracefully: LCFDR0610LB0 ≠ LCFDR0814SG (different products, correct),
  and "Concept Neo 6.5" keys {drean, concept, neo, 6.5kg} can still match via subset when another
  store includes the code alongside the line name.

### TV naming patterns
```
Fravega:  "Smart TV Philips 58" LED 4K UHD 58PUD7310/77"  → code: 58PUD7310
Megatone: "Smart TV QLED QN55Q7FAAGCZB"                   → code: QN55Q7FAAGCZB
Cetrogar: "Tv Led 55" Samsung QN55Q7FAAGCZB Qled"          → code: QN55Q7FAAGCZB

Megatone ⊆ Cetrogar? {samsung, qn55q7faagczb} ⊆ {samsung, qn55q7faagczb, 55} → YES → MATCH ✓
```
TV model codes are long and unique — this is the best-case scenario for matching.

### Notebook naming (more complex)
```
Fravega:  "Notebook Lenovo 15,6" AMD Ryzen 3 8GB 256GB SSD 82XQ00CTAR"  → code: 82XQ00CTAR
Fravega:  "Notebook Lenovo Ideapad Slim 3 15,3" Intel Core i5 8GB 512GB SSD 83K100T2AR"
Megatone: (notebook results include HP, Exo, Lenovo — similar patterns)
```
Notebooks often include the full part number. This makes them reliable Type 1 products.

---

## Edge Cases to Watch

1. **Color language mismatch** — English vs Spanish colors ("Blue" vs "Azul") may prevent
   matching if both survive/are filtered differently. Needs an English color supplement to the stop list.

2. **Reacondicionados** — Megatone includes "Reacondicionado" products (refurbished). These should
   likely be treated as separate product groups from new units.

3. **Accessories match to main product** — A "Cargador Samsung" (charger) has "samsung" as a key.
   The brand gate alone doesn't prevent it matching a phone. Need to ensure the model code or spec
   keys prevent this — charger names typically have very few keys after filtering.

4. **Test/garbage entries** — Megatone had one "Test title" placeholder in AC results. These
   would have very few keys and are unlikely to match anything real.

5. **OnCity breadth** — OnCity returns 473 results for "samsung" (a marketplace, not a focused
   retailer). The instant-match bypass is important for focused queries; for broad queries, the
   keying system needs to handle many more products.

---

## Architecture Plan

### New module: `electrodomestics_bot/matching.py`

Two public functions:

```python
@dataclass
class ProductGroup:
    canonical_name: str               # cleanest/most complete name from the group
    fingerprint: frozenset[str]       # key set that defines this group
    products: dict[str, ProductResult]  # store_name → best matching product

def extract_keys(name: str) -> frozenset[str]:
    """Normalize name, remove Spanish dictionary words and known noise, return key tokens."""

def group_results(
    all_results: dict[str, list[ProductResult]]
) -> tuple[list[ProductGroup], dict[str, list[ProductResult]]]:
    """
    Groups products across stores by identity fingerprint.
    Returns (groups, ungrouped) where ungrouped products couldn't be confidently matched.
    """
```

### CLI integration (in `__main__.py`)

After `print_results()` and "Show more?" prompt, add:
```
Found 3 distinct products. Which are you comparing?
  [1] Samsung Galaxy S26+ 512GB Violeta  (fravega, oncity, cetrogar)
  [2] Samsung Galaxy S26+ 256GB Violeta  (fravega, megatone)
  [3] Samsung Galaxy S26+ 512GB Negro    (fravega)
  [n] Skip comparison

Compare [1/2/3/n]:
```

If selected, show a compact comparison table:
```
Product: Samsung Galaxy S26+ 512GB Violeta
─────────────────────────────────────────────────────────────
Store      Price        Best installment           Shipping
fravega    $1,499,999   12x $124,999 (Visa)        FREE
oncity     $1,549,000   6x $258,166                FREE
cetrogar   $1,479,000   6x $246,500 (Visa, MC)     FREE
─────────────────────────────────────────────────────────────
Cheapest: castillo  $1,479,000
```

### Web UI consideration
The `group_results()` function is UI-agnostic — returns structured data.
The web frontend renders a comparison card. No CLI-specific logic leaks into matching.py.

---

## Open Questions

- Which Spanish dictionary to use? `pyspellchecker` (es) or a flat word list from hunspell es_AR?
  Performance: a Python `set` of 70K words does O(1) lookup. Load once at module import. Non-issue.

- Should `matching.py` know about the instant-match bypass, or should `__main__.py` decide?
  Cleaner to let `group_results()` return an empty groups list when all stores have ≤1 result,
  and the caller decides what to display.

- How to pick `canonical_name`? Heuristic: the name with the most keys (most informative).
  Fravega names tend to be cleaner than Megatone's dash-separated spec strings.
