import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import type { AspectSentimentData } from "@/types/api";

const ASPECT_LABELS: Record<string, string> = {
  performance: "Performance",
  cost: "Cost",
  reliability: "Reliability",
  ux: "UX",
  speed: "Speed",
  code_quality: "Code Quality",
  context_window: "Context Window",
};

interface AspectSentimentChartProps {
  data: AspectSentimentData["aspects"];
  source?: string;
  onClearFilter?: () => void;
}

function getBarColor(score: number | null): string {
  if (score === null) return "#e5e7eb";
  if (score > 0) return "rgb(20, 184, 166)"; // teal for positive
  if (score < 0) return "rgb(245, 158, 11)"; // amber for negative
  return "#e5e7eb"; // neutral
}

export function AspectSentimentChart({
  data,
  source,
  onClearFilter,
}: AspectSentimentChartProps) {
  // Check for genuine empty state (all aspects have count=0)
  const allEmpty = Object.values(data).every((v) => v.count === 0);

  if (allEmpty) {
    const sourceLabel =
      source && source !== "all"
        ? source.charAt(0).toUpperCase() + source.slice(1)
        : "this source";
    return (
      <div className="flex flex-col items-center justify-center py-8 gap-3 text-center">
        <p className="text-sm font-medium text-muted-foreground">
          No {sourceLabel} data indexed yet
        </p>
        <p className="text-xs text-muted-foreground max-w-xs">
          Aspect sentiment data becomes available after the LLM extraction
          pipeline processes posts from this source.
        </p>
        {onClearFilter && (
          <button
            onClick={onClearFilter}
            className="text-xs text-primary underline underline-offset-2 hover:no-underline"
          >
            View All Sources
          </button>
        )}
      </div>
    );
  }

  // Build chart data rows: sorted by score descending, null scores last
  const chartData = Object.entries(data)
    .map(([key, val]) => ({
      aspect: ASPECT_LABELS[key] ?? key,
      score: val.count > 0 ? val.mean : null,
      count: val.count,
      hasData: val.count > 0,
    }))
    .sort((a, b) => {
      if (a.score === null && b.score === null) return 0;
      if (a.score === null) return 1; // nulls last
      if (b.score === null) return -1;
      return b.score - a.score;
    });

  return (
    <div>
      {/* Accessibility/test fallback: render aspect labels and insufficient data markers in DOM.
          Recharts custom ticks do not render in jsdom; these visually-hidden spans provide
          testable handles for screen readers and unit tests. */}
      <div
        style={{
          position: "absolute",
          width: "1px",
          height: "1px",
          padding: 0,
          margin: "-1px",
          overflow: "hidden",
          clip: "rect(0,0,0,0)",
          whiteSpace: "nowrap",
          border: 0,
        }}
      >
        {chartData.map((entry) => (
          <span key={entry.aspect} data-aspect-label={entry.aspect}>
            {entry.aspect}
          </span>
        ))}
        {chartData
          .filter((entry) => !entry.hasData)
          .map((entry) => (
            <span key={`insufficient-${entry.aspect}`}>
              Insufficient data
            </span>
          ))}
      </div>

      <div style={{ width: "100%", height: `${chartData.length * 48 + 40}px` }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 0, right: 40, left: 130, bottom: 0 }}
          >
            <XAxis
              type="number"
              domain={[-1, 1]}
              tickFormatter={(v) => v.toFixed(1)}
              stroke="hsl(var(--muted-foreground))"
              fontSize={11}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              type="category"
              dataKey="aspect"
              width={120}
              stroke="hsl(var(--muted-foreground))"
              fontSize={12}
              axisLine={false}
              tickLine={false}
              tick={(props) => {
                const { x, y, payload } = props;
                const entry = chartData.find((d) => d.aspect === payload.value);
                return (
                  <g transform={`translate(${x},${y})`}>
                    <text
                      x={-4}
                      y={0}
                      dy={4}
                      textAnchor="end"
                      fill="hsl(var(--foreground))"
                      fontSize={12}
                      data-aspect-label={payload.value}
                    >
                      {payload.value}
                    </text>
                    {entry && !entry.hasData && (
                      <text
                        x={10}
                        y={0}
                        dy={4}
                        textAnchor="start"
                        fill="hsl(var(--muted-foreground))"
                        fontSize={10}
                      >
                        — Insufficient data
                      </text>
                    )}
                  </g>
                );
              }}
            />
            <ReferenceLine
              x={0}
              stroke="hsl(var(--border))"
              strokeWidth={1.5}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "hsl(var(--card))",
                border: "1px solid hsl(var(--border))",
                borderRadius: "8px",
                fontSize: "12px",
              }}
              formatter={(value: number | null) =>
                value !== null
                  ? [`${value.toFixed(2)}`, "Score"]
                  : ["No data", ""]
              }
            />
            <Bar dataKey="score" radius={[0, 4, 4, 0]}>
              {chartData.map((entry, idx) => (
                <Cell key={`cell-${idx}`} fill={getBarColor(entry.score)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
