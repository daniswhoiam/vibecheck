import { useParams, Link, useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import Header from "@/components/Header";
import SentimentBar from "@/components/SentimentBar";
import TrendIndicator from "@/components/TrendIndicator";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { useToolDetail, useTools } from "@/hooks/useTools";
import { useLanguage } from "@/hooks/useLanguage";

const Detail = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { t } = useLanguage();
  const { data: tool, isLoading, error } = useToolDetail(id);
  const { data: allTools } = useTools();

  // Get related tools from the same company
  const relatedTools = allTools?.filter(
    (t) => t.company === tool?.company
  ) ?? [];

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background">
        <Header />
        <main className="container mx-auto px-6 pt-24 pb-12">
          <Skeleton className="h-5 w-40 mb-6" />
          <div className="flex items-center gap-4 mb-8">
            <Skeleton className="w-16 h-16 rounded-2xl" />
            <div>
              <Skeleton className="h-7 w-32 mb-2" />
              <Skeleton className="h-5 w-20" />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-24 rounded-2xl" />
            ))}
          </div>
          <Skeleton className="h-80 rounded-2xl" />
        </main>
      </div>
    );
  }

  if (error || !tool) {
    return (
      <div className="min-h-screen bg-background">
        <Header />
        <main className="container mx-auto px-6 pt-24 pb-12">
          <Link 
            to="/" 
            className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors duration-200 mb-6"
          >
            <ArrowLeft className="w-4 h-4" />
            {t("backToDashboard")}
          </Link>
          <div className="text-center py-12">
            <p className="text-destructive">{t("toolNotFound")}</p>
          </div>
        </main>
      </div>
    );
  }

  const sentimentPercent = Math.round(
    (tool.sentiment.positive / 
      (tool.sentiment.positive + tool.sentiment.neutral + tool.sentiment.negative)) * 100
  );

  return (
    <div className="min-h-screen bg-background">
      <Header />
      
      <main className="container mx-auto px-6 pt-24 pb-12">
        {/* Back Link */}
        <Link 
          to="/" 
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors duration-200 mb-6"
        >
          <ArrowLeft className="w-4 h-4" />
          {t("backToDashboard")}
        </Link>

        {/* Header Section */}
        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-6 mb-8">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-2xl bg-secondary flex items-center justify-center">
              {tool.logo ? (
                <img src={tool.logo} alt={tool.name} className="w-10 h-10 object-contain" />
              ) : (
                <span className="text-2xl font-semibold text-muted-foreground">
                  {tool.name.charAt(0)}
                </span>
              )}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-semibold tracking-tight">{tool.name}</h1>
                <Badge variant="secondary" className="rounded-full px-2.5 py-0.5">
                  <TrendIndicator trend={tool.trend} className="text-xs" />
                </Badge>
              </div>
              <p className="text-muted-foreground">{tool.company}</p>
            </div>
          </div>

          <Select
            value={tool.id}
            onValueChange={(value) => navigate(`/detail/${value}`)}
          >
            <SelectTrigger className="w-48 rounded-xl">
              <SelectValue placeholder={t("selectModel")} />
            </SelectTrigger>
            <SelectContent>
              {relatedTools.map((relatedTool) => (
                <SelectItem key={relatedTool.id} value={relatedTool.id}>
                  {relatedTool.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
          <Card className="rounded-2xl border-border/50">
            <CardContent className="p-5">
              <p className="text-sm text-muted-foreground mb-1">{t("sentiment")}</p>
              <p className="text-2xl font-semibold text-[hsl(var(--sentiment-positive))]">
                {sentimentPercent}% {t("positivePercent")}
              </p>
            </CardContent>
          </Card>
          <Card className="rounded-2xl border-border/50">
            <CardContent className="p-5">
              <p className="text-sm text-muted-foreground mb-1">{t("mentions")}</p>
              <p className="text-2xl font-semibold">{tool.mentions.toLocaleString()}</p>
            </CardContent>
          </Card>
        </div>

        {/* Sentiment Trend Chart */}
        <Card className="rounded-2xl border-border/50 mb-8">
          <CardHeader>
            <CardTitle className="text-lg font-semibold">{t("trendLast6Months")}</CardTitle>
          </CardHeader>
          <CardContent>
            {/* Legend showing what each line represents */}
            <div className="flex items-center gap-6 mb-4">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-[hsl(var(--sentiment-positive))]" />
                <span className="text-sm text-muted-foreground">Gesamt (News + Reddit)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-blue-500" />
                <span className="text-sm text-muted-foreground">News</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-orange-500" />
                <span className="text-sm text-muted-foreground">Reddit</span>
              </div>
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={tool.trendData}>
                  <defs>
                    <linearGradient id="sentimentGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="hsl(var(--sentiment-positive))" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="hsl(var(--sentiment-positive))" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis
                    dataKey="date"
                    stroke="hsl(var(--muted-foreground))"
                    fontSize={12}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    orientation="right"
                    stroke="hsl(var(--muted-foreground))"
                    fontSize={12}
                    axisLine={false}
                    tickLine={false}
                    width={40}
                    domain={[0, 100]}
                    tickFormatter={(value) => `${value}%`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "12px",
                    }}
                    formatter={(value: number, name: string) => {
                      const labels: Record<string, string> = {
                        sentiment: "Gesamt",
                        newsSentiment: "News",
                        redditSentiment: "Reddit",
                      };
                      return [`${value}%`, labels[name] || name];
                    }}
                  />
                  {/* Aggregated sentiment line (main) */}
                  <Line
                    type="monotone"
                    dataKey="sentiment"
                    stroke="hsl(var(--sentiment-positive))"
                    strokeWidth={3}
                    dot={false}
                    fill="url(#sentimentGradient)"
                  />
                  {/* News sentiment line (dashed) */}
                  <Line
                    type="monotone"
                    dataKey="newsSentiment"
                    stroke="rgb(59 130 246)" // blue-500
                    strokeWidth={2}
                    strokeDasharray="5 5"
                    dot={false}
                  />
                  {/* Reddit sentiment line (dotted) */}
                  {tool.trendData.some(d => d.redditSentiment !== null) && (
                    <Line
                      type="monotone"
                      dataKey="redditSentiment"
                      stroke="rgb(249 115 22)" // orange-500
                      strokeWidth={2}
                      strokeDasharray="2 2"
                      dot={false}
                      connectNulls={false}
                    />
                  )}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Best For + Rating */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <Card className="rounded-2xl border-border/50">
            <CardHeader>
              <CardTitle className="text-lg font-semibold">{t("bestFor")}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {tool.bestFor.map((tag) => (
                  <Badge 
                    key={tag} 
                    variant="secondary"
                    className="rounded-full px-3 py-1 text-sm"
                  >
                    {tag}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
          <Card className="rounded-2xl border-border/50">
            <CardHeader>
              <CardTitle className="text-lg font-semibold">{t("rating")}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2">
                <span className="text-3xl font-semibold">{tool.rating.toFixed(1)}</span>
                <span className="text-muted-foreground">/ 5.0</span>
              </div>
              <SentimentBar 
                positive={tool.sentiment.positive}
                neutral={tool.sentiment.neutral}
                negative={tool.sentiment.negative}
                className="mt-4"
              />
            </CardContent>
          </Card>
        </div>

        {/* Recent Mentions */}
        <Card className="rounded-2xl border-border/50">
          <CardHeader>
            <CardTitle className="text-lg font-semibold">{t("recentMentions")}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {tool.recentMentions.map((mention) => (
                <div
                  key={mention.id}
                  className={`p-4 rounded-xl border ${mention.source === "Reddit" ? "bg-orange-500/5 border-orange-500/20" : "bg-secondary/50 border-border/30"}`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <Badge
                        variant="outline"
                        className={`rounded-full text-xs ${mention.source === "Reddit" ? "bg-orange-500/10 border-orange-500/30 text-orange-500" : ""}`}
                      >
                        {mention.source === "Reddit" && "👍 "}
                        {mention.source}
                      </Badge>
                      <Badge
                        variant="secondary"
                        className={`rounded-full text-xs ${
                          mention.sentiment === "positive"
                            ? "bg-[hsl(var(--sentiment-positive)/0.1)] text-[hsl(var(--sentiment-positive))]"
                            : mention.sentiment === "negative"
                            ? "bg-[hsl(var(--sentiment-negative)/0.1)] text-[hsl(var(--sentiment-negative))]"
                            : ""
                        }`}
                      >
                        {mention.sentiment}
                      </Badge>
                    </div>
                    <span className="text-xs text-muted-foreground">{mention.date}</span>
                  </div>
                  <p className="text-sm text-foreground">{mention.text}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  );
};

export default Detail;
