import { useQuery } from "@tanstack/react-query";

// Backend API response types for time-series data
interface SentimentPoint {
  timestamp: string;
  period: string;
  sentiment_mean: number | null;
  sentiment_min: number | null;
  sentiment_max: number | null;
  sentiment_std: number | null;
  article_count: number | null;
  reddit_sentiment: number | null;
  reddit_thread_count: number | null;
}

interface SentimentTimeseriesResponse {
  entity_id: number;
  period: string;
  data: SentimentPoint[];
  next_cursor: string | null;
  has_more: boolean;
}

// API base URL
const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

/**
 * Fetch sentiment time-series data for an entity
 * @param id - Entity ID
 * @param period - Time period granularity ("hourly" or "daily")
 * @param cursor - Optional cursor for pagination
 */
async function fetchSentimentTimeSeries(
  id: string,
  period: "hourly" | "daily" = "hourly",
  cursor?: string
): Promise<SentimentTimeseriesResponse> {
  const url = new URL(`${BASE_URL}/entities/${id}/sentiment`);
  url.searchParams.set("period", period);
  if (cursor) {
    url.searchParams.set("cursor", cursor);
  }

  const response = await fetch(url.toString());

  if (!response.ok) {
    throw new Error(`Failed to fetch time-series: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

/**
 * React Query hook for fetching sentiment time-series data
 * @param entityId - Entity ID to fetch time-series for
 * @param period - Time period granularity (default: "hourly")
 */
export function useSentimentTimeSeries(
  entityId: string | undefined,
  period: "hourly" | "daily" = "hourly"
) {
  return useQuery({
    queryKey: ["sentiment-timeseries", entityId, period],
    queryFn: () => fetchSentimentTimeSeries(entityId!, period),
    enabled: !!entityId,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes (formerly cacheTime)
  });
}
