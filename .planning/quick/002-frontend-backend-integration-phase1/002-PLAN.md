# Quick Task 002: Frontend-Backend Integration - Phase 1 (Critical Path)

**Created:** 2026-02-05
**Status:** Planning Complete
**Type:** Implementation
**Dependencies:** Quick Task 001 (alignment analysis)

## Description

Implement Phase 1 of the frontend-backend integration to enable end-to-end data flow from backend to frontend. This involves updating API endpoints, implementing real fetch calls, and creating a data transformation layer.

## Context

From Quick Task 001 analysis:
- Frontend expects `/tools` endpoints, backend provides `/entities`
- Frontend uses mock data in `src/services/api.ts`
- Data structures misaligned between `Tool` interface and `EntitySchema`
- Need data transformation layer to map backend responses to frontend expectations

## Tasks

### Task 1: Update API Endpoint Paths

**Objective:** Fix endpoint path mismatches between frontend and backend.

**Files:**
- `src/services/api.ts` (if exists) or create it
- Any hook files that hardcode endpoint paths

**Actions:**
1. Check current API service file structure
2. Update `/tools` → `/entities` for list endpoint
3. Update `/tools/${id}` → `/entities/${id}` for detail endpoint
4. Ensure base URL is configurable

**Acceptance Criteria:**
- Endpoints point to correct backend paths
- Base URL is configurable via environment variable
- No hardcoded URLs

**Estimated Time:** 10 minutes

---

### Task 2: Implement Real Fetch Calls

**Objective:** Replace mock data with real API calls to backend.

**Files:**
- `src/services/api.ts`

**Actions:**
1. Add/configure `BASE_URL` from environment variable
2. Implement `fetchTools()` with real fetch call to `/entities`
3. Implement `fetchToolDetail(id)` with real fetch call to `/entities/{id}`
4. Add error handling (try/catch, response.ok check)
5. Add proper TypeScript typing for responses
6. Handle 404 and error responses appropriately

**Acceptance Criteria:**
- Mock data replaced with fetch calls
- Error handling for network failures
- Proper HTTP status code handling
- Type-safe response parsing

**Estimated Time:** 15 minutes

---

### Task 3: Create Data Transformation Layer

**Objective:** Transform backend entity data to frontend tool format.

**Files:**
- `src/services/entityTransformer.ts` (NEW)

**Actions:**
1. Create `entityTransformer.ts` module
2. Implement `toTool(entity: EntitySchema): Tool` function
   - Convert numeric ID to string
   - Map `category` to `type` ("model" → "llm", "tool" → "tool")
   - Transform sentiment score to 3-bucket format (positive/neutral/negative)
   - Add placeholder/mock values for missing fields (rank, company, mentions, etc.)
3. Implement `toToolDetail(entity: EntityDetailSchema, sentimentData?: SentimentTimeseriesResponse): ToolDetail` function
   - Extend base Tool transformation
   - Add latest_sentiment handling
   - Add placeholder/mock data for extended fields (description, versions, bestFor, rating, etc.)
4. Add sentiment transformation helper
   - Convert single score to {positive, neutral, negative} breakdown
5. Export all functions

**Acceptance Criteria:**
- EntitySchema successfully transforms to Tool
- EntityDetailSchema successfully transforms to ToolDetail
- ID type conversion (number → string) working
- Sentiment score transformed to 3-bucket format
- Missing fields populated with sensible defaults

**Estimated Time:** 30 minutes

---

### Task 4: Integrate Transformation Layer

**Objective:** Use transformation layer in API service functions.

**Files:**
- `src/services/api.ts`

**Actions:**
1. Import transformation functions
2. Apply `toTool()` transformation in `fetchTools()`
3. Apply `toToolDetail()` transformation in `fetchToolDetail()`
4. Verify data flow works end-to-end
5. Test with actual backend data

**Acceptance Criteria:**
- API functions return transformed Tool/ToolDetail objects
- Data flows from backend → transformation → frontend correctly
- TypeScript types match expected interfaces

**Estimated Time:** 10 minutes

---

### Task 5: Update Environment Configuration

**Objective:** Add API base URL to environment configuration.

**Files:**
- `.env.example` (frontend)
- `vite.config.ts` (if proxy needed)

**Actions:**
1. Check if `.env.example` exists in frontend root
2. Add `VITE_API_BASE_URL=http://localhost:8000` to `.env.example`
3. Check `vite.config.ts` for proxy configuration
4. Add proxy if not present (proxy /api to backend)
5. Document the environment variable usage

**Acceptance Criteria:**
- `.env.example` documents API base URL
- Vite proxy configured for development
- Clear documentation on environment setup

**Estimated Time:** 5 minutes

---

### Task 6: Update STATE.md

**Objective:** Document Phase 1 completion in project state.

**Files:**
- `.planning/STATE.md`

**Actions:**
1. Update "Frontend-Backend Integration Status" section
2. Mark Phase 1 as complete
3. Update progress indicators
4. Add any relevant decisions to Accumulated Context

**Acceptance Criteria:**
- STATE.md reflects Phase 1 completion
- Current status updated
- Ready for Phase 2

**Estimated Time:** 3 minutes

## Success Criteria

- [ ] Frontend makes real API calls to backend
- [ ] Backend entities display in frontend UI
- [ ] Data transformation working correctly
- [ ] Error handling for failed requests
- [ ] Environment configuration documented
- [ ] STATE.md updated with Phase 1 completion

## Backend Schema Reference

```typescript
// EntitySchema
interface EntitySchema {
  id: number;
  name: string;
  category: string;
  created_at: string;
}

// EntityDetailSchema
interface EntityDetailSchema {
  id: number;
  name: string;
  category: string;
  created_at: string;
  latest_sentiment: number | null;
}
```

## Frontend Target Schema

```typescript
// Tool
interface Tool {
  id: string;
  rank: number;
  name: string;
  company: string;
  logo?: string;
  sentiment: { positive: number; neutral: number; negative: number };
  mentions: number;
  trend: "up" | "down" | "stable";
  trendPercent7d: number;
  sparklineData: number[];
  type: "llm" | "tool";
}

// ToolDetail
interface ToolDetail extends Tool {
  description: string;
  versions: string[];
  currentVersion: string;
  bestFor: string[];
  rating: number;
  trendData: TrendDataPoint[];
  recentMentions: Mention[];
}
```

## Implementation Notes

- Use mock/placeholder values for fields not available in backend (rank, company, mentions, etc.)
- Focus on getting real data flowing - can enhance in Phase 2
- Sentiment transformation: simple mapping for now (positive > 0.1, neutral ~0, negative < -0.1)
- Category mapping: "model" → "llm", everything else → "tool"
