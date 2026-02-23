# Phase 9: Frontend Evolution - Research

**Researched:** 2026-02-23
**Domain:** React frontend UI/UX components with data visualization
**Confidence:** HIGH

## Summary

Phase 9 adds source filtering and aspect-level sentiment visualization to the existing React frontend. The implementation builds on a mature tech stack: React 18.3, TypeScript 5.8, shadcn/ui Radix components, Recharts 2.15.4 for charting, and Tailwind CSS 3.4. The backend provides two ready-to-use API endpoints (`GET /entities/{id}/sentiment` with source_breakdown, `GET /entities/{id}/aspects`), eliminating the need for new backend work.

The frontend already has the patterns and dependencies in place: entity detail page exists, Recharts is integrated, React Query handles data fetching, and entityTransformer handles backend→frontend transformation. The phase is primarily about adding two new UI sections (source filter segmented toggle and aspect sentiment chart) and wiring them to existing backend data.

**Primary recommendation:** Use Recharts BarChart (horizontal layout) for aspects visualization. Implement source filter as a segmented toggle button group using @radix-ui/react-toggle-group (already installed). Extend Detail.tsx page with new sections and modify api.ts to fetch aspect data.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions

**Source filter design:**
- Segmented toggle button group (pill-style), not tabs or dropdown
- 5 options: [All Sources] [HN] [Reddit] [Discourse] [Dev.to]
- "All Sources" is the default selected state
- Placed horizontally directly below entity header, above all data sections
- Active state: filled background (visually distinct from inactive pills)
- Single-select (not multi-select) — primary use case is drill-down into one source
- When selected, filter affects the entire page: trend chart, stats cards, and recent mentions
- Rationale: tabs imply page navigation (anti-pattern for filters); dropdown hides options; 5 options is within threshold for visible segmented controls

**Aspect sentiment visualization:**
- Horizontal diverging bar chart as primary visualization
- Bars extend left (negative) and right (positive) from center neutral axis
- All 7 aspects shown as rows: performance, cost, reliability, UX, speed, code quality, context window
- Sorted by score descending (strongest aspects at top)
- Color: two-color scheme — teal/green for positive side, amber/red for negative side
- Each row shows numeric score and trend arrow (up/down/stable) if historical data exists
- Section heading: "Sentiment by Aspect"
- **No radar chart** as default — radar requires interpreting area and angle (high cognitive load), 7 axes crowd label readability. Horizontal bars use length, strongest pre-attentive attribute
- If comparison view ever needed (future phase), radar could be added as optional toggle

**Page layout:**
- Vertical scrollable sections — no tabs, no accordion
- Layout order top-to-bottom:
  1. Entity header (name, logo, company, trend badge)
  2. Source filter (segmented toggle)
  3. Overview stats cards (sentiment %, mentions count)
  4. Sentiment trend chart (existing LineChart, now source-filterable)
  5. Sentiment by Aspect (new horizontal bar chart section)
  6. Recent mentions (existing, now source-filterable)
- Each section gets clear heading with subtle divider
- Rationale: tabs hide data behind clicks and prevent simultaneous visibility; accordion forces clicks to reveal content; vertical scroll lets analysts synthesize information across sections
- If page becomes long, sticky in-page nav (jump links) can be added — but defer unless needed

**Empty states and loading:**
- Skeleton screens with shimmer for loading (not spinners), matching structural layout of each section
- Shimmer: left-to-right, 1.5s loop
- Never show "No data" while data is still fetching — sequence: skeleton → real content (or real empty state)
- When switching source filter: charts immediately skeleton while new data fetches
- Genuine empty state (source has no data): inline per-section message with 3 elements:
  1. Clear status: "No [Source] data indexed yet"
  2. Context: brief explanation why
  3. Action: "View All Sources" button to clear the filter
- Partial aspect data: render available bars normally, show "—" or "Insufficient data" inline for missing aspect rows — never blank entire chart
- Distinguish between "no data for this filter" (show clear-filter CTA) and "no data at all" (show general explanation)

