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
