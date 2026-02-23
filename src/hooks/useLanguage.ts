// Minimal i18n hook — provides a t() translation function.
// All keys return English strings by default.
const translations: Record<string, string> = {
  backToDashboard: "Back to Dashboard",
  toolNotFound: "Tool not found",
  sentiment: "Sentiment",
  mentions: "Mentions",
  trendLast6Months: "Trend (Last 6 Months)",
  bestFor: "Best For",
  rating: "Rating",
  recentMentions: "Recent Mentions",
  selectModel: "Select model",
  positivePercent: "positive",
  source: "Source",
  days7: "7 Days",
  positive: "Positive",
  negative: "Negative",
  trendUp: "Trending up",
  trendDown: "Trending down",
  trendStable: "Stable",
  errorLoading: "Error loading data",
};

export function useLanguage() {
  const t = (key: string): string => translations[key] ?? key;
  return { t };
}
