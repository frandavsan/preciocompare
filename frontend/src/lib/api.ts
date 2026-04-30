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
  constructor(
    public status: number,
    message: string,
    public retryAfterSeconds?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export type ErrorKind = "auth" | "rate_limit" | "server" | "network" | "unknown";

export interface UserFacingError {
  kind: ErrorKind;
  title: string;
  body: string;
}

export function classifyError(err: unknown): UserFacingError {
  if (err instanceof ApiError) {
    if (err.status === 401) {
      return {
        kind: "auth",
        title: "Sesion expirada",
        body: "Iniciá sesión nuevamente para continuar.",
      };
    }
    if (err.status === 429) {
      return {
        kind: "rate_limit",
        title: "Demasiadas busquedas",
        body: "Esperá un momento antes de volver a intentar.",
      };
    }
    if (err.status >= 500) {
      return {
        kind: "server",
        title: "Servicio no disponible",
        body: "Hay un problema con el servidor. Reintentá en unos segundos.",
      };
    }
    return {
      kind: "unknown",
      title: "No se pudo completar la busqueda",
      body: err.message || "Reintentá en unos segundos.",
    };
  }
  return {
    kind: "network",
    title: "Sin conexion",
    body: "Verificá tu conexión a internet e intentá nuevamente.",
  };
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
    let retryAfterSeconds: number | undefined;
    if (response.status === 429) {
      const header = response.headers.get("Retry-After");
      const parsed = header ? parseInt(header, 10) : NaN;
      if (Number.isFinite(parsed) && parsed > 0) retryAfterSeconds = parsed;
    }
    try {
      const body = await response.json();
      detail = body.detail ?? body.error ?? detail;
      if (retryAfterSeconds === undefined && typeof body.retry_after === "number") {
        retryAfterSeconds = body.retry_after;
      }
    } catch {
      // response body wasn't JSON; fall back to statusText
    }
    throw new ApiError(response.status, detail, retryAfterSeconds);
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

// Streams the generated Excel as a Blob plus its server-side filename. Kept
// separate from `apiFetch` because that helper assumes a JSON body — this
// endpoint returns binary content with the filename in Content-Disposition.
export async function downloadPricingExcel(
  q: string,
  token: string,
  commerceName?: string,
  init?: RequestInit,
): Promise<{ blob: Blob; filename: string }> {
  const params = new URLSearchParams({ q });
  const trimmedCommerceName = commerceName?.trim();
  if (trimmedCommerceName) {
    params.set("commerce_name", trimmedCommerceName);
  }
  const response = await fetch(`${API_BASE_URL}/pricing/excel?${params}`, {
    ...init,
    headers: {
      ...(init?.headers ?? {}),
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    let detail = response.statusText;
    let retryAfterSeconds: number | undefined;
    if (response.status === 429) {
      const header = response.headers.get("Retry-After");
      const parsed = header ? parseInt(header, 10) : NaN;
      if (Number.isFinite(parsed) && parsed > 0) retryAfterSeconds = parsed;
    }
    try {
      const body = await response.json();
      detail = body.detail ?? body.error ?? detail;
    } catch {
      // body wasn't JSON; fall through
    }
    throw new ApiError(response.status, detail, retryAfterSeconds);
  }

  const blob = await response.blob();
  const cd = response.headers.get("Content-Disposition") ?? "";
  const match = cd.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
  const filename = match ? decodeURIComponent(match[1]) : "pricing.xlsx";
  return { blob, filename };
}
