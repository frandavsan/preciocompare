"""
Post-processing layer: cross-store product identity matching and grouping.

Public API:
    extract_keys(name: str) -> frozenset[str]
    group_results(all_results: dict[str, list[ProductResult]]) -> list[ProductGroup]

Architecture note:
    This module is intentionally separate from the data-fetching layer
    (service.py, core.py, platforms/, adapters/). The data-fetching layer
    retrieves raw ProductResult objects per store. This module groups them
    by product identity so the presentation layer can render comparisons.
    Neither layer imports the other — both depend only on models.py.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from dataclasses import replace

from ..models import ProductResult, StoreSearchResult


@dataclass
class ProductGroup:
    canonical_name: str               # most informative name from the group
    fingerprint: frozenset[str]       # key set that defines this group
    products: dict[str, ProductResult] = field(default_factory=dict)  # store → product


# ---------------------------------------------------------------------------
# Stop-list: words that are inconsistent across stores and break subset matching
# ---------------------------------------------------------------------------

_STOP_WORDS: frozenset[str] = frozenset({
    # Prepositions / articles / connectors
    "con", "sin", "de", "del", "la", "el", "los", "las", "un", "una",
    "en", "para", "por", "al", "lo", "se", "su", "sus", "que", "mas",
    "y", "e", "o", "a",
    # Category names (vary across stores: "Celular" vs "Smartphone" vs absent)
    "heladera", "heladeras", "refrigerador", "refrigeradora", "congelador",
    "lavarropas", "lavarropa", "lavadora", "secadora", "lavasecadora",
    "televisor", "television", "tv", "celular", "celulares", "telefono", "movil",
    "notebook", "notebooks", "computadora", "computadoras",
    "tablet", "tablets", "aire", "acondicionado",
    "cocina", "cocinas", "horno", "hornos", "microondas",
    "lavavajillas", "calefon", "calefactor", "aspiradora",
    "licuadora", "batidora", "cafetera", "tostadora",
    "impresora", "proyector", "camara", "camaras",
    "auriculares", "auricular", "parlante", "parlantes", "smartwatch",
    "smartphone", "smartphones",
    # Feature descriptors (inconsistent: one store says it, another doesn't)
    "automatico", "automatica", "portatil",
    "no", "frost", "inverter",  # "No Frost" and "Inverter" vary per store
    "smart",       # "Smart TV" vs just TV model code
    "led", "qled", "oled", "uled", "amoled",  # panel types vary in naming
    "uhd", "fhd", "hd",  # resolution labels inconsistent
    # Spanish colors
    "negro", "negra", "negros", "negras",
    "blanco", "blanca", "blancos", "blancas",
    "gris", "grises", "azul", "azules",
    "rojo", "roja", "rojos", "rojas",
    "verde", "verdes", "amarillo", "amarilla", "naranja",
    "violeta", "violetas", "morado", "morada", "rosa", "rosas",
    "plateado", "plateada", "dorado", "dorada",
    "champagne", "titanio", "grafito", "celeste", "turquesa",
    # English colors (stores mix Spanish/English — remove both)
    "black", "white", "grey", "gray", "blue", "red", "green",
    "yellow", "orange", "violet", "purple", "pink", "gold", "silver",
    "brown", "teal", "navy", "midnight", "sunrise",
    "gravity", "phantom", "mystic", "prism", "haze", "lavender",
    "lilac", "olive", "mint", "cream", "ivory", "cosmic",
})

_BRANDS: frozenset[str] = frozenset({
    "samsung", "lg", "philips", "motorola", "apple", "lenovo", "hp", "asus",
    "whirlpool", "drean", "philco", "electrolux", "gafa", "bgh", "tcl",
    "hisense", "noblex", "rca", "carrier", "sansei", "siam", "midea",
    "candy", "codini", "longvie", "admiral", "enova", "eslabon",
    "florencia", "escorial", "atma", "kanji", "yelmo", "gadnic",
    "xiaomi", "hitachi", "toshiba", "aoc", "exo", "zenit",
    "acer", "sony", "huawei", "realme", "oneplus",
    "smartlife", "telefunken", "columbia",
})

# Unit normalization: collapse "12 Gb" → "12gb", "5 Kg" → "5kg", etc.
# Applied before tokenization so numeric specs match across stores.
_UNIT_SUBS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'(\d+)\s*(?:gb|giga)\b', re.IGNORECASE), r'\1gb'),
    (re.compile(r'(\d+)\s*(?:tb|tera)\b', re.IGNORECASE), r'\1tb'),
    (re.compile(r'(\d+)\s*(?:mb|mega)\b', re.IGNORECASE), r'\1mb'),
    (re.compile(r'(\d+)\s*(?:kg|kilos?)\b', re.IGNORECASE), r'\1kg'),
    (re.compile(r'(\d+)\s*(?:lts?|litros?)\b', re.IGNORECASE), r'\1l'),
    (re.compile(r'(\d+)\s*rpm\b', re.IGNORECASE), r'\1rpm'),
    # Strip /suffix from model codes: "58PUD7310/77" → "58PUD7310"
    # Only strip when the suffix is 1-4 characters (avoids touching real tokens)
    (re.compile(r'([A-Z0-9]{4,})/[A-Z0-9]{1,4}\b', re.IGNORECASE), r'\1'),
]


def _norm(s: str) -> str:
    """Lowercase and strip Unicode combining marks (accents)."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s.lower())
        if unicodedata.category(c) != "Mn"
    )