### Claude's Discretion

None — all design decisions were delegated and locked.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FRON-01 | User can see sentiment breakdown by data source (HN, Reddit, Discourse, Dev.to) on entity detail page with filter control | Backend already provides `GET /entities/{id}/sentiment` with `source_breakdown` JSON field; SentimentPointSchema includes `{"hn": {"mean": 0.4, "count": 12}, "reddit": {...}}` per data point. Frontend needs segmented toggle filter + filtered LineChart rendering. |
| FRON-02 | User can view aspect-level sentiment chart per entity showing scores across 7 defined aspects | Backend provides `GET /entities/{id}/aspects?window=7d\|30d\|90d&source=...` endpoint returning AspectSentimentResponse with dict of 7 aspects (performance, cost, reliability, ux, speed, code_quality, context_window). Each aspect has `mean` [-1.0, 1.0] and `count`. Frontend needs horizontal bar chart component + aspect data fetching. |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | 18.3.1 | UI framework | Latest stable (18.x); proven for dashboards and complex interactive UIs |
| TypeScript | 5.8.3 | Type safety | Critical for data transformations; catches schema mismatches at build time |
| Recharts | 2.15.4 | Data visualization | Already in project; composable chart system handles bar/line/composite charts elegantly |
| @radix-ui/react-toggle-group | 1.1.10 | Toggle button groups | Installed, accessible, supports single-select segmented patterns out-of-box |
| Tailwind CSS | 3.4.17 | Styling | Already project standard; highly configurable for diverging bar color schemes |
| React Query (@tanstack/react-query) | 5.83.0 | Data fetching & caching | Already used project-wide; handles async loading states and pagination |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| shadcn/ui | (component library) | Pre-built UI components | Card, Badge, Skeleton, Separator — used throughout existing frontend |
| react-router-dom | 6.30.1 | Routing | Already in project; Detail.tsx uses useParams and navigation |
| lucide-react | 0.462.0 | Icon library | Trend arrows, source badges, UI icons — already project standard |
| date-fns | 3.6.0 | Date utilities | Format timestamps in charts and empty state messages |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Recharts BarChart | Visx/Victory/Chart.js | Recharts already installed, team familiar, smaller learning curve, easier responsive sizing |
| @radix-ui/react-toggle-group | Custom toggle component | Radix Toggle Group has accessibility built-in (keyboard nav, ARIA roles); custom adds testing burden |
| Tailwind for styling | Styled-components/CSS modules | Tailwind is project standard; consistency and faster development |
| React Query for aspects fetch | Direct fetch() or SWR | React Query already used for entity list/detail; reusing reduces mental overhead and deduplicates caching logic |

**Installation:** No new packages needed — all standard stack libraries already in package.json.

## Architecture Patterns

### Recommended Project Structure

The existing structure is sound; Phase 9 adds files/sections:

```
src/
├── components/
│   ├── SourceFilterToggle.tsx          [NEW] Segmented toggle component
│   ├── AspectSentimentChart.tsx        [NEW] Horizontal bar chart component
│   ├── SentimentBar.tsx                [EXISTING] Already used for sentiment distribution
│   ├── TrendIndicator.tsx              [EXISTING] Trend direction arrow
│   └── ui/                             [EXISTING] shadcn/ui primitives
├── hooks/
│   ├── useTools.ts                     [EXISTING] Entity list/detail queries
│   ├── useSentimentTimeSeries.ts       [EXISTING] Sentiment data hook
│   └── useAspectSentiment.ts           [NEW] Aspects data hook
├── pages/
│   └── Detail.tsx                      [MODIFY] Add source filter + aspects section
├── services/
│   ├── api.ts                          [MODIFY] Add fetchAspectSentiment function
│   ├── entityTransformer.ts            [EXISTING] Backend → frontend transformation
│   └── aspectTransformer.ts            [NEW] Aspect data transformation (if needed)
└── types/
    └── api.ts                          [MODIFY] Add AspectData types
```

