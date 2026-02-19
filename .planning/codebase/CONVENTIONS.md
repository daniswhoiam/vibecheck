# Coding Conventions

**Analysis Date:** 2026-02-05

## Naming Patterns

**Files:**
- Components: PascalCase, e.g., `Button.tsx`, `Card.tsx`, `Index.tsx`
- Utilities/hooks: camelCase with optional prefix, e.g., `use-toast.ts`, `use-mobile.tsx`, `utils.ts`
- UI component files: kebab-case, e.g., `alert-dialog.tsx`, `button.tsx`, `card.tsx`, `input-otp.tsx`
- Page files: PascalCase, e.g., `Index.tsx`, `NotFound.tsx`

**Functions:**
- Hook functions: prefix with `use`, e.g., `useToast()`, `useIsMobile()`
- Regular functions: camelCase, e.g., `toast()`, `cn()`, `genId()`, `dispatch()`
- React components: PascalCase, e.g., `Card`, `Button`, `Alert`, `Index`

**Variables:**
- Constants: UPPER_SNAKE_CASE, e.g., `TOAST_LIMIT`, `TOAST_REMOVE_DELAY`, `MOBILE_BREAKPOINT`, `MAX_SAFE_INTEGER`
- Regular variables: camelCase, e.g., `isMobile`, `toastId`, `state`, `memoryState`
- React state: camelCase, e.g., `className`, `variant`, `size`, `open`

**Types:**
- Interface/Type names: PascalCase, e.g., `ButtonProps`, `ToasterToast`, `State`, `Action`, `ActionType`
- Props types: Component name + "Props", e.g., `ButtonProps`, `CardProps`
- Generic types for discriminated unions: PascalCase, e.g., `ToasterToast`, `Action`

## Code Style

**Formatting:**
- Prettier (via Vite/TypeScript setup, implicit configuration)
- Line length: Follows default Prettier (80-100 characters)
- Indentation: 2 spaces

**Linting:**
- ESLint with TypeScript support (@eslint/js, typescript-eslint)
- React hooks and refresh plugins enabled
- Key enforced rules:
  - React hooks must follow rules of hooks (react-hooks/rules-of-hooks)
  - React refresh component exports only (react-refresh/only-export-components with allowConstantExport)
  - Unused variables disabled (noUnusedLocals: false, noUnusedParameters: false)
  - Implicit any allowed (noImplicitAny: false)

**Component Structure Pattern:**
Functional components with arrow function or function declaration. Example from `src/components/ui/card.tsx`:
```typescript
const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("...", className)} {...props} />
  )
);
Card.displayName = "Card";
```

## Import Organization

**Order:**
1. React and external libraries (e.g., `import * as React from "react"`)
2. Internal path-aliased imports from `@/` (e.g., `import { cn } from "@/lib/utils"`)
3. Type imports (using explicit `type` keyword where applicable)

**Example from `src/components/ui/button.tsx`:**
```typescript
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";
```

**Path Aliases:**
- `@/*` maps to `./src/*` (defined in tsconfig.json)
- Used for all internal imports to avoid relative paths

## Error Handling

**Patterns:**
- Console logging for errors in useEffect hooks, e.g., `console.error("404 Error: User attempted to access non-existent route:", location.pathname)`
- No try/catch blocks observed; relies on React error boundaries (implicit)
- Validation handled through react-hook-form and zod schemas (available as dependencies)

**Error Context:**
- Errors logged with descriptive context messages
- Location/path information included when relevant

## Logging

**Framework:** `console` (native browser API)

**Patterns:**
- `console.error()` for logging errors with context
- Logging occurs in lifecycle hooks (useEffect)
- Only error-level logging observed; no debug/info/warn patterns established

## Comments

**When to Comment:**
- Inline comments rare; code is generally self-documenting
- Comments used for design system information and special cases
- Side effects marked with inline comments, e.g., `// ! Side effects !` in `src/hooks/use-toast.ts`

**JSDoc/TSDoc:**
- Not used; TypeScript interfaces/types serve as inline documentation
- React.forwardRef components include displayName for debugging

## Function Design

**Size:** Functions are compact and focused; utility functions are single-responsibility (e.g., `cn()` for className merging, `genId()` for ID generation)

**Parameters:**
- Spread operator used for forwarding component props: `...props`
- Destructuring used for extracting specific props: `{ className, variant, size, asChild = false, ...props }`
- Default values set at destructuring level: `asChild = false`

**Return Values:**
- Components return JSX elements
- Hooks return state/functions, e.g., `useToast()` returns object with `{ toasts, toast, dismiss }`
- Utility functions return simple values, e.g., `cn()` returns string

## Module Design

**Exports:**
- Named exports for multiple sub-components: `export { Card, CardHeader, CardFooter, CardTitle, CardDescription, CardContent }`
- Default exports for page components: `export default Index`, `export default NotFound`
- Both named and default exports used, e.g., `export { useToast, toast }` + top-level `useToast()` hook

**Barrel Files:**
- Not observed in current structure
- Individual component files export their own components

**Discriminated Union Types:**
- Used for reducer actions in `src/hooks/use-toast.ts`:
  ```typescript
  type Action =
    | { type: ActionType["ADD_TOAST"]; toast: ToasterToast }
    | { type: ActionType["UPDATE_TOAST"]; toast: Partial<ToasterToast> }
    | { type: ActionType["DISMISS_TOAST"]; toastId?: string }
    | { type: ActionType["REMOVE_TOAST"]; toastId?: string };
  ```

**State Management Pattern:**
- Reducer pattern with dispatch for toast state management
- Global memory state + listener pattern for synchronization across hook instances
- See `src/hooks/use-toast.ts` for reference implementation

---

*Convention analysis: 2026-02-05*
