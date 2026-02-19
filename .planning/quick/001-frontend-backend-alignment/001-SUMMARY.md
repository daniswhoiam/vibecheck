# Frontend-Backend Alignment Analysis - Quick Task 001

**Completed:** 2026-02-05
**Task:** Analyze frontend-backend API alignment and document integration gaps

---

## Executive Summary

The Vibecheck frontend and backend are **currently disconnected**. While Phase 3 (API & Integration) is marked complete in STATE.md, the frontend is still using mock data and has not been integrated with the real backend API. This analysis identifies critical alignment gaps that must be resolved before the application can function end-to-end.

**Status:** 🔴 **CRITICAL MISALIGNMENT** - Frontend cannot communicate with backend without fixes

---

## Available Backend Endpoints

### Health Endpoints
| Method | Path | Purpose | Status |
|--------|------|---------|--------|
| GET | `/health` | Database connectivity check | ✅ Working |
| GET | `/health/scheduler` | Scheduled job health status | ✅ Working |

### Entity Endpoints
| Method | Path | Response Schema | Status |
|--------|------|-----------------|--------|
| GET | `/entities` | `EntitySchema[]` | ✅ Implemented |
| GET | `/entities/{entity_id}` | `EntityDetailSchema` | ✅ Implemented |
| GET | `/entities/{entity_id}/sentiment` | `SentimentTimeseriesResponse` | ✅ Implemented |

### Backend Data Models

```typescript
// EntitySchema (list view)
interface EntitySchema {
  id: number;
  name: string;
  category: string;
  created_at: datetime;
}

// EntityDetailSchema (detail view)
interface EntityDetailSchema extends EntitySchema {
  latest_sentiment: number | null;
}

// SentimentPointSchema
interface SentimentPointSchema {
  timestamp: datetime;
  period: string;  // "hourly" or "daily"
  sentiment_mean: number | null;
  sentiment_min: number | null;
  sentiment_max: number | null;
  sentiment_std: number | null;
  article_count: number | null;
  reddit_sentiment: number | null;
  reddit_thread_count: number | null;
}

// SentimentTimeseriesResponse
interface SentimentTimeseriesResponse {
  entity_id: number;
  period: string;
  data: SentimentPointSchema[];
  next_cursor: string | null;
  has_more: boolean;
}
```

---

## Frontend API Expectations

### Frontend Data Models

```typescript
// Tool interface (what frontend expects)
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

// ToolDetail interface
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

### Frontend API Calls

**File:** `src/services/api.ts`

```typescript
// Current: Mock data functions
export async function fetchTools(): Promise<Tool[]> {
  // TODO: Replace with real API call
  // return fetch(`${BASE_URL}/tools`).then(...)
  return mockTools;  // Currently returns hardcoded data
}

