# Quick Task 003: Frontend-Backend Integration - Phase 2 (Enhanced Features)

**Created:** 2026-02-05
**Status:** Planning Complete
**Type:** Implementation
**Dependencies:** Quick Task 002 (Phase 1 - Critical Path)

## Description

Implement Phase 2 of the frontend-backend integration to add sentiment time-series features, trend calculations, and populate sparkline data with real data from the backend.

## Context

From Quick Task 001 and 002:
- Backend provides `/entities/{id}/sentiment` endpoint with time-series data
- Frontend currently uses placeholder sparkline data (all zeros)
- Trend indicators (up/down/stable) are hardcoded to "stable"
- Phase 1 complete: Basic data flowing, latest_sentiment working

## Tasks

### Task 1: Create Sentiment Time-Series Hook

**Objective:** Create React Query hook for fetching sentiment time-series data.

**Files:**
- `src/hooks/useSentimentTimeSeries.ts` (NEW)

**Actions:**
1. Create `useSentimentTimeSeries(entityId: string, period?: 'hourly' | 'daily')` hook
2. Fetch from `/api/entities/{id}/sentiment?period={period}`
3. Handle pagination (next_cursor, has_more)
4. Return { data, isLoading, error, fetchMore }
5. Configure React Query caching (5-minute stale time)

**Acceptance Criteria:**
- Hook fetches time-series data successfully
- Handles loading and error states
- Caches results to avoid excessive API calls
- Supports both hourly and daily periods

**Estimated Time:** 15 minutes

---

### Task 2: Implement Trend Calculations

**Objective:** Calculate 7-day trend and trend direction from time-series data.

**Files:**
- `src/services/trendCalculator.ts` (NEW)

**Actions:**
1. Create `calculate7DayTrend(timeseries: SentimentPoint[])` function
   - Compare average sentiment from last 7 data points with previous 7
   - Return trend percentage (e.g., 12.5% increase)
2. Create `getTrendDirection(trendPercent: number)` function
   - Return "up" if > 5%, "down" if < -5%, else "stable"
3. Create `generateSparklineData(timeseries: SentimentPoint[], points: number)` function
   - Extract last N sentiment_mean values
   - Handle null values (use 0 or previous value)
4. Export all functions

**Acceptance Criteria:**
- 7-day trend calculated from actual time-series data
- Trend direction correctly determined (up/down/stable)
- Sparkline data extracted from time-series points
- Graceful handling of null/missing values

**Estimated Time:** 20 minutes

---

### Task 3: Integrate Time-Series Data in Entity Transformer

**Objective:** Update transformer to fetch and use time-series data for Tool/ToolDetail.

**Files:**
- `src/services/entityTransformer.ts`

**Actions:**
1. Import trend calculation functions
2. Update `toTool()` to accept optional time-series data
   - Calculate sparklineData from time-series if provided
   - Set trend and trendPercent7d using trend calculator
3. Update `toToolDetail()` to accept time-series data
   - Populate trendData array from time-series
   - Calculate and set all trend-related fields
4. Keep placeholders as fallback when no time-series data

**Acceptance Criteria:**
- Transformer uses real time-series data when available
- Falls back to placeholders when data missing
- Sparkline data populated from actual sentiment values
- Trend indicators calculated from real data

**Estimated Time:** 15 minutes

---

### Task 4: Update API Service to Fetch Time-Series

**Objective:** Fetch time-series data when loading entities for rich display.

**Files:**
- `src/services/api.ts`
- `src/hooks/useTools.ts` (if exists, or create)
- `src/hooks/useToolDetail.ts` (if exists, or create)

**Actions:**
1. Update `fetchTools()` to optionally include time-series
   - Add parameter `includeTimeseries?: boolean`
   - If true, fetch time-series for each entity
   - Pass data to transformer
2. Update `fetchToolDetail()` to always fetch time-series
   - Call `/api/entities/{id}/sentiment` after getting entity
   - Merge entity + time-series data
   - Pass to transformer
3. Create/update React Query hooks to use enhanced API functions

**Acceptance Criteria:**
- Entity detail fetches associated time-series data
- List view optionally fetches time-series (for sparklines)
- Data merged correctly before transformation
- Error handling for failed time-series fetches

**Estimated Time:** 20 minutes

---

### Task 5: Update Frontend Components to Display Trends

**Objective:** Ensure UI components display the new trend data correctly.

**Files:**
- `src/components/` (cards, charts, trend indicators)
- Check existing components for trend display

**Actions:**
1. Review existing UI components for trend/sparkline usage
2. Verify components accept and display the new data:
   - sparklineData array rendered as sparkline chart
   - trend ("up"/"down"/"stable") shown with appropriate icon/color
   - trendPercent7d displayed as percentage
3. Update any hardcoded values to use real data
4. Add loading states for time-series data

**Acceptance Criteria:**
- Sparkline charts show real sentiment history
- Trend indicators (arrows, colors) reflect actual direction
- Trend percentages display correctly
- Loading states during data fetch

**Estimated Time:** 15 minutes

---

### Task 6: Update STATE.md

**Objective:** Document Phase 2 completion in project state.

**Files:**
- `.planning/STATE.md`

**Actions:**
1. Update "Frontend-Backend Integration Status" section
2. Mark Phase 2 as complete
3. Update progress indicators
4. Add any relevant decisions to Accumulated Context

**Acceptance Criteria:**
- STATE.md reflects Phase 2 completion
- Current status updated
- Ready for Phase 3

**Estimated Time:** 3 minutes

## Success Criteria

- [ ] Time-series hook created and working
- [ ] Trend calculations implemented (7-day, direction)
- [ ] Sparkline data populated from real time-series
- [ ] Entity transformer uses time-series data
- [ ] API service fetches time-series for details
- [ ] Frontend displays trends and sparklines
- [ ] STATE.md updated with Phase 2 completion

## Backend API Reference

```typescript
// GET /entities/{id}/sentiment
interface SentimentTimeseriesResponse {
  entity_id: number;
  period: string;
  data: SentimentPoint[];
  next_cursor: string | null;
  has_more: boolean;
}

interface SentimentPoint {
  timestamp: string;  // ISO datetime
  period: string;     // "hourly" or "daily"
  sentiment_mean: number | null;
  sentiment_min: number | null;
  sentiment_max: number | null;
  sentiment_std: number | null;
  article_count: number | null;
  reddit_sentiment: number | null;
  reddit_thread_count: number | null;
}
```

## Implementation Notes

- Use hourly period for sparkline data (more granular)
- Fetch last 7-30 points for sparklines
- Calculate trends from most recent vs previous period
- Handle null sentiment_mean values (treat as 0 or skip)
- Cache time-series data to avoid redundant fetches
