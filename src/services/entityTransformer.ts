// Data Transformation Layer
// Transforms backend EntitySchema to frontend Tool/ToolDetail format

import type { Tool, ToolDetail, Sentiment } from "@/types/api";
import type { SentimentPoint } from "@/hooks/useSentimentTimeSeries";
import {
  calculate7DayTrend,
  getTrendDirection,
  generateSparklineData,
  generateTrendData,
} from "./trendCalculator";

// =============================================================================
// LOGO MAPPING - Reliable logo URLs for all companies
// =============================================================================

// Model family logos - matches by prefix in model name
const modelFamilyLogos: Record<string, string> = {
  // OpenAI models
  "gpt": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/openai.png",
  "openai": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/openai.png",
  "dall-e": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/openai.png",
  "chatgpt": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/openai.png",

  // Anthropic/Claude models
  "claude": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/claude-color.png",

  // Google models
  "gemini": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/gemini.png",
  "gemma": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/gemini.png",

  // Meta models
  "llama": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/meta-color.png",

  // Mistral models
  "mistral": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/mistral-color.png",
  "mixtral": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/mistral-color.png",
  "codestral": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/mistral-color.png",

  // DeepSeek models
  "deepseek": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/deepseek-color.png",

  // xAI/Grok models
  "grok": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/grok.png",

  // Cohere models
  "command": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/cohere-color.png",

  // Perplexity models
  "perplexity": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/perplexity-color.png",
  "sonar": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/perplexity-color.png",

  // Alibaba models
  "qwen": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/qwen-color.png",

  // Microsoft models
  "phi": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/azure.png",
};

// Company logos - fallback when no model prefix matches
const companyLogos: Record<string, string> = {
  "OpenAI": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/openai.png",
  "Anthropic": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/claude-color.png",
  "Google": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/gemini.png",
  "Meta": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/meta-color.png",
  "Mistral AI": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/mistral-color.png",
  "DeepSeek": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/deepseek-color.png",
  "xAI": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/grok.png",
  "Cohere": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/cohere-color.png",
  "Perplexity AI": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/perplexity-color.png",
  "Alibaba": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/qwen-color.png",
  "01.AI": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/yi-color.png",
  "Microsoft": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/azure.png",
  "Databricks": "https://avatars.githubusercontent.com/u/4998052?s=200&v=4",
  "TII": "https://avatars.githubusercontent.com/u/95152865?s=200&v=4",
  "Inflection AI": "https://avatars.githubusercontent.com/u/127966711?s=200&v=4",
  "Moonshot AI": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/moonshot.png",
  "BigCode": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/huggingface-color.png",
  "WizardLM": "https://avatars.githubusercontent.com/u/130567770?s=200&v=4",

  // Tool Companies
  "Cursor Inc.": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/cursor.png",
  "Lovable": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/lovable-color.png",
  "Vercel": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/vercel.png",
  "StackBlitz": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/stackblitz.png",
  "Replit": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/replit-color.png",
  "GitHub": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/github.png",
  "Codeium": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/codeium-color.png",
  "Midjourney": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/midjourney.png",
  "Stability AI": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/stability-color.png",
  "Runway": "https://avatars.githubusercontent.com/u/25898221?s=200&v=4",
  "Figma": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/figma-color.png",
  "Notion": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/notion.png",
  "Jasper AI": "https://avatars.githubusercontent.com/u/89174667?s=200&v=4",
  "Copy.ai": "https://avatars.githubusercontent.com/u/75654792?s=200&v=4",
  "Grammarly": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/grammarly.png",
  "DeepL": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/deepl-color.png",
  "Otter.ai": "https://avatars.githubusercontent.com/u/34316882?s=200&v=4",
  "Descript": "https://avatars.githubusercontent.com/u/22982566?s=200&v=4",
  "ElevenLabs": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/elevenlabs.png",
  "Synthesia": "https://avatars.githubusercontent.com/u/28540323?s=200&v=4",
  "HeyGen": "https://avatars.githubusercontent.com/u/97590381?s=200&v=4",
  "Canva": "https://static.canva.com/static/images/favicon-1.ico",
  "Adobe": "https://www.adobe.com/favicon.ico",
  "Pika": "https://avatars.githubusercontent.com/u/134440818?s=200&v=4",
  "Suno": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/suno.png",
  "Udio": "https://avatars.githubusercontent.com/u/161574918?s=200&v=4",
  "Gamma": "https://avatars.githubusercontent.com/u/88725516?s=200&v=4",
  "Beautiful.ai": "https://avatars.githubusercontent.com/u/30329723?s=200&v=4",
  "Tome": "https://avatars.githubusercontent.com/u/60209684?s=200&v=4",
  "Zapier": "https://cdn.zapier.com/zapier/images/favicon.png",
  "Make": "https://images.ctfassets.net/qqlj6g4ee76j/2gPlhqHLriGR36sWhmAGdA/a77d1a1e8e4f1b5a8db98efd1c9ece11/android-chrome-192x192.png",
  "n8n": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/n8n.png",
  "LangChain": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/langchain-color.png",
  "LlamaIndex": "https://avatars.githubusercontent.com/u/130722866?s=200&v=4",
  "Hugging Face": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/huggingface-color.png",
  "Amazon": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/aws.png",
  "Pinecone": "https://avatars.githubusercontent.com/u/54333248?s=200&v=4",
  "Weaviate": "https://avatars.githubusercontent.com/u/37794290?s=200&v=4",
  "Supabase": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/supabase-color.png",
  "Base44": "https://avatars.githubusercontent.com/u/128663099?s=200&v=4",
  "Tempo": "https://avatars.githubusercontent.com/u/135779431?s=200&v=4",
  "Magic Patterns": "https://avatars.githubusercontent.com/u/128457295?s=200&v=4",
};

