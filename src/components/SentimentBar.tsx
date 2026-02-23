interface SentimentBarProps {
  positive: number;
  neutral: number;
  negative: number;
  className?: string;
}

const SentimentBar = ({ positive, neutral, negative, className = "" }: SentimentBarProps) => {
  const total = positive + neutral + negative;
  if (total === 0) return null;

  const positivePercent = (positive / total) * 100;
  const neutralPercent = (neutral / total) * 100;
  const negativePercent = (negative / total) * 100;

  return (
    <div className={`flex h-2 rounded-full overflow-hidden ${className}`}>
      <div
        className="bg-[hsl(var(--sentiment-positive))]"
        style={{ width: `${positivePercent}%` }}
        title={`Positive: ${positivePercent.toFixed(0)}%`}
      />
      <div
        className="bg-[hsl(var(--muted-foreground)/0.3)]"
        style={{ width: `${neutralPercent}%` }}
        title={`Neutral: ${neutralPercent.toFixed(0)}%`}
      />
      <div
        className="bg-[hsl(var(--sentiment-negative))]"
        style={{ width: `${negativePercent}%` }}
        title={`Negative: ${negativePercent.toFixed(0)}%`}
      />
    </div>
  );
};

export default SentimentBar;
