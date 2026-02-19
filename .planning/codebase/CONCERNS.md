# Codebase Concerns

**Analysis Date:** 2026-02-05

## TypeScript Configuration Relaxed

**Issue:** TypeScript strict mode is disabled with multiple type-safety checks turned off
- Files: `tsconfig.json`, `tsconfig.app.json`
- Impact: Type safety compromised; refactoring is error-prone; increases risk of runtime errors
- Current settings disabled:
  - `strict: false` (root cause - disables all strict checks)
  - `noUnusedLocals: false` - Dead code accumulation
  - `noUnusedParameters: false` - Unused parameters not caught
  - `noImplicitAny: false` - Any types not flagged
  - `strictNullChecks: false` - Null/undefined errors not caught
  - `noFallthroughCasesInSwitch: false` - Switch case bugs possible

**Fix approach:** Gradually enable strict mode:
1. Enable `strictNullChecks` first (lowest breaking impact)
2. Enable `noImplicitAny` with explicit type annotations
3. Enable full `strict: true` after codebase audit
4. Add `noUnusedLocals` and `noUnusedParameters` once clean

---

## ESLint Configuration Too Permissive

**Issue:** Unused variable checking disabled
- Files: `eslint.config.js` (line 23)
- Impact: Dead code not detected; code bloat; maintenance burden
- Current rule: `"@typescript-eslint/no-unused-vars": "off"`

**Fix approach:** Re-enable with exceptions for intentionally unused vars like `_unused`:
```javascript
"@typescript-eslint/no-unused-vars": [
  "warn",
  { argsIgnorePattern: "^_" }
]
```

---

## Sidebar Cookie Handling Lacks Protection

**Issue:** Direct unsanitized cookie write without SameSite or Secure flags
- Files: `src/components/ui/sidebar.tsx` (line 68)
- Impact: Potential XSS attack surface; CSRF vulnerability risk
- Current code:
  ```typescript
  document.cookie = `${SIDEBAR_COOKIE_NAME}=${openState}; path=/; max-age=${SIDEBAR_COOKIE_MAX_AGE}`;
  ```

**Security risk:** No `SameSite` or `Secure` flags; value not validated; only URL-safe boolean but pattern dangerous if reused elsewhere

**Fix approach:**
1. Add `SameSite=Strict; Secure` flags if HTTPS
2. Consider using browser localStorage instead (simpler, safer for non-sensitive state)
3. If cookies persist, add input validation layer
4. Document why cookies needed vs. alternatives

---

## Chart Component Uses dangerouslySetInnerHTML

**Issue:** Style tags injected via dangerouslySetInnerHTML
- Files: `src/components/ui/chart.tsx` (lines 69-86)
- Impact: XSS vulnerability if chart config comes from untrusted source
- Current pattern: Object.entries() generating CSS variable strings

**Current safety:** Config is internal/controlled, but pattern is fragile for future

**Fix approach:**
1. Add input validation: validate all theme and color values are valid hex/rgb
2. Add JSDoc warning that config must not come from user input
3. Consider CSS custom properties set via style attribute instead:
   ```typescript
   style={{ "--color-key": color } as React.CSSProperties}
   ```
4. Add tests verifying no HTML/scripts escape

---

## No Environment Configuration

**Issue:** No .env files, .env.example, or environment validation
- Files: None found
- Impact: Cannot configure API endpoints, feature flags, or external services; secrets would be exposed
- Blocks: Any API integration, multi-environment deployment

**Fix approach:**
1. Create `.env.example` with required vars
2. Add runtime validation in main entry (`src/main.tsx`)
3. Document required env vars in README
4. Add CI check for required env vars before build

---

## No Error Boundaries

**Issue:** Application lacks React error boundaries
- Files: `src/App.tsx`, `src/main.tsx`
- Impact: Single component error crashes entire app; poor UX for users
- Current: Only BrowserRouter error handling, no component fallback

