import { useQuery } from "@tanstack/react-query";
import { fetchAspectSentiment } from "@/services/api";
import type { AspectSentimentData, AspectWindow } from "@/types/api";

/**
 * React Query hook for fetching aspect-level sentiment data.
 * Disabled when entityId is undefined (e.g., before route param resolves).
 *
 * @param entityId - Entity ID string from route params
 * @param window - Time window: "7d", "30d", or "90d" (default "7d")
 * @param source - Optional source filter: "hn", "reddit", "discourse", "devto"
 */
export function useAspectSentiment(
  entityId: string | undefined,
  window: AspectWindow = "7d",
  source?: string
) {
  return useQuery<AspectSentimentData>({
    queryKey: ["aspects", entityId, window, source],
    queryFn: () => fetchAspectSentiment(entityId!, window, source),
    enabled: !!entityId,
    staleTime: 5 * 60 * 1000,   // 5 minutes
    gcTime: 10 * 60 * 1000,     // 10 minutes
  });
}
