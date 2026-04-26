import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { searchProducts, type SearchResponse } from "@/lib/api";
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
    retry: false,
  });
}