**Fix approach:**
1. Create `ErrorBoundary` component wrapper
2. Add to `src/App.tsx` around route content
3. Implement error logging/reporting
4. Show user-friendly error UI instead of blank page

---

## Missing Content Security Policy (CSP)

**Issue:** No CSP headers defined; dangerouslySetInnerHTML used without protections
- Files: Public HTML entry point (not visible, likely `index.html`)
- Impact: XSS vulnerabilities not mitigated; inline styles easier to exploit
- Current: Browser defaults only

**Fix approach:**
1. Add CSP meta tag to HTML:
   ```html
   <meta http-equiv="Content-Security-Policy" content="default-src 'self'; style-src 'self' 'unsafe-inline'">
   ```
2. Configure Vite to set CSP headers in dev mode
3. Document CSP requirements for production deployment

---

## useToast Hook Has Dependency Warning

**Issue:** useToast useEffect dependency not properly specified
- Files: `src/hooks/use-toast.ts` (line 177)
- Impact: Stale closures; listener array could grow unbounded; memory leak risk
- Current code:
  ```typescript
  React.useEffect(() => {
    listeners.push(setState);
    return () => { /* cleanup */ };
  }, [state]);  // <-- state in dependency but state is updated
  ```

**Problem:** Depends on `state` which changes on every listener update, causing effect re-run and duplicate listeners

**Fix approach:**
```typescript
React.useEffect(() => {
  listeners.push(setState);
  return () => {
    const index = listeners.indexOf(setState);
    if (index > -1) listeners.splice(index, 1);
  };
}, []); // Empty dependency - register once
```

---

## useIsMobile Hook Has Double State Update

**Issue:** Initial value then resize listener both set state
- Files: `src/hooks/use-mobile.tsx` (lines 14)
- Impact: Unnecessary re-render on mount; hydration mismatch in SSR (if used)
- Current code sets state twice synchronously

**Fix approach:**
```typescript
const [isMobile, setIsMobile] = React.useState<boolean | undefined>(
  window.innerWidth < MOBILE_BREAKPOINT
);
```

---

## Test Coverage Minimal

**Issue:** Only placeholder test exists
- Files: `src/test/example.test.ts` - single "expect(true).toBe(true)" test
- Impact: No validation of actual code; regressions undetected; UI components untested
- Current: Zero coverage of hooks, components, or utilities

**Fix approach:**
1. Add unit tests for utilities (`src/lib/utils.ts`, `cn()` function)
2. Add hook tests for `useToast`, `useIsMobile`, `useCarousel`
3. Add component tests for critical UI components
4. Configure coverage reporting with threshold (e.g., 60%)
5. Target coverage on `src/` excluding UI library (which is generated)

---

## No Router Lazy Loading

**Issue:** All route components loaded upfront
- Files: `src/App.tsx` (lines 1, 6)
- Impact: Large bundle; slow initial load; no code splitting benefit
- Current: `import Index from "./pages/Index"` - eager import

**Fix approach:**
```typescript
const Index = lazy(() => import("./pages/Index"));
const NotFound = lazy(() => import("./pages/NotFound"));
// Wrap in Suspense
<Suspense fallback={<LoadingSpinner />}>
  <Routes>...
</Suspense>
```

---

## Console.error in Production Code

**Issue:** Direct console.error call in NotFound page
- Files: `src/pages/NotFound.tsx` (line 8)
- Impact: Cluttered console; not centralized logging; can't toggle for production
- Current: `console.error("404 Error: User attempted...")`

**Fix approach:**
1. Create logger utility: `src/lib/logger.ts`
2. Centralize logging with environment checks
3. Replace all console calls with logger
4. Add structured error reporting service (e.g., Sentry)

---

## No Input Validation Patterns

**Issue:** No form validation framework beyond react-hook-form setup
- Files: Dependencies show zod + react-hook-form, but no usage examples
- Impact: Cannot enforce data contract; vulnerable to invalid submissions; poor UX feedback
- Current: Infrastructure exists but not demonstrated

