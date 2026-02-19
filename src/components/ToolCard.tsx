import { useState } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import MiniSparkline from "./MiniSparkline";
import { useLanguage } from "@/hooks/useLanguage";
import type { Tool } from "@/types/api";

interface ToolCardProps {
  tool: Tool;
}

const formatMentions = (mentions: number): string => {
  if (mentions >= 1000000) {
    return `${(mentions / 1000000).toFixed(1)}M`;
  }
  if (mentions >= 1000) {
    return `${(mentions / 1000).toFixed(1)}k`;
  }
  return mentions.toString();
};

const ToolCard = ({ tool }: ToolCardProps) => {
  const [imageError, setImageError] = useState(false);
  const { t } = useLanguage();
  
  const total = tool.sentiment.positive + tool.sentiment.neutral + tool.sentiment.negative;
  const positivePercent = total > 0 ? Math.round((tool.sentiment.positive / total) * 100) : 0;
  const negativePercent = total > 0 ? Math.round((tool.sentiment.negative / total) * 100) : 0;

  const trendColor = tool.trendPercent7d >= 0 
    ? "text-[hsl(var(--trend-up))]" 
    : "text-[hsl(var(--trend-down))]";

  const sparklineColor = tool.trendPercent7d >= 0 
    ? "hsl(var(--trend-up))" 
    : "hsl(var(--trend-down))";

  return (
    <Link to={`/detail/${tool.id}`}>
      <Card className="card-hover cursor-pointer bg-card border-border/50 rounded-2xl overflow-hidden">
        <CardContent className="p-5">
          {/* Header: Logo + Name | Rank */}
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-secondary flex items-center justify-center overflow-hidden">
                {tool.logo && !imageError ? (
                  <img 
                    src={tool.logo} 
                    alt={tool.name} 
                    className="w-6 h-6 object-contain"
                    onError={() => setImageError(true)}
                  />
                ) : (
                  <span className="text-base font-semibold text-muted-foreground">
                    {tool.name.charAt(0)}
                  </span>
                )}
              </div>
              <h3 className="font-semibold text-foreground">{tool.name}</h3>
            </div>
            <span className="text-sm font-semibold text-muted-foreground">#{tool.rank}</span>
          </div>

          {/* Sentiment Section */}
          <div className="mb-5">
            <p className="text-xs text-muted-foreground mb-3">{t("sentiment")}:</p>
            <div className="grid grid-cols-2 gap-4">
              {/* Positive */}
              <div>
                <div className="flex items-center gap-1.5 mb-1.5">
                  <span className="text-sm">😊</span>
                  <span className="text-xs text-muted-foreground">{t("positive")}</span>
                  <span className="text-xs font-semibold text-foreground ml-auto">{positivePercent}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-secondary overflow-hidden">
                  <div 
                    className="h-full bg-[hsl(var(--sentiment-positive))] transition-all duration-300"
                    style={{ width: `${positivePercent}%` }}
                  />
                </div>
              </div>
              {/* Negative */}
              <div>
                <div className="flex items-center gap-1.5 mb-1.5">
                  <span className="text-sm">😠</span>
                  <span className="text-xs text-muted-foreground">{t("negative")}</span>
                  <span className="text-xs font-semibold text-foreground ml-auto">{negativePercent}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-secondary overflow-hidden">
                  <div 
                    className="h-full bg-[hsl(var(--sentiment-negative))] transition-all duration-300"
                    style={{ width: `${negativePercent}%` }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Mentions + Trend */}
          <div className="flex items-center justify-between py-3 border-t border-border/50">
            <div className="flex items-center gap-2">
              <span className="text-sm">📈</span>
              <span className="text-xs text-muted-foreground">{t("mentions")}:</span>
              <span className="text-sm font-semibold text-foreground">{formatMentions(tool.mentions)}</span>
            </div>
            <div className={`text-xs font-semibold ${trendColor}`}>
              {tool.trendPercent7d >= 0 ? "↑" : "↓"}{Math.abs(tool.trendPercent7d)}% ({t("days7")})
            </div>
          </div>

          {/* Mini Sparkline */}
          <div className="pt-3 border-t border-border/50 flex justify-center">
            <MiniSparkline 
              data={tool.sparklineData} 
              color={sparklineColor}
              className="w-full h-8"
            />
          </div>
        </CardContent>
      </Card>
    </Link>
  );
};

export default ToolCard;
