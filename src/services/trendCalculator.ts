// Trend calculation utilities for sentiment time-series data
// Handles aggregation of hourly data into daily averages

import type { SentimentPoint } from "@/hooks/useSentimentTimeSeries";

// =============================================================================
// TYPES
// =============================================================================

/**
 * Aggregated daily sentiment data
 */
export interface DailySentiment {
  date: string;  // ISO date string (YYYY-MM-DD)
  avg: number;   // Average sentiment for the day
  count: number; // Number of data points aggregated
}

// =============================================================================
// AGGREGATION FUNCTIONS
// =============================================================================

/**
 * Extract date (YYYY-MM-DD) from ISO timestamp string
 */
function extractDate(timestamp: string): string {
  return timestamp.split('T')[0];
}

/**
 * Aggregate hourly time-series data into daily averages
 * @param timeseries - Array of sentiment time-series points (hourly, newest first)
 * @returns Array of daily averages (newest first)
 */
export function aggregateToDaily(timeseries: SentimentPoint[]): DailySentiment[] {
  if (!timeseries || timeseries.length === 0) {
    return [];
  }

  // Filter out null sentiment values
  const validPoints = timeseries.filter(
    (point) => point.sentiment_mean !== null && point.sentiment_mean !== undefined
  );

  // Group by date
  const dailyMap = new Map<string, number[]>();

  for (const point of validPoints) {
    const date = extractDate(point.timestamp);
    if (!dailyMap.has(date)) {
      dailyMap.set(date, []);
    }
    dailyMap.get(date)!.push(point.sentiment_mean!);
  }

  // Calculate daily averages
  const dailyData: DailySentiment[] = [];

  for (const [date, values] of dailyMap.entries()) {
    const avg = values.reduce((sum, val) => sum + val, 0) / values.length;
    dailyData.push({
      date,
      avg,
      count: values.length,
    });
  }

  // Sort by date descending (newest first)
  dailyData.sort((a, b) => b.date.localeCompare(a.date));

  return dailyData;
}

/**
 * Get sentiment values from daily data for sparkline
 * Returns up to N days of values (oldest first for chart rendering)
 */
export function getSparklineValues(dailyData: DailySentiment[], days: number = 7): number[] {
  // Take the most recent N days
  const recent = dailyData.slice(0, days);
  // Reverse for chronological order (oldest first)
  return recent.reverse().map((d) => d.avg);
}

// =============================================================================
// TREND CALCULATION FUNCTIONS
// =============================================================================

/**
 * Calculate 7-day trend from time-series data
 * Uses raw data points split by time (recent half vs older half)
 * This approach is more robust than daily averages for sparse binary data
 * @param timeseries - Array of sentiment time-series points (hourly, newest first)
 * @returns Trend percentage and metadata
 */
export function calculate7DayTrend(timeseries: SentimentPoint[]): {
  trendPercent: number;
  latestAvg: number;
  baselineAvg: number;
  daysWithData: number;
} {
  // Filter out null sentiment values
  const validPoints = timeseries.filter(
    (point) => point.sentiment_mean !== null && point.sentiment_mean !== undefined
  );

  // Need at least 10 data points for meaningful trend
  if (validPoints.length < 10) {
    return { trendPercent: 0, latestAvg: 0, baselineAvg: 0, daysWithData: 0 };
  }

  // Split data: recent 40% vs older 60% (roughly last 3 days vs previous 4-5 days)
  const splitPoint = Math.floor(validPoints.length * 0.4);
  const recentPoints = validPoints.slice(0, splitPoint);
  const olderPoints = validPoints.slice(splitPoint);

  // Calculate averages
  const recentAvg = recentPoints.reduce((sum, p) => sum + p.sentiment_mean!, 0) / recentPoints.length;
  const olderAvg = olderPoints.reduce((sum, p) => sum + p.sentiment_mean!, 0) / olderPoints.length;

  // Calculate trend percentage
  let trendPercent = 0;

  // Use a conservative calculation that reduces extreme swings
  // The difference in sentiment is divided by 2 (the full range is -1 to 1)
  const rawDiff = recentAvg - olderAvg;
  trendPercent = rawDiff * 50; // Scale so that -1 to +1 difference becomes -50% to +50%

  // Clamp to reasonable range
  trendPercent = Math.max(-50, Math.min(50, trendPercent));

  // Round to 1 decimal place
  trendPercent = Math.round(trendPercent * 10) / 10;

  // Also compute daily averages for the return value (for display/debugging)
  const dailyData = aggregateToDaily(timeseries);
  const latestDaily = dailyData.length > 0 ? dailyData[0].avg : 0;
  const baselineDaily = dailyData.length > 1
    ? dailyData.slice(1, 7).reduce((sum, d) => sum + d.avg, 0) / Math.min(6, dailyData.length - 1)
    : 0;

  return {
    trendPercent,
    latestAvg: latestDaily,
    baselineAvg: baselineDaily,
    daysWithData: dailyData.length,
  };
}

/**
 * Determine trend direction from trend percentage
 * @param trendPercent - Trend percentage from calculate7DayTrend
 * @returns Trend direction: "up", "down", or "stable"
 */
export function getTrendDirection(trendPercent: number): "up" | "down" | "stable" {
  if (trendPercent > 2) {
    return "up";
  } else if (trendPercent < -2) {
    return "down";
  }
  return "stable";
}

/**
 * Generate sparkline data for visualization
 * Returns 7 days of sentiment values (oldest first for proper chart rendering)
 * @param timeseries - Array of sentiment time-series points (hourly, newest first)
 * @returns Array of sentiment values for the last 7 days
 */
export function generateSparklineData(
  timeseries: SentimentPoint[],
  days: number = 7
): number[] {
  const dailyData = aggregateToDaily(timeseries);
  return getSparklineValues(dailyData, days);
}

/**
 * Generate trend data array for detailed view
 * Converts time-series points to TrendDataPoint format with daily aggregation
 * @param timeseries - Array of sentiment time-series points (hourly, newest first)
 * @returns Array of trend data points with daily aggregation (oldest first)
 */
export function generateTrendData(timeseries: SentimentPoint[]): Array<{
  date: string;
  mentions: number;
  sentiment: number;
}> {
  if (!timeseries || timeseries.length === 0) {
    return [];
  }

  // Aggregate to daily
  const dailyData = aggregateToDaily(timeseries);

  // Convert to trend data format
  // Also sum up mentions for each day
  const dailyMap = new Map<string, { sentiment: number; mentions: number }>();

  for (const point of timeseries) {
    if (point.sentiment_mean === null || point.sentiment_mean === undefined) continue;

    const date = extractDate(point.timestamp);

    if (!dailyMap.has(date)) {
      dailyMap.set(date, { sentiment: 0, mentions: 0 });
    }

    const entry = dailyMap.get(date)!;
    entry.sentiment = (entry.sentiment * entry.mentions + point.sentiment_mean) / (entry.mentions + 1);
    entry.mentions += point.article_count || 0;
  }

  // Convert to array and sort chronologically
  const trendData = Array.from(dailyMap.entries())
    .map(([date, data]) => ({
      date,
      mentions: data.mentions,
      sentiment: Math.round(data.sentiment * 100) / 100,
    }))
    .sort((a, b) => a.date.localeCompare(b.date));

  return trendData;
}
