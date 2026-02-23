// API Types - shared across the application

export interface Sentiment {
  positive: number;
  neutral: number;
  negative: number;
}

export interface Tool {
  id: string;
  rank: number;
  name: string;
  company: string;
  logo?: string;
  sentiment: Sentiment;
  mentions: number;
  trend: "up" | "down" | "stable";
  trendPercent7d: number; // e.g. 23 for +23%
  sparklineData: number[]; // Last 7 data points for mini sparkline
  type: "llm" | "tool";
}

export interface TrendDataPoint {
  date: string;
  mentions: number;
  sentiment: number; // Aggregated sentiment (70% news + 30% Reddit)
  newsSentiment: number; // News sentiment percentage
  redditSentiment: number | null; // Reddit sentiment percentage (null if unavailable)
}

export interface Mention {
  id: string;
  source: string;
  text: string;
  date: string;
  sentiment: "positive" | "neutral" | "negative";
}

export interface ToolDetail extends Tool {
  description: string;
  versions: string[];
  currentVersion: string;
  bestFor: string[];
  rating: number;
  trendData: TrendDataPoint[];
  recentMentions: Mention[];
}

// =============================================================================
// ASPECT SENTIMENT TYPES (Phase 9)
// =============================================================================

/** Aggregated score for a single aspect within a time window (matches backend AspectWindowSchema) */
export interface AspectWindowData {
  mean: number | null;  // [-1.0, 1.0], null if no data
  count: number;
}

/** Response from GET /entities/{id}/aspects (matches backend AspectSentimentResponse) */
export interface AspectSentimentData {
  entity_id: number;
  window: "7d" | "30d" | "90d";
  source: string | null;
  aspects: {
    performance: AspectWindowData;
    cost: AspectWindowData;
    reliability: AspectWindowData;
    ux: AspectWindowData;
    speed: AspectWindowData;
    code_quality: AspectWindowData;
    context_window: AspectWindowData;
  };
}

/** All valid source filter values for the UI */
export type SourceFilter = "all" | "hn" | "reddit" | "discourse" | "devto";

/** All valid aspect window sizes */
export type AspectWindow = "7d" | "30d" | "90d";
