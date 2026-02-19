# Architecture

**Analysis Date:** 2026-02-05

## Pattern Overview

**Overall:** Component-driven SPA with provider-based dependency injection and routing.

**Key Characteristics:**
- Single Page Application with client-side routing
- UI component library built on Radix UI primitives and shadcn/ui patterns
- Global state management through React Context and React Query
- Layered architecture separating UI, hooks, utilities, and pages

## Layers

**Presentation Layer:**
- Purpose: Render UI components and handle user interactions
- Location: `src/components/` and `src/pages/`
- Contains: React components, UI primitives, page-level components
- Depends on: Hooks layer, utilities, React Router
- Used by: App-level routing, other components

**Hooks Layer:**
- Purpose: Encapsulate stateful logic and side effects
- Location: `src/hooks/`
- Contains: Custom React hooks for state management, side effects, and reusable logic
- Depends on: React, utilities
- Used by: Presentation components

**Utilities Layer:**
- Purpose: Provide shared helper functions and constants
- Location: `src/lib/`
- Contains: Utility functions, styling helpers, type definitions
- Depends on: Third-party libraries (clsx, tailwind-merge)
- Used by: All layers

**Root Application Layer:**
- Purpose: Configure providers, routing, and app-level setup
- Location: `src/App.tsx`, `src/main.tsx`
- Contains: Route definitions, provider configuration, global setup
- Depends on: All lower layers
- Used by: Entry point

## Data Flow

**Page Load & Initialization:**

1. `src/main.tsx` creates React root and renders `<App />`
2. `<App />` in `src/App.tsx` sets up provider hierarchy
3. QueryClientProvider wraps application for server state
4. TooltipProvider and notification components (Toaster, Sonner) are initialized
5. BrowserRouter configures client-side routing
6. Routes match URL to page component

**Component Rendering:**

1. Route matches pathname to page component (`src/pages/Index.tsx`, etc.)
2. Page component can use hooks from `src/hooks/` for local state
3. Components from `src/components/ui/` render styled DOM elements
4. Utilities from `src/lib/` apply styles and helpers

**State Management:**

- **Component State:** React.useState for local component state
- **Server State:** React Query (TanStack Query) for API/server data via QueryClientProvider
- **Global UI State:** Custom hook state management (e.g., useToast uses reducer + context pattern)
- **Router State:** React Router manages navigation and route parameters

**Toast Notification Flow:**

1. Component calls `toast()` function from `src/hooks/use-toast.ts`
2. Action dispatched to global reducer updates `memoryState`
3. Listeners (hook subscribers) notified of state change
4. `useToast()` hook in Toaster component re-renders with new toasts
5. Toaster component renders Toast UI elements

## Key Abstractions

**UI Component Library:**
- Purpose: Provide reusable, styled, accessible components following shadcn/ui patterns
- Examples: `src/components/ui/button.tsx`, `src/components/ui/card.tsx`, `src/components/ui/dialog.tsx`
- Pattern: ForwardRef wrapper components using Radix UI primitives, styled with Tailwind CSS classes

**Custom Hooks:**
- Purpose: Encapsulate reusable stateful logic and side effects
- Examples: `src/hooks/use-toast.ts`, `src/hooks/use-mobile.tsx`
- Pattern: `use-toast` implements reducer pattern with dispatch, listeners, and memory state; `use-mobile` uses effects and media queries

**Page Components:**
- Purpose: Route-level components representing distinct views
- Examples: `src/pages/Index.tsx`, `src/pages/NotFound.tsx`
- Pattern: Functional components that compose UI components and hooks

**Layout & Provider Wrapper:**
- Purpose: Establish global application context and styling
- Location: `src/App.tsx`
- Pattern: Nested provider pattern (QueryClientProvider > TooltipProvider > Toaster > BrowserRouter)

## Entry Points

**Browser Entry:**
- Location: `index.html`
- Triggers: Browser page load
- Responsibilities: Loads HTML shell with root div, imports main.tsx

**React Root:**
- Location: `src/main.tsx`
- Triggers: Module load
- Responsibilities: Creates React root and renders App component

**Application Root:**
- Location: `src/App.tsx`
- Triggers: Rendering from main.tsx
- Responsibilities: Configures providers, sets up routing, defines route structure

**Page Components:**
- Location: `src/pages/*.tsx`
- Triggers: Route match in BrowserRouter
- Responsibilities: Render page-specific UI and composition

## Error Handling

**Strategy:** Declarative routing with NotFound fallback, console logging for diagnostics.

**Patterns:**
- 404 Page: `src/pages/NotFound.tsx` catches unmatched routes via `<Route path="*" />`
- Error Logging: NotFound component logs pathname to console for diagnostics
- Toast System: Applications can use `toast()` function to display user-facing notifications

## Cross-Cutting Concerns

**Styling:**
- Tailwind CSS classes applied directly to components
- Design tokens defined in `src/index.css` using CSS custom properties (HSL color system)
- Utility function `cn()` from `src/lib/utils.ts` merges Tailwind classes and resolves conflicts

**Tooltips & Popovers:**
- Radix UI TooltipProvider wraps entire app in `src/App.tsx` to enable tooltip components

**Notifications:**
- Toaster component displays toast notifications from `src/hooks/use-toast.ts`
- Sonner provides alternative notification UI

**Routing:**
- React Router v6 with declarative Route definitions in `src/App.tsx`
- Query-based routing (URL parameters) supported via React Router's useSearchParams

**Form Handling:**
- React Hook Form (`react-hook-form`) and Zod validation available via dependencies
- Not yet integrated into default pages

---

*Architecture analysis: 2026-02-05*
