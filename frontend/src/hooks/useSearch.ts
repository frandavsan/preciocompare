import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { ApiError, searchProducts, type SearchResponse } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

interface UseSearchOptions {
  enabled?: boolean;
  detail?: boolean;
  postalCode?: string;
}

// Single source of truth for /search. Both Landing and ProductIntelligence
// call this; React Query dedupes by ["search", q, detail, postalCode] so a
// navigation from Landing -> ProductIntelligence reuses the cached result
// without a second network round-trip.
export function useSearch(
  q: string,
  options: UseSearchOptions = {},
): UseQueryResult<SearchResponse> {
  const { token } = useAuth();
  const { enabled = true, detail = false, postalCode } = options;
  const trimmed = q.trim();

  return useQuery<SearchResponse>({
    queryKey: ["search", trimmed, detail, postalCode ?? null],
    queryFn: ({ signal }) =>
      searchProducts(trimmed, detail, token as string, { signal }, postalCode),
    enabled: Boolean(enabled && trimmed && token),
    staleTime: 5 * 60 * 1000,
    // One retry on transport faults (5xx, network); never on 4xx — the user
    // needs to fix something (auth, rate limit, bad query) and silent retries
    // would just delay surfacing the error.
    retry: (failureCount, error) => {
      if (failureCount >= 1) return false;
      if (error instanceof ApiError) return error.status >= 500;
      return true;
    },
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 4000),
  });
}
