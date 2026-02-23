import { QueryClient } from "@tanstack/react-query";

/**
 * Factory function returning an AspectSentimentResponse-shaped object.
 * Used in tests to provide realistic aspect sentiment data.
 */
export function mockAspectResponse(overrides = {}) {
  return {
    entity_id: 1,
    window: "7d",
    source: null,
    aspects: {
      performance:    { mean: 0.65,  count: 12 },
      cost:           { mean: -0.30, count: 8  },
      reliability:    { mean: 0.40,  count: 9  },
      ux:             { mean: 0.10,  count: 5  },
      speed:          { mean: 0.55,  count: 11 },
      code_quality:   { mean: 0.20,  count: 7  },
      context_window: { mean: null,  count: 0  },
    },
    ...overrides,
  };
}

/**
 * Returns a QueryClient configured for testing.
 * No retries, infinite stale time — prevents flaky async behavior in tests.
 */
export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: Infinity },
    },
  });
}

/**
 * Returns an AspectSentimentResponse where all aspects have count=0 and mean=null.
 * Used to test empty-state rendering.
 */
export function mockEmptyAspectResponse(entityId = 1) {
  const aspects = Object.fromEntries(
    ["performance", "cost", "reliability", "ux", "speed", "code_quality", "context_window"]
      .map((k) => [k, { mean: null, count: 0 }])
  );
  return { entity_id: entityId, window: "7d", source: "discourse", aspects };
}
