const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

if (!API_BASE_URL) {
  throw new Error(
    "VITE_API_BASE_URL missing. Set it in frontend/.env.development (dev) or frontend/.env.production (build)."
  );
}

export interface InstallmentResponse {
  count: number;
  amount: number;
  cards: string[];
}

export interface ProductResponse {
  name: string;
  sku: string | null;
  price: number | null;
  currency: string;
  url: string;
  installments: InstallmentResponse[];
  free_shipping: boolean;
  international: boolean | null;
  available: boolean;
  image_url: string | null;
}

export type StoreStatus = "ok" | "error" | "timeout";

export interface StoreStatusResponse {
  status: StoreStatus;
  result_count: number;
  error_detail: string | null;
  duration_ms: number | null;
}

export interface SearchResponse {
  query: string;
  results: Record<string, ProductResponse[]>;
  store_status: Record<string, StoreStatusResponse>;
}

export interface StoreInfo {
  name: string;
  base_url: string;
  platform: string;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function apiFetch<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(init?.headers ?? {}),
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? body.error ?? detail;
    } catch {
      // response body wasn't JSON; fall back to statusText
    }
    throw new ApiError(response.status, detail);
  }

  return (await response.json()) as T;
}

export function searchProducts(
  q: string,
  detail: boolean,
  token: string,
  init?: RequestInit,
  postalCode?: string
): Promise<SearchResponse> {
  const params = new URLSearchParams({ q, detail: String(detail) });
  if (postalCode) {
    params.set("postal_code", postalCode);
  }
  return apiFetch<SearchResponse>(`/search?${params}`, token, init);
}

export function listStores(token: string, init?: RequestInit): Promise<StoreInfo[]> {
  return apiFetch<StoreInfo[]>("/stores", token, init);
}