### Pattern 1: Data Fetching with React Query

**What:** Encapsulate backend queries in custom hooks using @tanstack/react-query

**When to use:** Async data dependencies in components (entities, sentiments, aspects)

**Example:**

```typescript
// src/hooks/useAspectSentiment.ts
import { useQuery } from "@tanstack/react-query";
import { fetchAspectSentiment } from "@/services/api";

export function useAspectSentiment(
  entityId: string | undefined,
  window: "7d" | "30d" | "90d" = "7d",
  source?: string
) {
  return useQuery({
    queryKey: ["aspects", entityId, window, source],
    queryFn: () => fetchAspectSentiment(entityId!, window, source),
    enabled: !!entityId,
  });
}
```

Source: Project pattern established in useTools.ts, useSentimentTimeSeries.ts

### Pattern 2: Backend → Frontend Transformation

**What:** Centralize API response mapping in dedicated transformer modules

**When to use:** Complex schema conversions, unit-testable data reshaping

**Example:**

```typescript
// src/services/api.ts - ADD
export async function fetchAspectSentiment(
  entityId: string,
  window: "7d" | "30d" | "90d" = "7d",
  source?: string
): Promise<AspectSentimentData> {
  const params = new URLSearchParams({ window });
  if (source) params.append("source", source);

  const response = await fetch(
    `${BASE_URL}/entities/${entityId}/aspects?${params}`
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch aspects: ${response.status}`);
  }

  const data = await response.json();
  return toAspectData(data); // Transform to frontend types
}
```

Source: Project pattern in entityTransformer.ts, api.ts

### Pattern 3: Controlled Filter State in Page Component

**What:** Single page-level state for source filter; drill down to child components

**When to use:** Filter affects multiple sections (chart, stats, mentions) on same page

**Example:**

```typescript
// src/pages/Detail.tsx - MODIFY
const [selectedSource, setSelectedSource] = useState<string | null>(null);

// Pass to child components
<SentimentTrendChart
  data={selectedSource ? filterData(trendData, selectedSource) : trendData}
/>
<AspectSentimentChart
  entityId={id}
  source={selectedSource}
