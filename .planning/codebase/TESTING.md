# Testing Patterns

**Analysis Date:** 2026-02-05

## Test Framework

**Runner:**
- Vitest 3.2.4
- Config: `vitest.config.ts`

**Assertion Library:**
- Vitest built-in expect API (compatible with Jest)
- @testing-library/react 16.0.0 for React component testing
- @testing-library/jest-dom 6.6.0 for DOM matchers

**Run Commands:**
```bash
npm run test              # Run all tests once
npm run test:watch       # Run tests in watch mode
```

## Test File Organization

**Location:**
- Co-located with source code in `src/test/` directory
- Test files placed in dedicated test folder rather than alongside components

**Naming:**
- Pattern: `*.test.ts` or `*.spec.ts`
- Example: `src/test/example.test.ts`

**Structure:**
```
src/
├── test/
│   ├── setup.ts           # Test environment setup
│   └── example.test.ts    # Test files
```

## Test Structure

**Suite Organization:**
```typescript
import { describe, it, expect } from "vitest";

describe("feature name", () => {
  it("should perform expected behavior", () => {
    expect(true).toBe(true);
  });
});
```

**Patterns:**
- Tests use `describe()` for grouping related tests
- Tests use `it()` for individual test cases
- Assertion via `expect()` with matcher chaining

## Test Setup

**File:** `src/test/setup.ts`

**Configuration:**
- Imports @testing-library/jest-dom matchers
- Polyfills `window.matchMedia` for components testing media queries
- Provides mock implementation for matchMedia API required by responsive components

**matchMedia Mock Implementation:**
```typescript
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},      // Deprecated but still used
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => {},
  }),
});
```

## Vitest Configuration

**File:** `vitest.config.ts`

**Key Settings:**
- Environment: `jsdom` (browser-like environment for React components)
- Globals: `true` (describe, it, expect available without imports)
- Setup files: `./src/test/setup.ts` (runs before tests)
- Include pattern: `src/**/*.{test,spec}.{ts,tsx}` (discovers test files)
- Path alias: `@` resolves to `./src`

**Environment Setup:**
- jsdom provides DOM APIs (window, document, etc.)
- React SWC plugin enabled for JSX transformation
- Path resolution mirrors application configuration

## Mocking

**Framework:** Vitest built-in mocking (vi object)

**Patterns:**
Not extensively demonstrated in current codebase, but available:
- Vitest provides `vi.mock()`, `vi.spyOn()`, `vi.fn()` utilities
- @testing-library/react provides utilities like `render()`, `fireEvent`, `waitFor()`

**What to Mock:**
- External API calls (use vi.mock or vi.spyOn)
- Browser APIs like matchMedia (handled in setup.ts)
- Redux/state management (wrap in providers)

**What NOT to Mock:**
- React components themselves (test real rendering)
- DOM event handlers (use fireEvent/userEvent)
- Component lifecycle hooks (test side effects via useEffect)

## Fixtures and Factories

**Test Data:**
Not explicitly observed in current codebase. Pattern recommendations:
- Create factory functions in test utilities for complex data objects
- Keep fixtures close to tests using them
- Use inline objects for simple data

**Location:**
- Would place shared fixtures in `src/test/fixtures/` or `src/test/factories/`
- Component-specific fixtures can live in dedicated .test.ts files

## Coverage

**Requirements:** Not enforced (no coverage configuration in vitest.config.ts)

**View Coverage:**
```bash
npx vitest --coverage
```

(Requires coverage provider like @vitest/coverage-v8 to be installed)

## Test Types

**Unit Tests:**
- Scope: Individual functions, utilities, hooks
- Approach: Test in isolation with mocked dependencies
- Location: Alongside implementation in `src/test/`
- Example pattern: Test utility functions like `cn()` from `src/lib/utils.ts`

**Integration Tests:**
- Scope: Multiple components working together, or components with their providers
- Approach: Render full component tree with real providers (QueryClientProvider, BrowserRouter, etc.)
- Example: Test a page component with all its hooks and providers

**E2E Tests:**
- Framework: Not configured
- Can be added with Playwright or Cypress if needed
- Would require separate configuration

## Common Patterns

**Async Testing:**
```typescript
describe("async operation", () => {
  it("should handle async data", async () => {
    // Vitest automatically detects async tests
    const result = await fetchData();
    expect(result).toBeDefined();
  });

  it("should wait for state updates", async () => {
    // When testing React components with async state
    const { getByText } = render(<MyComponent />);
    // Use waitFor from @testing-library/react for state updates
    await waitFor(() => {
      expect(getByText("loaded")).toBeInTheDocument();
    });
  });
});
```

**Error Testing:**
```typescript
describe("error handling", () => {
  it("should throw on invalid input", () => {
    expect(() => {
      functionThatThrows(null);
    }).toThrow("Expected non-null value");
  });
});
```

**Hook Testing:**
```typescript
import { renderHook, act } from "@testing-library/react";
import { useIsMobile } from "@/hooks/use-mobile";

describe("useIsMobile", () => {
  it("should detect mobile viewport", () => {
    const { result } = renderHook(() => useIsMobile());
    expect(typeof result.current).toBe("boolean");
  });
});
```

**Component Rendering:**
```typescript
import { render } from "@testing-library/react";
import { Button } from "@/components/ui/button";

describe("Button", () => {
  it("should render with default variant", () => {
    const { getByRole } = render(<Button>Click me</Button>);
    expect(getByRole("button")).toBeInTheDocument();
  });

  it("should apply variant class", () => {
    const { getByRole } = render(<Button variant="destructive">Delete</Button>);
    expect(getByRole("button")).toHaveClass("bg-destructive");
  });
});
```

## Testing Libraries Available

**Installed but not yet used in tests:**
- @testing-library/react (16.0.0) - Component rendering and queries
- @testing-library/jest-dom (6.6.0) - DOM matchers (toBeInTheDocument, etc.)
- react-hook-form (7.61.1) - Form testing utilities available
- zod (3.25.76) - Schema validation can be tested directly

## Current Test Status

**Existing Tests:**
- `src/test/example.test.ts` - Basic passing test to verify setup

**Coverage Gaps:**
- No tests for components (Button, Card, Alert, etc.)
- No tests for hooks (useToast, useIsMobile)
- No tests for utilities (cn function)
- No integration tests with providers
- No E2E tests

---

*Testing analysis: 2026-02-05*