def extract_keys(name: str) -> frozenset[str]:
    """
    Normalize a product name and return the set of meaningful key tokens.

    Steps:
      1. Lowercase + accent-strip
      2. Unit normalization ("12 Gb" → "12gb")
      3. Tokenize on non-alphanumeric boundaries
      4. Drop stop-words and single-character tokens
    """
    s = _norm(name)
    for pattern, repl in _UNIT_SUBS:
        s = pattern.sub(repl, s)
    tokens = re.findall(r'[a-z0-9]+', s)
    return frozenset(t for t in tokens if t not in _STOP_WORDS and len(t) > 1)


def _detect_brand(keys: frozenset[str]) -> str | None:
    """Return the first brand token found in keys, or None."""
    return next((k for k in keys if k in _BRANDS), None)


def _keys_match(a: frozenset[str], b: frozenset[str]) -> bool:
    """
    Two key sets match if:
      - The shorter is a subset of the longer (strict identity), OR
      - ≥80% of the shorter set appears in the longer (handles English color
        name asymmetry: "cosmic" survives the filter on one store but not another)
    """
    if not a or not b:
        return False
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if shorter <= longer:
        return True
    return len(shorter & longer) / len(shorter) >= 0.80


def dedup_results(
    all_results: dict[str, StoreSearchResult],
) -> dict[str, StoreSearchResult]:
    """
    Within each store, collapse duplicate listings of the same product
    (marketplace sellers listing the same item) down to the cheapest one.

    Uses _keys_match so slightly different names for the same product
    (e.g. one seller adds "Google TV", another omits it) are still caught.
    Preserves the StoreSearchResult status metadata through deduplication.
    """
    out: dict[str, StoreSearchResult] = {}
    for store, ssr in all_results.items():
        products = ssr.products
        if len(products) <= 1:
            out[store] = ssr
            continue
        kept: list[tuple[ProductResult, frozenset[str]]] = []
        for prod in products:
            keys = extract_keys(prod.name)
            merged = False
            for idx, (existing, existing_keys) in enumerate(kept):
                if _keys_match(keys, existing_keys):
                    if (prod.price if prod.price is not None else float("inf")) < (existing.price if existing.price is not None else float("inf")):
                        kept[idx] = (prod, keys)
                    merged = True
                    break
            if not merged:
                kept.append((prod, keys))
        out[store] = replace(ssr, products=[p for p, _ in kept])
    return out


def group_results(all_results: dict[str, StoreSearchResult]) -> list[ProductGroup]:
    """
    Group products from different stores by product identity.

    Algorithm (greedy cross-store grouping):
      1. Flatten all (store, product, keys, brand) tuples.
      2. For each unassigned product, seed a new group.
      3. Scan remaining unassigned products from *other stores*:
         - Skip if brands detected and differ.
         - Match via _keys_match.
         - If the store already has a representative in this group,
           keep whichever has higher key overlap with the seed.
      4. Mark all absorbed products as assigned.
      5. Sort groups by store count (desc), then canonical name.

    Returns an empty list if no products were provided.
    Only groups with ≥2 stores are practically useful for comparison,
    but single-store groups are returned too — the caller decides what to show.
    """
    flat: list[tuple[str, ProductResult, frozenset[str], str | None]] = []
    for store, ssr in all_results.items():
        for prod in ssr.products:
            keys = extract_keys(prod.name)
            flat.append((store, prod, keys, _detect_brand(keys)))
    if not flat:
        return []

    # Precomputed key lookup by object identity — avoids re-running extract_keys
    # inside the O(n²) inner loop and the canonical-name max() call.
    _prod_keys: dict[int, frozenset[str]] = {id(prod): keys for _, prod, keys, _ in flat}

    assigned = [False] * len(flat)
    groups: list[ProductGroup] = []

    for i, (store_i, prod_i, keys_i, brand_i) in enumerate(flat):
        if assigned[i]:
            continue
        assigned[i] = True
        group_stores: dict[str, ProductResult] = {store_i: prod_i}

        for j, (store_j, prod_j, keys_j, brand_j) in enumerate(flat):
            if assigned[j] or store_j == store_i:
                continue
            if brand_i is not None and brand_j is not None and brand_i != brand_j:
                continue
            if not _keys_match(keys_i, keys_j):
                continue
            if store_j not in group_stores:
                group_stores[store_j] = prod_j
            else:
                # Store already represented — keep the product with higher overlap
                if len(keys_i & keys_j) > len(keys_i & _prod_keys[id(group_stores[store_j])]):
                    group_stores[store_j] = prod_j
            assigned[j] = True

        canonical = max(group_stores.values(), key=lambda p: len(_prod_keys[id(p)]))
        groups.append(ProductGroup(
            canonical_name=canonical.name,
            fingerprint=keys_i,
            products=group_stores,
        ))

    groups.sort(key=lambda g: (-len(g.products), g.canonical_name.lower()))
    return groups