/>
```

Source: Established pattern in Detail.tsx (already uses useState for local state)

### Anti-Patterns to Avoid
- **Prop drilling through many layers:** If filter state needed by 3+ components, consider Context API. Current 2 components (trend chart + aspects chart) allow props.
- **Separate source filter hook:** Don't use useQuery for filter state — it's UI state (localStorage-like), not backend data. Use useState.
- **Recharts responsive sizing issues:** Always wrap charts in `<div style={{width: '100%', height: '...'}}>` and use `<ResponsiveContainer>`. Never use fixed pixel widths.
- **Aspect data transformation at render:** Transform once in hook/service layer, not inside JSX. Prevents recalculation on every render.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Segmented toggle button group | Custom button components with onClick handlers | @radix-ui/react-toggle-group | Radix handles keyboard navigation (arrow keys), ARIA roles (role="group", aria-pressed), focus management. Custom risks accessibility gaps. |
| Horizontal bar chart with diverging positive/negative colors | SVG rect elements + manual positioning | Recharts BarChart with custom shapes | Recharts handles axis labels, tooltips, legend, responsive sizing, animation. Manual SVG requires ~200 lines for a robust chart. |
| Skeleton screens with shimmer animation | CSS keyframes from scratch | shadcn/ui Skeleton + Tailwind animate | Project already has shadcn Skeleton; animation plugin (tailwindcss-animate) installed. One line: `<Skeleton className="animate-pulse" />`. |
| Empty state messaging | Static text | Conditional render + structured UI (status + context + action) | UX decision locked in CONTEXT.md: 3-part empty state (status, context, action). Ensure all three elements present per design. |
| Time window selector (7d/30d/90d) for aspects | Custom dropdown | Existing Select component from shadcn/ui | Already installed, consistent with entity selector in Detail.tsx line 126-140. Reuse pattern. |
| Aspect name display + formatting | Hard-code strings in component | Transform layer + constant mapping | VALID_ASPECTS from backend is authoritative. Map to readable labels ("code_quality" → "Code Quality") in transformer, not in component. |

**Key insight:** This phase is mostly wiring together existing patterns (React Query, Recharts, Radix) rather than inventing new ones. The complexity is in state management (filter affects multiple sections) and data transformation (API response → chart-ready format), not component building.

## Common Pitfalls

### Pitfall 1: Filter State Doesn't Persist Across Re-renders

**What goes wrong:** User selects source filter, chart updates, then user navigates away and back to detail page — filter selection is lost (reset to "All Sources").

**Why it happens:** Filter state in Detail.tsx is useState, which resets on component remount. No localStorage or URL params.

**How to avoid:**
- Option A (simple): Store in URL query param `?source=reddit`. Read with `new URLSearchParams(location.search).get('source')` on mount.
- Option B (explicit): localStorage if user expects filter to persist across sessions.
- Decision: CONTEXT.md silent on persistence. Recommend Option A (URL) — more shareable, aligns with analytics workflows ("send colleague this URL with your filter applied").

**Warning signs:** After selecting filter, reload page (Cmd+R) → filter disappears.

### Pitfall 2: Aspect Chart Blank When No Data for Selected Source

**What goes wrong:** User selects "Discourse" source; backend returns 200 with all aspects having `count=0, mean=null`. Chart renders nothing (no bars visible).

**Why it happens:** Recharts BarChart doesn't render a bar if dataValue is null. Empty state message gets buried below blank chart area.

**How to avoid:**
- Fetch aspects with selected source.
- Check if **all** aspects have count=0 (genuine empty state).
- If all zero-count: render empty state instead of chart.
- If **some** aspects have data: render chart normally, show "—" or "Insufficient data" label for zero-count aspects.
- CONTEXT.md decision (line 65-66): "Partial aspect data: render available bars normally, show inline 'Insufficient data' for missing rows — never blank the entire chart."

**Warning signs:** Scroll past empty chart area searching for content; aspect names visible but no bars.

### Pitfall 3: Source Filter Doesn't Update All Sections Simultaneously

**What goes wrong:** User selects "Reddit" source. Trend chart updates but "Recent Mentions" section still shows all sources. Confusing.

**Why it happens:** Filter state not threaded through to Recent Mentions component, or each section fetches independently and misses the filter prop.

**How to avoid:**
- Source filter state lives in Detail.tsx parent.
- Pass `source` prop to **all** sections that display filtered data: TrendChart, MentionsSection, AspectChart.
- Each child component uses prop to fetch/filter its own data, or parent pre-filters data before passing.
- Recommended: Parent filters data; children display it (simpler, one source of truth).

**Warning signs:** Toggle filter, scroll down, notice one section hasn't changed while others have.

### Pitfall 4: SourceFilterToggle Keyboard Navigation Broken

**What goes wrong:** User presses Tab to navigate to toggle group, can't use arrow keys to select different sources. Fails accessibility.

**Why it happens:** Custom toggle implementation or incorrect Radix usage (e.g., missed `orientation="horizontal"` prop, tabIndex management).

**How to avoid:**
- Use @radix-ui/react-toggle-group directly (don't wrap in custom component unless necessary).
- Set `type="single"` (single-select), `orientation="horizontal"`, `defaultValue="all"`.
- Test: Tab to toggle group → use arrow keys → Tab out.
- Radix handles ARIA attributes automatically if props correct.

**Warning signs:** Keyboard-only user (tab-based navigation) can't change source selection.

## Code Examples

Verified patterns from official sources:

### Source Filter Toggle Component

```typescript
// src/components/SourceFilterToggle.tsx
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
// Source: @radix-ui/react-toggle-group (installed, shadcn/ui wrapper)