export async function fetchToolDetail(id: string): Promise<ToolDetail | null> {
  // TODO: Replace with real API call
  // return fetch(`${BASE_URL}/tools/${id}`).then(...)
  return mockToolDetail;  // Currently returns hardcoded data
}
```

**React Query Hooks:**
- `useTools()` - Fetches all tools for listing page
- `useToolDetail(id)` - Fetches single tool details

---

## Critical Alignment Issues

### 🔴 Issue 1: API Endpoint Path Mismatch

**Impact:** HIGH - Frontend calls will fail with 404 errors

| Frontend Expects | Backend Provides | Fix Required |
|------------------|------------------|--------------|
| `GET /tools` | `GET /entities` | Update frontend to use `/entities` |
| `GET /tools/{id}` | `GET /entities/{entity_id}` | Update frontend to use `/entities/{id}` |
| `GET /tools/{id}/trend` | `GET /entities/{id}/sentiment` | Implement sentiment call |

**Files to Change:**
- `src/services/api.ts` - Update endpoint paths
- `src/hooks/useTools.ts` (if exists) - Update endpoint paths
- `src/hooks/useToolDetail.ts` (if exists) - Update endpoint paths

---

### 🔴 Issue 2: Data Structure Mismatch

**Impact:** HIGH - Data transformation layer required

**Field Mapping Required:**

| Frontend Field | Backend Field | Type | Notes |
|----------------|---------------|------|-------|
| `id` | `id` | string → number | Convert number to string |
| `name` | `name` | string → string | ✅ Direct match |
| `rank` | *(missing)* | number | Needs algorithm or mock data |
| `company` | *(missing)* | string | Not tracked in backend |
| `sentiment` | `latest_sentiment` | object → number | Needs transformation |
| `mentions` | *(missing)* | number | Could use `article_count` |
| `trend` | *(missing)* | enum | Needs calculation from time-series |
| `trendPercent7d` | *(missing)* | number | Needs calculation from time-series |
| `sparklineData` | *(missing)* | number[] | Use sentiment time-series data |
| `type` | `category` | enum | Map "model"/"tool" to "llm"/"tool" |

**Missing Backend Fields:**
- `logo` - No image/logo tracking
- `company` - No company/organization tracking
- `description` - No entity descriptions
- `versions` - No version history tracking
- `bestFor` - No use case tracking
- `rating` - No rating system
- `recentMentions` - No articles endpoint

**Solutions:**
1. **Option A:** Transform backend data in frontend (map Entity → Tool with mock data for missing fields)
2. **Option B:** Extend backend schemas to include frontend fields
3. **Option C:** Hybrid - Transform available fields, mock missing ones

**Recommended:** Option A for quick integration, add backend fields incrementally

---

### 🟡 Issue 3: ID Type Mismatch

**Impact:** MEDIUM - Type conversion required

- **Frontend:** `id: string` (e.g., "1", "2", "openai-gpt-4")
- **Backend:** `id: number` (e.g., 1, 2, 3)

**Fix Required:**
```typescript
// Convert backend numeric IDs to strings for frontend
const tool: Tool = {
  id: String(entity.id),  // number → string
  // ... rest of mapping
};
```

---

### 🟡 Issue 4: Sentiment Data Structure

**Impact:** MEDIUM - Sentiment format differs

**Frontend Expects:**
```typescript
sentiment: {
  positive: number;  // e.g., 0.65
  neutral: number;   // e.g., 0.25
  negative: number;  // e.g., 0.10
}
```

**Backend Provides:**
```typescript
sentiment_mean: number | null;  // e.g., 0.35 (overall score)
reddit_sentiment: number | null;  // e.g., 0.45
```

**Transformation Logic:**
- If `sentiment_mean > 0`: positive sentiment
- If `sentiment_mean < 0`: negative sentiment
- If `sentiment_mean ≈ 0`: neutral sentiment
- Need to distribute single score into 3-bucket breakdown

**Example Transformation:**
```typescript
function transformSentiment(meanScore: number | null) {
  if (meanScore === null) {
    return { positive: 0, neutral: 0, negative: 0 };
  }

  // Simple mapping - can be refined
  if (meanScore > 0.1) {
    return { positive: meanScore, neutral: 1 - meanScore, negative: 0 };
  } else if (meanScore < -0.1) {
    return { positive: 0, neutral: 1 - Math.abs(meanScore), negative: Math.abs(meanScore) };
  } else {
    return { positive: 0, neutral: 1, negative: 0 };
  }
}
```

---

### 🟢 Issue 5: CORS Configuration

**Impact:** NONE - Already aligned ✅

- **Backend:** `CORS_ORIGINS=*` (allows all origins)
- **Frontend:** `http://localhost:8080` (Vite dev server)
- **Status:** No CORS issues expected

---

### 🟢 Issue 6: Port Configuration

**Impact:** LOW - Already configured ✅

- **Frontend:** Port 8080 (Vite config)
- **Backend:** Port 8000 (default FastAPI)
- **Status:** No conflicts

---

## Missing Integrations

### 1. Real API Implementation

**Current:** Frontend uses hardcoded mock data in `src/services/api.ts`

**Required:**
- [ ] Implement real `fetch()` calls to backend
- [ ] Configure API base URL (environment variable)
- [ ] Add error handling for network failures
- [ ] Add loading states and timeouts

**Files:**
- `src/services/api.ts`

---

### 2. Sentiment Time-Series Integration

**Available:** Backend provides `/entities/{id}/sentiment` with rich time-series data

