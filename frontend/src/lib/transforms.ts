import type { ProductResponse, SearchResponse, StoreStatus } from "./api";
import { getStoreDisplayName } from "./stores";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export type GroupStatus = StoreStatus | "empty";

export interface StoreResult {
  url: string;
  name: string;
  detail: string;
  price: number;
  available: boolean;
}

export interface StoreGroup {
  storeKey: string;
  displayName: string;
  status: GroupStatus;
  results: StoreResult[];
}

export interface SelectedProduct {
  storeKey: string;
  displayName: string;
  product: ProductResponse;
}

export function formatPrice(price: number): string {
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
    maximumFractionDigits: 0,
  }).format(price);
}

// Highest installment count whose total (count * amount) doesn't exceed the
// product's price (within a small tolerance for rounding). Returns null if no
// such plan exists.
export function bestSinInteresCount(product: ProductResponse): number | null {
  if (!product.price || !product.installments?.length) return null;
  let best: number | null = null;
  for (const ins of product.installments) {
    if (ins.count <= 1) continue;
    const total = ins.amount * ins.count;
    if (total <= product.price * 1.01 && (best === null || ins.count > best)) {
      best = ins.count;
    }
  }
  return best;
}

function bestSinInteresInstallment(product: ProductResponse) {
  const count = bestSinInteresCount(product);
  if (count === null || product.price === null) return null;
  return product.installments.find((ins) => {
    if (ins.count !== count) return false;
    const total = ins.amount * ins.count;
    return total <= product.price * 1.01;
  }) ?? null;
}

export function formatBestPromo(product: ProductResponse): string | null {
  const installment = bestSinInteresInstallment(product);
  if (!installment || product.price === null) return null;
  const count = installment.count;
  const installmentAmount = Math.round(product.price / count);
  const issuer = installment.cards.find((card) => card.trim().length > 0)?.trim();
  return `${count}x sin interes de ${formatPrice(installmentAmount)}${issuer ? ` (${issuer})` : ""}`;
}

function buildResultDetail(product: ProductResponse): string {
  const bits: string[] = [];
  const promo = formatBestPromo(product);
  if (promo) bits.push(promo);
  if (product.free_shipping) bits.push("envio gratis");
  if (!bits.length) bits.push(product.available ? "Stock disponible" : "Sin stock");
  return bits.join(" · ");
}

export function searchToStoreGroups(
  response: SearchResponse,
  storeKeys: readonly string[],
): StoreGroup[] {
  return storeKeys.map((key) => {
    const apiStatus = response.store_status[key]?.status ?? "ok";
    const products = response.results[key] ?? [];
    const results: StoreResult[] = products
      .filter((p) => p.price !== null)
      .map((p) => ({
        url: p.url,
        name: p.name,
        detail: buildResultDetail(p),
        price: p.price as number,
        available: p.available,
      }));
    const status: GroupStatus =
      apiStatus !== "ok" ? apiStatus : results.length === 0 ? "empty" : "ok";
    return {
      storeKey: key,
      displayName: getStoreDisplayName(key),
      status,
      results,
    };
  });
}

// Cheapest available product per store (falls back to cheapest overall if
// nothing in stock).
export function autoSelectProducts(response: SearchResponse): SelectedProduct[] {
  const out: SelectedProduct[] = [];
  for (const [storeKey, products] of Object.entries(response.results)) {
    const candidates = products.filter((p) => p.price !== null);
    if (!candidates.length) continue;
    const available = candidates.filter((p) => p.available);
    const pool = available.length ? [...available] : [...candidates];
    pool.sort((a, b) => (a.price as number) - (b.price as number));
    out.push({
      storeKey,
      displayName: getStoreDisplayName(storeKey),
      product: pool[0],
    });
  }
  return out;
}

// Match a per-store URL selection back against the live search response.
// Drops entries whose store is missing or whose URL no longer appears in the
// adapter's results (e.g. paginated out, restocked under a new URL).
export function applySelection(
  response: SearchResponse,
  selection: { store: string; url: string }[],
): SelectedProduct[] {
  const out: SelectedProduct[] = [];
  for (const sel of selection) {
    const products = response.results[sel.store] ?? [];
    const match = products.find((p) => p.url === sel.url);
    if (!match || match.price === null) continue;
    out.push({
      storeKey: sel.store,
      displayName: getStoreDisplayName(sel.store),
      product: match,
    });
  }
  return out;
}

export function resolveImageUrl(path: string | null): string | null {
  if (!path) return null;
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return `${API_BASE_URL}${path}`;
}