interface SourceFilterToggleProps {
  value: string | null;
  onChange: (value: string) => void;
}

export function SourceFilterToggle({ value, onChange }: SourceFilterToggleProps) {
  const sources = [
    { id: "all", label: "All Sources" },
    { id: "hn", label: "HN" },
    { id: "reddit", label: "Reddit" },
    { id: "discourse", label: "Discourse" },
    { id: "devto", label: "Dev.to" },
  ];

  return (
    <div className="mb-6">
      <ToggleGroup
        type="single"
        value={value || "all"}
        onValueChange={onChange}
        className="gap-2"
      >
        {sources.map((source) => (
          <ToggleGroupItem
            key={source.id}
            value={source.id}
            className="px-4 py-2 rounded-full font-medium"
          >
            {source.label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  );
}
```

Source: Radix UI ToggleGroup (https://www.radix-ui.com/docs/primitives/components/toggle-group)

### Aspect Sentiment Chart (Horizontal Bar)

```typescript
// src/components/AspectSentimentChart.tsx
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, Cell, ResponsiveContainer,
} from "recharts";

interface AspectChartData {
  aspect: string;
  score: number; // [-1, 1], negative left, positive right
  count: number;
}

export function AspectSentimentChart({ data }: { data: AspectChartData[] }) {
  // Sort by score descending (strongest at top)
  const sorted = [...data].sort((a, b) => (b.score || 0) - (a.score || 0));

  const getBarColor = (score: number | null) => {
    if (score === null) return "#e5e7eb"; // gray for no data
    if (score > 0) return "rgb(20, 184, 166)"; // teal for positive
    if (score < 0) return "rgb(245, 158, 11)"; // amber for negative
    return "#e5e7eb"; // gray for neutral
  };

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart
        data={sorted}
        layout="vertical"
        margin={{ top: 0, right: 30, left: 120, bottom: 0 }}
      >
        <XAxis type="number" domain={[-1, 1]} />
        <YAxis type="category" dataKey="aspect" width={110} />
        <Tooltip
          contentStyle={{
            backgroundColor: "hsl(var(--card))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "8px",
          }}
          formatter={(value: number) => [value.toFixed(2), "Score"]}
        />
        <Bar dataKey="score" fill="#8884d8" radius={4}>
          {sorted.map((entry, idx) => (
            <Cell key={`cell-${idx}`} fill={getBarColor(entry.score)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
```

Source: Recharts BarChart horizontal layout (https://recharts.org/en-US/examples/SimpleBarChart)

### Fetching Aspect Data

```typescript
// src/services/api.ts - ADD
export async function fetchAspectSentiment(
  entityId: string,
  window: "7d" | "30d" | "90d" = "7d",
  source?: string
): Promise<AspectSentimentResponse> {
  try {
    const params = new URLSearchParams({ window });
    if (source && source !== "all") params.append("source", source);

    const response = await fetch(`${BASE_URL}/entities/${entityId}/aspects?${params}`);

    if (!response.ok) {
      throw new Error(`Failed to fetch aspects: ${response.status}`);
    }

    const data: AspectSentimentResponse = await response.json();
    return data;
  } catch (error) {
    console.error("Error fetching aspect data:", error);
    throw error;
  }
}
```

Source: Established pattern in api.ts, fetch with query params

### React Query Hook for Aspects

```typescript
// src/hooks/useAspectSentiment.ts - NEW
import { useQuery } from "@tanstack/react-query";
import { fetchAspectSentiment } from "@/services/api";

export function useAspectSentiment(
  entityId: string | undefined,
  window: "7d" | "30d" | "90d" = "7d",
  source?: string
) {
  return useQuery({
    queryKey: ["aspects", entityId, window, source],
    queryFn: () => fetchAspectSentiment(entityId!, window, source),
    enabled: !!entityId,
  });
}
```

Source: Project pattern (useTools.ts, line 4-8)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single aggregate sentiment score | Per-source sentiment breakdown + aspect details | Phase 7-8 | Frontend now displays source-specific trends, enabling drill-down analysis. Requires filtering UI. |
| Manual sentiment classification (v1.0) | Tier 1 RoBERTa + Tier 2 LLM aspect extraction | Phase 7-8 (backend) | Aspect data now available for fine-grained visualization. Frontend must surface it. |
| v1.0 LineChart showing only aggregate | v2.0 LineChart with source filter | Phase 9 | User can isolate individual source trends. Improves diagnosis of sentiment anomalies. |
| No aspect visualization | Horizontal bar chart (diverging, sorted) | Phase 9 | New section on detail page. Answers "Which aspects are strongest/weakest?" |

**Deprecated/outdated:**
- v1.0 AskNews API integration: Removed Phase 6 (replaced by free data sources). No frontend impact.
- Tiered tabs for source views (old design anti-pattern): Discarded in CONTEXT.md. Segmented toggle chosen instead (aligns with current UX trends).

## Open Questions

1. **Time window selector for aspects**
   - What we know: Backend supports 7d/30d/90d windows. CONTEXT.md silent on user control.
   - What's unclear: Should detail page let user pick window, or default to 7d? Should it sync with sentiment chart window?
   - Recommendation: Start with fixed 7d (simplest). Add selector dropdown if Phase 9 feedback requests other windows. Placeholder for future.

2. **Aspect trend arrows (historical comparison)**
   - What we know: CONTEXT.md mentions "trend arrow (up/down/stable) if historical data exists."
   - What's unclear: How to fetch historical aspect data? Backend supports window query but not time-series per aspect yet.
   - Recommendation: Wave 0 implementation skips trend arrows (render "—" placeholder). Add backend endpoint for historical aspects in future phase if needed.

3. **Source-filtered mentions section**
   - What we know: Recent Mentions component exists, currently shows all sources mixed.
   - What's unclear: How to fetch mentions for selected source? Backend sentiment endpoint has source_breakdown, but no separate mentions endpoint yet.
   - Recommendation: For now, filter existing recentMentions array client-side by source. Add backend `/entities/{id}/mentions?source=...` endpoint later if filtering insufficient.

## Validation Architecture

> Nyquist validation enabled: workflow.nyquist_validation = true in config.json

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Vitest 3.2.4 + React Testing Library 16.0.0 |
| Config file | vite.config.ts (implicit; uses vitest plugin) |
| Quick run command | `npm test` (runs all .test.tsx files once) |
| Full suite command | `npm test` (equivalent; vitest no watch by default) |
| Estimated runtime | ~15-20 seconds (existing tests + new phase tests) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FRON-01 | Source filter appears on detail page with 5 options; selecting option updates sentiment chart | Integration | `npm test -- src/pages/Detail.test.tsx` | ❌ Wave 0 gap |
| FRON-01 | Sentiment trend chart filters to selected source (or shows aggregate if "All") | Unit | `npm test -- src/components/SentimentTrendChart.test.tsx` | ❌ Wave 0 gap (existing component, needs source-filtering test) |
| FRON-02 | Aspect sentiment chart renders with all 7 aspects sorted by score | Unit | `npm test -- src/components/AspectSentimentChart.test.tsx` | ❌ Wave 0 gap |
| FRON-02 | Aspect data fetches from `GET /entities/{id}/aspects` endpoint | Integration | `npm test -- src/hooks/useAspectSentiment.test.ts` | ❌ Wave 0 gap |
| FRON-02 | Empty state displays when selected source has no aspect data | Unit | `npm test -- src/components/AspectSentimentChart.test.tsx` | ❌ Wave 0 gap |

### Nyquist Sampling Rate
- **Minimum sample interval:** After every committed task → run: `npm test`
- **Full suite trigger:** Before merging final task of Wave 1 (all sections implemented)
- **Phase-complete gate:** Full suite green before `/gsd:verify-work` runs
- **Estimated feedback latency per task:** ~15 seconds

### Wave 0 Gaps (must be created before implementation)
- [ ] `src/pages/Detail.test.tsx` — Integration test for source filter appearance and chart interaction
- [ ] `src/components/AspectSentimentChart.test.tsx` — Unit test for horizontal bar chart rendering with 7 aspects, sort order, empty state
- [ ] `src/components/SourceFilterToggle.test.tsx` — Unit test for toggle button keyboard nav (arrow keys), single-select behavior
- [ ] `src/hooks/useAspectSentiment.test.ts` — Integration test for React Query hook mocking backend fetch, error handling, enabled state
- [ ] `src/test/mocks.ts` (extend existing) — Mock AspectSentimentResponse and endpoint. Establish queryClient fixture for React Query testing.

*(Existing test infrastructure covers component rendering, hooks, and API interaction patterns. Wave 0 adds Phase 9-specific test files.)*

## Sources

### Primary (HIGH confidence)
- **Recharts 2.15.4 docs** (https://recharts.org/) - BarChart horizontal layout, responsive container, tooltip customization
- **@radix-ui/react-toggle-group docs** (https://www.radix-ui.com/docs/primitives/components/toggle-group) - Single-select segmented control, keyboard navigation, ARIA roles
- **React Query @tanstack/react-query 5.83.0 docs** (https://tanstack.com/query/v5) - useQuery hook, queryKey structure, error handling
- **React 18 docs** (https://react.dev/) - useState, useEffect, component composition
- **Existing project code** - Detail.tsx, entityTransformer.ts, useTools.ts established patterns confirmed in codebase

### Secondary (MEDIUM confidence)
- **Backend Phase 8 documentation** (.planning/phases/08-tier-2-llm-aspect-extraction/) - AspectSentimentResponse schema and GET /entities/{id}/aspects endpoint confirmed from reading backend/api/routes/entities.py
- **shadcn/ui component library** (https://ui.shadcn.com/) - Skeleton, Card, Badge, Select components — already integrated in project
- **Tailwind CSS 3.4 docs** (https://tailwindcss.com/) - Animation utilities, color scheme customization

### Tertiary (LOW confidence)
- None — all critical claims verified with codebase inspection or official documentation

## Metadata

**Confidence breakdown:**
- **Standard stack:** HIGH - All libraries confirmed in package.json, existing components verified in codebase
- **Architecture:** HIGH - Existing patterns (React Query, Recharts, transformation layer) proven in Detail.tsx and related files
- **Pitfalls:** MEDIUM - Common issues inferred from standard React/chart visualization patterns; validated against CONTEXT.md UX decisions
- **Testing:** MEDIUM - Vitest config inferred from package.json scripts; wave 0 gaps identified but test patterns established in project

**Research date:** 2026-02-23
**Valid until:** 2026-03-23 (30 days; stable libs, no breaking changes expected)

## Notes

1. **No backend work required** — All endpoints (sentiment with source_breakdown, aspects) already implemented and tested in Phase 8.

2. **Aspect names in UI** — Backend uses snake_case (code_quality, context_window). Transform to title case in frontend ("Code Quality", "Context Window") in transformer layer, not component.

3. **Color scheme for diverging bar** — CONTEXT.md specifies teal/green (positive) + amber/red (negative). Use Tailwind utilities or inline styles; exact hex values flexible but keep high contrast for readability.

4. **Skeleton loading** — Project already has shadcn Skeleton component. Use with Tailwind animate-pulse for shimmer effect (1.5s loop per CONTEXT.md).

5. **Empty state structure** — User decision locked: status (clear title) + context (explanation) + action (clear filter button). Enforce all three in implementation.

6. **No comparison view in Phase 9** — CONTEXT.md defers side-by-side comparison and radar chart to future phases. Keep implementation focused on single-entity drill-down.
