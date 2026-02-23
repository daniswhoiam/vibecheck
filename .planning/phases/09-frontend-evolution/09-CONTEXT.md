# Phase 9: Frontend Evolution - Context

**Gathered:** 2026-02-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Surface source-breakdown and aspect-level sentiment data in the existing React frontend. The entity detail page gains a source filter that updates the sentiment chart and a new aspect breakdown section. Existing entity list and sentiment trend views must continue working with no regressions.

Requirements: FRON-01 (source breakdown by data source), FRON-02 (aspect-level sentiment charts per entity).

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion

All design decisions were delegated to Claude with instruction to use UI/UX best practices. Decisions below are based on research from NNGroup, IBM Carbon, Tableau, Highcharts, and analytics tool patterns (Mixpanel, Amplitude, Google Analytics).

### Source filter design
- **Segmented toggle button group** (pill-style), not tabs or dropdown
- 5 options: `[All Sources] [HN] [Reddit] [Discourse] [Dev.to]`
- "All Sources" is the default selected state
- Placed horizontally directly below the entity header, above all data sections
- Active state: filled background (visually distinct from inactive pills)
- Single-select (not multi-select) — primary use case is drill-down into one source
- When selected, filter affects the entire page: trend chart, stats cards, and recent mentions
- Rationale: tabs imply page navigation (anti-pattern for filters); dropdown hides options behind an extra click; 5 options is within the threshold for visible segmented controls

### Aspect sentiment visualization
- **Horizontal diverging bar chart** as the primary visualization
- Bars extend left (negative) and right (positive) from a center neutral axis
- All 7 aspects shown as rows: performance, cost, reliability, UX, speed, code quality, context window
- Sorted by score descending (strongest aspects at top)
- Color: two-color scheme — teal/green for positive side, amber/red for negative side
- Each row shows the numeric score and a trend arrow (up/down/stable) if historical data exists
- Section heading: "Sentiment by Aspect"
- **No radar chart** as default — radar requires interpreting area and angle (high cognitive load), and 7 axes crowd label readability. Horizontal bars use length, the strongest pre-attentive attribute humans process
- If comparison view is ever needed (future phase), radar could be added as an optional toggle

### Page layout
- **Vertical scrollable sections** — no tabs, no accordion
- Layout order top-to-bottom:
  1. Entity header (name, logo, company, trend badge)
  2. Source filter (segmented toggle)
  3. Overview stats cards (sentiment %, mentions count)
  4. Sentiment trend chart (existing LineChart, now source-filterable)
  5. Sentiment by Aspect (new horizontal bar chart section)
  6. Recent mentions (existing, now source-filterable)
- Each section gets a clear heading with subtle divider
- Rationale: tabs hide data behind clicks and prevent simultaneous visibility; accordion forces clicks to reveal content; vertical scroll lets analysts synthesize information across sections together
- If page becomes long, a sticky in-page nav (jump links) can be added — but defer unless needed

### Empty states and loading
- **Skeleton screens with shimmer** for loading (not spinners), matching the structural layout of each section
- Shimmer: left-to-right, 1.5s loop
- Never show "No data" while data is still fetching — sequence must be: skeleton → real content (or real empty state)
- When switching source filter: charts immediately skeleton while new data fetches
- **Genuine empty state** (source has no data): inline per-section message with 3 elements:
  1. Clear status: "No [Source] data indexed yet"
  2. Context: brief explanation why
  3. Action: "View All Sources" button to clear the filter
- **Partial aspect data**: render available bars normally, show "—" or "Insufficient data" inline for missing aspect rows — never blank the entire chart
- Distinguish between "no data for this filter" (show clear-filter CTA) and "no data at all" (show general explanation)

</decisions>

<specifics>
## Specific Ideas

- Current detail page already has news/reddit sentiment lines on the trend chart — the source filter should replace this dual-line approach with a single filtered line (or "All" showing the aggregate)
- The existing MiniSparkline component on tool cards should continue showing aggregate data regardless of any source filter on the detail page
- Recharts is already in the project (v2.15.4) — use it for the aspect bar chart too for consistency
- The existing `entityTransformer.ts` maps backend → frontend types; extend this pattern for aspect data rather than creating a separate transform layer
- The backend already has `GET /entities/{id}/aspects` endpoint (from Phase 8) with `window` (7d/30d/90d) and `source` query params — wire directly to this

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 09-frontend-evolution*
*Context gathered: 2026-02-23*