**Not Used:** Frontend doesn't call this endpoint

**Potential Use Cases:**
- Trend charts on detail pages
- Sparkline data for list view
- Historical sentiment visualization
- Reddit sentiment comparison

**Required:**
- [ ] Create `useSentimentTimeSeries(id)` hook
- [ ] Implement data fetching from `/entities/{id}/sentiment`
- [ ] Transform `SentimentPointSchema[]` to chart data
- [ ] Add date range filtering UI

---

### 3. Data Transformation Layer

**Required:** Map backend entities to frontend tools

**Implementation Options:**

**Option A: Frontend Service (Recommended for quick integration)**
```typescript
// src/services/entityTransformer.ts
export function toTool(entity: EntitySchema): Tool {
  return {
    id: String(entity.id),
    name: entity.name,
    rank: 1,  // Mock or calculate
    company: "Unknown",  // Mock or map from category
    sentiment: transformSentiment(entity.latest_sentiment),
    mentions: 0,  // Mock until article endpoint exists
    trend: "stable",  // Calculate from time-series
    trendPercent7d: 0,  // Calculate from time-series
    sparklineData: [],  // Fetch from /sentiment endpoint
    type: entity.category === "model" ? "llm" : "tool",
  };
}
```

**Option B: Backend Adapter Endpoint**
- Create `/tools` endpoint that wraps `/entities`
- Transform data on backend
- Frontend gets data in correct format

**Option C: Backend Schema Update**
- Add frontend fields to EntitySchema
- Populate fields in database
- Frontend consumes data directly

---

## Prioritized Action Plan

### Phase 1: Critical Path (End-to-End Data Flow)

**Goal:** Frontend displays real data from backend

1. **Update API Endpoint Paths** (10 min)
   - [ ] Change `/tools` → `/entities` in `src/services/api.ts`
   - [ ] Change `/tools/${id}` → `/entities/${id}` in `src/services/api.ts`
   - [ ] Update hook implementations if needed
   - **Impact:** Enables basic communication

2. **Implement Real Fetch Calls** (15 min)
   - [ ] Uncomment `BASE_URL` configuration
   - [ ] Replace mock returns with `fetch()` calls
   - [ ] Add error handling (try/catch, status checks)
   - **Impact:** Real data flows to frontend

3. **Create Data Transformation Layer** (30 min)
   - [ ] Create `src/services/entityTransformer.ts`
   - [ ] Implement `toTool()` function
   - [ ] Implement `toToolDetail()` function
   - [ ] Handle ID type conversion (number → string)
   - [ ] Transform sentiment score to 3-bucket format
   - **Impact:** Frontend can render backend data

**Time Estimate:** 55 minutes
**Result:** Functional frontend showing real backend data (with some mocked fields)

---

### Phase 2: Enhanced Features (Leverage Available Data)

**Goal:** Use sentiment time-series data for better UX

1. **Implement Sentiment Time-Series Hook** (20 min)
   - [ ] Create `useSentimentTimeSeries(id)` hook
   - [ ] Fetch from `/entities/{id}/sentiment`
   - [ ] Handle pagination (next_cursor, has_more)
   - **Impact:** Access to historical sentiment data

2. **Add Trend Calculations** (15 min)
   - [ ] Calculate 7-day trend from time-series data
   - [ ] Determine trend direction (up/down/stable)
   - [ ] Generate sparkline data points
   - **Impact:** Dynamic trend indicators instead of mocks

3. **Update Sparkline Data** (10 min)
   - [ ] Use real sentiment points for sparklines
   - [ ] Fetch last 30 data points for list view
   - [ ] Cache results to avoid excessive API calls
   - **Impact:** Real trend visualization on list cards

**Time Estimate:** 45 minutes
**Result:** Richer data visualization with real trends

---

### Phase 3: Production Readiness (Error Handling & Config)

**Goal:** Robust API integration ready for deployment

1. **Environment Configuration** (10 min)
   - [ ] Add `VITE_API_BASE_URL` to `.env.example`
   - [ ] Update `vite.config.ts` proxy settings
   - [ ] Add production/development base URL logic
   - **Impact:** Flexible deployment configuration