**Fix approach:**
1. Create validation schema examples (use existing zod + react-hook-form)
2. Add form error boundary patterns
3. Document validation best practices
4. Add CI test for schema validation

---

## Missing QueryClient Configuration

**Issue:** QueryClient created with defaults, no configuration
- Files: `src/App.tsx` (line 9)
- Impact: React Query caching behavior unclear; error handling not customized; may not match API expectations

**Fix approach:**
```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 0,
    },
  },
});
```

---

## Prettier Configuration Missing

**Issue:** No Prettier config file found
- Files: None (.prettierrc* not found)
- Impact: Code formatting inconsistent; Vite build might have different style rules; contributor confusion

**Fix approach:**
1. Create `.prettierrc` with team standards
2. Add pre-commit hook to format
3. Run `prettier --write src/` to normalize existing code

---

## No .gitignore Reviewed

**Issue:** Potential for committing sensitive files
- Files: Not visible in grep, assume standard but unverified
- Impact: Could accidentally commit `.env` files, build artifacts, or node_modules if corrupted

**Fix approach:**
1. Verify `.gitignore` contains: `.env`, `.env.local`, `dist/`, `node_modules/`
2. Add hook to prevent env file commits
3. Document in CONTRIBUTING.md

---

## Vite Dev Server Hardcoded Configuration

**Issue:** Dev server hardcoded to port 8080 and :: host
- Files: `vite.config.ts` (lines 8-13)
- Impact: Conflicts if port in use; cannot customize without code change; CI/CD issues

**Fix approach:**
```typescript
server: {
  host: process.env.VITE_HOST ?? "127.0.0.1",
  port: parseInt(process.env.VITE_PORT ?? "5173"),
  hmr: process.env.VITE_HMR === "false" ? false : { overlay: false },
}
```

---

## Memory Leak Potential in Toast System

**Issue:** toastTimeouts Map in use-toast.ts could grow if dispose not called
- Files: `src/hooks/use-toast.ts` (line 53, 61-68)
- Impact: Memory leak over long sessions with many toasts; possible performance degradation
- Current: Relies on setTimeout cleanup, but if dispatch never called, timeout lingers

**Fix approach:**
1. Add cleanup verification test
2. Add explicit cleanup on component unmount
3. Consider using AbortController pattern instead of Map
4. Add max timeout tracking

---

## No Loading/Skeleton States Documented

**Issue:** App uses Skeleton component but no loading pattern guide
- Files: `src/components/ui/skeleton.tsx` exists but not used in main app
- Impact: Inconsistent loading UX; components might block rendering
- Current: Infrastructure exists but pattern unclear

**Fix approach:**
1. Document loading state pattern
2. Create example in pages
3. Add tests for suspense boundaries
4. Create loading placeholder components

---

## NavLink Wrapper May Cause Confusion

**Issue:** Custom NavLink wrapper shadows React Router's component
- Files: `src/components/NavLink.tsx`
- Impact: Confusing imports (local vs. imported); not immediately clear why wrapper needed
- Current: Adds activeClassName/pendingClassName support

**Fix approach:**
1. Add JSDoc explaining why wrapper needed
2. Consider inline className function instead:
   ```typescript
   <RouterNavLink className={({isActive}) => ...} />
   ```
3. Document when to use each pattern

---

## No Accessibility (a11y) Testing

**Issue:** No accessibility checks; components not validated for WCAG compliance
- Files: All UI components (can't verify without audit)
- Impact: Screen reader issues; keyboard navigation broken; fails accessibility audits

**Fix approach:**
1. Add `@testing-library/jest-dom` assertions for a11y
2. Add `jest-axe` for automated a11y testing
3. Test keyboard navigation on interactive components
4. Verify color contrast ratios
5. Test with screen reader (NVDA/VoiceOver)

---

*Concerns audit: 2026-02-05*
