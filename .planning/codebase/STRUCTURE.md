# Codebase Structure

**Analysis Date:** 2026-02-05

## Directory Layout

```
vibecheck/
├── public/                 # Static assets served as-is
├── src/                    # Source code (TypeScript/React)
│   ├── components/         # Reusable React components
│   │   ├── ui/            # Shadcn/UI primitive components
│   │   └── NavLink.tsx    # Custom router-compatible NavLink
│   ├── pages/             # Page/route-level components
│   ├── hooks/             # Custom React hooks
│   ├── lib/               # Utility functions and helpers
│   ├── test/              # Test files and test setup
│   ├── App.tsx            # Root application component
│   ├── main.tsx           # React root and DOM mount
│   └── index.css          # Global styles and design tokens
├── index.html             # HTML entry point
├── vite.config.ts         # Vite build configuration
├── vitest.config.ts       # Vitest testing configuration
├── tsconfig.json          # TypeScript configuration (root)
├── tsconfig.app.json      # TypeScript configuration (app)
├── tsconfig.node.json     # TypeScript configuration (build tools)
├── eslint.config.js       # ESLint configuration
├── package.json           # NPM dependencies and scripts
└── .planning/             # GSD planning documents
```

## Directory Purposes

**public/:**
- Purpose: Static assets served directly by the web server
- Contains: Favicon, robots.txt, placeholder images
- Key files: `favicon.ico`, `placeholder.svg`, `robots.txt`

**src/:**
- Purpose: All application source code
- Contains: React components, hooks, pages, utilities, styles, tests
- Key files: `main.tsx` (entry), `App.tsx` (app root), `index.css` (styles)

**src/components/:**
- Purpose: Reusable React components
- Contains: UI primitives and custom components
- Key files: `ui/` directory with shadcn/ui components, `NavLink.tsx` wrapper

**src/components/ui/:**
- Purpose: Shadcn/UI component library built on Radix UI
- Contains: 50+ accessible, styled components (Button, Card, Dialog, etc.)
- Key files: `button.tsx`, `card.tsx`, `dialog.tsx`, `toaster.tsx`, `use-toast.ts`
- Pattern: Each component exports ForwardRef wrapper, display names, and type props

**src/pages/:**
- Purpose: Page/route-level components representing full views
- Contains: Top-level components rendered by React Router
- Key files: `Index.tsx` (home page), `NotFound.tsx` (404 page)

**src/hooks/:**
- Purpose: Custom React hooks for reusable stateful logic
- Contains: Hooks for state management, effects, and utilities
- Key files: `use-toast.ts` (toast notifications), `use-mobile.tsx` (responsive design)

**src/lib/:**
- Purpose: Utility functions and helper code
- Contains: Shared functions, styling helpers, type utilities
- Key files: `utils.ts` (cn() function), can expand for other utilities

**src/test/:**
- Purpose: Test files and testing configuration
- Contains: Test suites and test setup files
- Key files: `setup.ts` (vitest setup), `example.test.ts` (example test)

## Key File Locations

**Entry Points:**
- `index.html`: HTML shell with root div and script tag
- `src/main.tsx`: React root creation and DOM mount point
- `src/App.tsx`: Application component with providers and routing

**Configuration:**
- `vite.config.ts`: Build, dev server, and path alias configuration
- `vitest.config.ts`: Test runner, environment, and include patterns
- `tsconfig.json`: TypeScript compiler root configuration with path aliases
- `tsconfig.app.json`: TypeScript app-specific settings (target ES2020, JSX)
- `eslint.config.js`: ESLint rules and plugin configuration

**Core Logic:**
- `src/App.tsx`: Routing, provider setup
- `src/pages/Index.tsx`: Home page (blank scaffold)
- `src/pages/NotFound.tsx`: 404 error page with routing info

**Styling:**
- `src/index.css`: Tailwind CSS directives and design token CSS variables
- Design tokens: Colors in HSL format (background, foreground, primary, secondary, etc.)

**UI Components:**
- `src/components/ui/button.tsx`: Base button with variants
- `src/components/ui/card.tsx`: Card container with header/footer/content
- `src/components/ui/toaster.tsx`: Toast notification renderer
- `src/components/ui/dialog.tsx`: Modal dialog component
- `src/components/ui/[40+ others]`: Full component library

**Hooks & State:**
- `src/hooks/use-toast.ts`: Global toast notification state and API
- `src/hooks/use-mobile.tsx`: Responsive design detection (viewport < 768px)
- `src/components/ui/use-toast.ts`: Re-export from hooks (some components expect it here)

**Utilities:**
- `src/lib/utils.ts`: `cn()` function combining clsx and tailwind-merge
- Expands to hold common functions, validators, formatters, etc.

**Testing:**
- `src/test/setup.ts`: Vitest environment setup (matchMedia mock)
- `src/test/example.test.ts`: Example test using vitest and expect

## Naming Conventions

**Files:**
- Components: PascalCase (e.g., `Button.tsx`, `NavLink.tsx`, `Index.tsx`)
- Utilities: camelCase (e.g., `utils.ts`, `setup.ts`)
- Hooks: `use[Feature].ts[x]` (e.g., `use-toast.ts`, `use-mobile.tsx`)
- Config: kebab-case (e.g., `vite.config.ts`, `vitest.config.ts`)

**Directories:**
- Plural nouns for collections: `components`, `pages`, `hooks`, `utils` (lib/), `test`
- Single noun for feature: `ui` (component library), `lib` (utilities)

**Exports:**
- Named exports for components and hooks
- Default export for page components (used by React Router)
- Display names set on ForwardRef components for debugging

## Where to Add New Code

**New Page/Route:**
- Primary code: `src/pages/[PageName].tsx`
- Add route to `src/App.tsx` in Routes element
- Import page: `import [PageName] from "./pages/[PageName]"`

**New Reusable Component:**
- If UI primitive: `src/components/ui/[ComponentName].tsx`
- If domain-specific: `src/components/[ComponentName].tsx`
- Export with ForwardRef if accepting DOM refs

**New Custom Hook:**
- Location: `src/hooks/use[HookName].ts` or `.tsx`
- Export hook function and any related types

**New Utility Function:**
- Location: `src/lib/[domain].ts` (create new file by domain/purpose)
- Example: `src/lib/validation.ts` for validation helpers, `src/lib/formatting.ts` for formatters

**New Test:**
- Location: `src/test/[subject].test.ts` or place test file near source (e.g., `src/lib/utils.test.ts`)
- Pattern: Use vitest and testing-library
- Import: `import { describe, it, expect } from "vitest"`

## Special Directories

**.planning/:**
- Purpose: GSD codebase analysis and planning documents
- Generated: Yes, by GSD commands
- Committed: Yes
- Contains: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, etc.

**.claude/:**
- Purpose: Claude agent context and memory
- Generated: Yes, by Claude agent
- Committed: Yes
- Contents: Agent decision logs and context

**node_modules/:**
- Purpose: Installed npm dependencies
- Generated: Yes, by npm install
- Committed: No (.gitignore)

**dist/:**
- Purpose: Production build output
- Generated: Yes, by `npm run build`
- Committed: No (.gitignore implied by vite.config.ts)

**.git/:**
- Purpose: Git repository metadata
- Generated: Yes, by git init
- Committed: N/A (git's internal directory)

---

*Structure analysis: 2026-02-05*
