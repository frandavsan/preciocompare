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

# Matches unit-spec tokens produced by _UNIT_SUBS (e.g. "128gb", "570l", "1000rpm").
# These look like model codes (letters + digits) but are product attributes, not identifiers.
_UNIT_SPEC_RE: re.Pattern = re.compile(
    r'^\d+(?:gb|tb|mb|kg|l|rpm|w|hz|v|ah|mah)$'
)

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
    # Strip 2-letter country/region suffixes appended directly to long model codes:
    # "WW95AA046BXUBG" → "WW95AA046BXU" (BG = Argentina Samsung suffix).
    # Only fires on tokens ≥10 chars so short codes like "A16" are unaffected.
    (re.compile(r'([A-Z0-9]{8,})(AR|BG|CL|BR|MX|UY|PE|CO)\b', re.IGNORECASE), r'\1'),
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
      5. Strip feature-bullet suffix (│-delimited) before tokenizing — Castillo
         appends "│ 70% Ahorro │ AI ThinQ │ …" which inflates the token set.
      6. Glue adjacent alpha+digit pairs as model-code aliases so "Stage 301"
         and "STAGE301" share the token "stage301" and match each other.
    """
    # Strip everything from the first │ (U+2502) — it's always a feature-bullet
    # separator added by some stores, never part of a model name.
    if '\u2502' in name:
        name = name[:name.index('\u2502')]
    s = _norm(name)
    for pattern, repl in _UNIT_SUBS:
        s = pattern.sub(repl, s)
    tokens = re.findall(r'[a-z0-9]+', s)
    meaningful = [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]
    glued: set[str] = set(meaningful)
    for i in range(len(meaningful) - 1):
        a, b = meaningful[i], meaningful[i + 1]
        if (a.isalpha() and b.isdigit()) or (a.isdigit() and b.isalpha()):
            glued.add(a + b)
    return frozenset(glued)


_MAX_PRICE_RATIO = 2.0  # reject cross-store matches where price differs by more than 2×


def _group_median_price(products: dict[str, ProductResult]) -> float | None:
    """Median price of products with known prices; None if no prices are known."""
    prices = sorted(p.price for p in products.values() if p.price is not None)
    if not prices:
        return None
    mid = len(prices) // 2
    return (prices[mid - 1] + prices[mid]) / 2 if len(prices) % 2 == 0 else prices[mid]


def _detect_brand(keys: frozenset[str]) -> str | None:
    """Return the first brand token found in keys, or None."""
    return next((k for k in keys if k in _BRANDS), None)


def _is_model_code(token: str) -> bool:
    """True if token is a model code (letters + digits, ≥4 chars, not a unit spec)."""
    return (
        len(token) >= 4
        and any(c.isalpha() for c in token)
        and any(c.isdigit() for c in token)
        and not _UNIT_SPEC_RE.match(token)
    )


def _has_model_code(tokens: frozenset[str]) -> bool:
    """True if any token is a model code."""
    return any(_is_model_code(t) for t in tokens)


def _has_strong_model_code(tokens: frozenset[str]) -> bool:
    """True if any token is a strong model code (≥5 chars, letters + digits).

    Strong codes like "gs66sxsc", "55pud7310", "stage301" are unambiguous
    product identifiers — sharing one is near-certain proof of a match.
    Weak codes (4 chars, e.g. "2k25") are too short to be conclusive alone.
    """
    return any(_is_model_code(t) and len(t) >= 5 for t in tokens)


def _keys_match(a: frozenset[str], b: frozenset[str]) -> bool:
    """
    Two key sets match if:
      - The shorter is a subset of the longer (strict identity), OR
      - They share a strong model code (≥5 chars, e.g. "stage301") → instant match, OR
      - They share a weak model code (4 chars) and ≥50% overlap, OR
      - ≥80% of the shorter set appears in the longer (general fallback)
    """
    if not a or not b:
        return False
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if shorter <= longer:
        return True
    overlap = shorter & longer
    if _has_strong_model_code(overlap):
        return True
    ratio = len(overlap) / len(shorter)
    if _has_model_code(overlap):
        return ratio >= 0.50
    return ratio >= 0.80


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
        group_keysets: dict[str, frozenset[str]] = {store_i: keys_i}

        for j, (store_j, prod_j, keys_j, brand_j) in enumerate(flat):
            if assigned[j] or store_j == store_i:
                continue
            if brand_i is not None and brand_j is not None and brand_i != brand_j:
                continue
            if not any(_keys_match(gk, keys_j) for gk in group_keysets.values()):
                continue
            # Price outlier guard: skip if price is >2× or <0.5× the group median.
            # Catches cases where a same-named product line has very different models
            # (e.g. Gran Lattissima $800k vs $1.7M — different machines, same brand line).
            if prod_j.price is not None:
                median = _group_median_price(group_stores)
                if median is not None:
                    ratio = prod_j.price / median
                    if ratio > _MAX_PRICE_RATIO or ratio < 1.0 / _MAX_PRICE_RATIO:
                        continue
            if store_j not in group_stores:
                group_stores[store_j] = prod_j
                group_keysets[store_j] = keys_j
            else:
                # Store already represented — keep the product with higher overlap
                existing_keys = _prod_keys[id(group_stores[store_j])]
                best_overlap = max(len(gk & keys_j) for gk in group_keysets.values())
                existing_overlap = max(len(gk & existing_keys) for gk in group_keysets.values())
                if best_overlap > existing_overlap:
                    group_stores[store_j] = prod_j
                    group_keysets[store_j] = keys_j
            assigned[j] = True

        canonical = max(group_stores.values(), key=lambda p: len(_prod_keys[id(p)]))
        groups.append(ProductGroup(
            canonical_name=canonical.name,
            fingerprint=keys_i,
            products=group_stores,
        ))

    groups.sort(key=lambda g: (-len(g.products), g.canonical_name.lower()))
    return groups