2. **Error Handling** (20 min)
   - [ ] Add retry logic for failed requests
   - [ ] Implement exponential backoff
   - [ ] Show user-friendly error messages
   - [ ] Add React Query error states
   - **Impact:** Better user experience during failures

3. **Loading States** (10 min)
   - [ ] Add skeleton loaders for list view
   - [ ] Add loading spinners for detail view
   - [ ] Implement optimistic UI updates
   - **Impact:** Perceived performance improvement

4. **Testing** (30 min)
   - [ ] Test with empty database (no entities)
   - [ ] Test with missing sentiment data
   - [ ] Test API failure scenarios
   - [ ] Verify CORS in production environment
   - **Impact:** Confidence in deployment

**Time Estimate:** 70 minutes
**Result:** Production-ready frontend-backend integration

---

### Phase 4: Feature Expansion (Optional Enhancements)

**Goal:** Add features beyond current backend capabilities

1. **Missing Backend Fields** (Backend work required)
   - [ ] Add `company` field to Entity model
   - [ ] Add `description` field to Entity model
   - [ ] Create articles endpoint for recent mentions
   - [ ] Add ranking algorithm
   - **Impact:** More complete data, requires backend changes

2. **Advanced Analytics** (Frontend + Backend)
   - [ ] Sentiment comparison between entities
   - [ ] Custom date range selectors
   - [ ] Export data as CSV
   - [ ] Reddit vs overall sentiment comparison
   - **Impact:** Enhanced user capabilities

**Time Estimate:** 3-4 hours (includes backend work)
**Result:** Full-featured analytics application

---

## Recommendations

### Immediate Action (This Session)

1. **Document this analysis** in STATE.md (under "Frontend-Backend Integration Status")
2. **Create quick task 002** to implement Phase 1 (Critical Path)
3. **Get stakeholder approval** on transformation approach (Option A/B/C)

### Short Term (Next Week)

1. Implement Phase 1: Critical Path (55 min)
2. Implement Phase 2: Enhanced Features (45 min)
3. Test end-to-end in development environment

### Long Term (Future Phases)

1. Implement Phase 3: Production Readiness (70 min)
2. Plan Phase 4: Feature Expansion
3. Consider backend schema updates for missing fields

---

## File-by-File Change Summary

### Files That Need Changes

#### Frontend (Critical)

1. **`src/services/api.ts`**
   - Update endpoint paths (/tools → /entities)
   - Implement real fetch calls
   - Add error handling
   - Configure base URL

2. **`src/services/entityTransformer.ts`** (NEW)
   - Create transformation functions
   - Map EntitySchema → Tool
   - Map EntityDetailSchema → ToolDetail
   - Transform sentiment data

3. **`src/hooks/useTools.ts`** (if exists)
   - Update to use real API
   - Add loading/error states

4. **`src/hooks/useToolDetail.ts`** (if exists)
   - Update to use real API
   - Add loading/error states

5. **`src/hooks/useSentimentTimeSeries.ts`** (NEW)
   - Create hook for time-series data
   - Handle pagination
   - Cache results

#### Configuration

6. **`.env.example`**
   - Add `VITE_API_BASE_URL=http://localhost:8000`

7. **`vite.config.ts`**
   - Configure proxy for /api routes

#### Documentation

8. **`.planning/STATE.md`**
   - Add "Frontend-Backend Integration Status" section
   - Document current alignment state
   - Link to this quick task

---

## Conclusion

The Vibecheck application has a **functional backend API** and a **well-designed frontend UI**, but they are **currently disconnected**. The frontend is using mock data and expects different API endpoints and data structures than what the backend provides.

**Good News:**
- Backend API is complete and working
- CORS is properly configured
- All necessary endpoints exist
- Data transformation is straightforward

**Path Forward:**
- Phase 1 (55 min): Connect frontend to backend with data transformation
- Phase 2 (45 min): Add sentiment time-series features
- Phase 3 (70 min): Production-ready error handling and config

**Estimated Total Time:** 2.5-3 hours for full integration

This analysis provides a clear roadmap for connecting the frontend and backend. The next step is stakeholder review and approval of the recommended approach.