/**
 * Get logo URL - first checks model name prefix, then falls back to company
 */
function getToolLogo(name: string, company: string): string {
  const nameLower = name.toLowerCase();

  // Check model family prefixes first
  for (const [prefix, logo] of Object.entries(modelFamilyLogos)) {
    if (nameLower.startsWith(prefix) || nameLower.includes(prefix)) {
      return logo;
    }
  }

  // Fallback to company logo
  return companyLogos[company] || `https://logo.clearbit.com/${company.toLowerCase().replace(/\s+/g, '')}.com`;
}

// Backend schema types (matching backend API responses)
interface EntitySchema {
  id: number;
  name: string;
  category: string;
  created_at: string;
  latest_sentiment?: number | null;  // Optional in list, always present in detail
}

interface EntityDetailSchema extends EntitySchema {
  latest_sentiment: number | null;
}

// =============================================================================
// TRANSFORMATION FUNCTIONS
// =============================================================================

/**
 * Calculate sentiment distribution from time-series data
 * Counts positive/neutral/negative occurrences and returns percentages
 * @param timeseries - Array of sentiment time-series points
 * @returns Sentiment object with positive, neutral, negative percentages
 */
function calculateSentimentDistribution(timeseries: SentimentPoint[]): Sentiment {
  if (!timeseries || timeseries.length === 0) {
    return { positive: 0, neutral: 100, negative: 0 };
  }

  let positive = 0;
  let neutral = 0;
  let negative = 0;

  for (const point of timeseries) {
    const score = point.sentiment_mean;
    if (score === null || score === undefined) {
      neutral++;
    } else if (score > 0.05) {
      positive++;
    } else if (score < -0.05) {
      negative++;
    } else {
      neutral++;
    }
  }

  const total = positive + neutral + negative;

  if (total === 0) {
    return { positive: 0, neutral: 100, negative: 0 };
  }

  return {
    positive: Math.round((positive / total) * 100),
    neutral: Math.round((neutral / total) * 100),
    negative: Math.round((negative / total) * 100),
  };
}

/**
 * Map backend category to frontend type
 */
function mapCategoryToType(category: string): "llm" | "tool" {
  return category === "model" ? "llm" : "tool";
}

/**
 * Transform EntitySchema to Tool format
 * @param entity - Backend entity object
 * @param timeseries - Optional time-series data for trend calculations
 * @returns Frontend Tool object
 */
export function toTool(entity: EntitySchema, timeseries?: SentimentPoint[]): Tool {
  // Calculate sentiment distribution from time-series if available
  const sentiment = calculateSentimentDistribution(timeseries || []);

  // Calculate trends from time-series if provided
  let trend: "up" | "down" | "stable" = "stable";
  let trendPercent7d: number = 0;
  let sparklineData: number[] = [];

  if (timeseries && timeseries.length > 0) {
    const trendResult = calculate7DayTrend(timeseries);
    trendPercent7d = trendResult.trendPercent;
    trend = getTrendDirection(trendPercent7d);
    sparklineData = generateSparklineData(timeseries, 7); // 7 days for sparkline
  }

  return {
    id: entity.id.toString(),
    rank: 0,
    name: entity.name,
    company: "Unknown",
    logo: getToolLogo(entity.name, "Unknown"),
    sentiment,
    mentions: timeseries?.length || 0, // Use timeseries count as mentions
    trend,
    trendPercent7d,
    sparklineData,
    type: mapCategoryToType(entity.category),
  };
}

/**
 * Transform EntityDetailSchema to ToolDetail format
 * @param entity - Backend entity detail object
 * @param timeseries - Optional time-series data for trend calculations
 * @returns Frontend ToolDetail object
 */
export function toToolDetail(entity: EntityDetailSchema, timeseries?: SentimentPoint[]): ToolDetail {
  // Calculate sentiment distribution from time-series if available
  const sentiment = calculateSentimentDistribution(timeseries || []);

  // Calculate trends from time-series if provided
  let trend: "up" | "down" | "stable" = "stable";
  let trendPercent7d: number = 0;
  let sparklineData: number[] = [];
  let trendData: Array<{ date: string; mentions: number; sentiment: number }> = [];

  if (timeseries && timeseries.length > 0) {
    const trendResult = calculate7DayTrend(timeseries);
    trendPercent7d = trendResult.trendPercent;
    trend = getTrendDirection(trendPercent7d);
    sparklineData = generateSparklineData(timeseries, 7);
    trendData = generateTrendData(timeseries);
  }

  return {
    id: entity.id.toString(),
    rank: 0,
    name: entity.name,
    company: "Unknown",
    logo: getToolLogo(entity.name, "Unknown"),
    sentiment,
    mentions: timeseries?.length || 0,
    trend,
    trendPercent7d,
    sparklineData,
    type: mapCategoryToType(entity.category),
    // Extended fields
    description: `${entity.name} is a ${entity.category} in the AI ecosystem.`,
    versions: ["Latest"],
    currentVersion: "Latest",
    bestFor: ["AI"],
    rating: 4.0,
    trendData,
    recentMentions: [],
  };
}
