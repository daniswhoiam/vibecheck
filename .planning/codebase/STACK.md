# Technology Stack

**Analysis Date:** 2026-02-05

## Languages

**Primary:**
- TypeScript 5.8.3 - Application code, components, hooks, utilities
- JavaScript - Configuration files (vite.config.ts, eslint.config.js, tailwind.config.ts, postcss.config.js)

**Secondary:**
- HTML - Static markup in `index.html`
- CSS - Tailwind CSS in `src/index.css`

## Runtime

**Environment:**
- Node.js 20.11.0 (required for development)

**Package Manager:**
- npm 10.6.0
- Lockfile: `package-lock.json` present (also `bun.lockb` for Bun package manager alternative)

## Frameworks

**Core:**
- React 18.3.1 - UI framework for components and pages
- React DOM 18.3.1 - DOM rendering
- React Router DOM 6.30.1 - Client-side routing (`react-router-dom`)
- Vite 5.4.19 - Build tool and development server

**UI Component Library:**
- shadcn-ui - Pre-built component library based on Radix UI and Tailwind CSS
- Radix UI 1.x - Unstyled, accessible component primitives (accordion, alert-dialog, avatar, checkbox, dialog, dropdown-menu, select, tabs, toast, and 15+ more)

**CSS & Styling:**
- Tailwind CSS 3.4.17 - Utility-first CSS framework
- PostCSS 8.5.6 - CSS transformation tool
- Autoprefixer 10.4.21 - Vendor prefix automation
- tailwindcss-animate 1.0.7 - Animation utilities
- tailwind-merge 2.6.0 - Merge utility class names without conflicts

**Theming:**
- next-themes 0.3.0 - Dark mode and theme management

**Data Visualization:**
- Recharts 2.15.4 - Chart and graph components

**Form Handling:**
- React Hook Form 7.61.1 - Form state management
- @hookform/resolvers 3.10.0 - Schema validation support for RHF
- Zod 3.25.76 - TypeScript-first schema validation

**State Management & Data Fetching:**
- TanStack React Query 5.83.0 - Server state management and data fetching

**UI Utilities:**
- clsx 2.1.1 - Conditional class name builder
- class-variance-authority 0.7.1 - Component variant management
- cmdk 1.1.1 - Command menu component
- date-fns 3.6.0 - Date manipulation and formatting
- lucide-react 0.462.0 - Icon library (SVG icons as components)
- react-day-picker 8.10.1 - Date picker component
- embla-carousel-react 8.6.0 - Carousel/slider library
- input-otp 1.4.2 - OTP (One-Time Password) input component
- react-resizable-panels 2.1.9 - Resizable panel layout
- sonner 1.7.4 - Toast notification library
- vaul 0.9.9 - Drawer/modal component

## Testing

**Framework:**
- Vitest 3.2.4 - Unit test runner and framework
- @testing-library/react 16.0.0 - React component testing utilities
- @testing-library/jest-dom 6.6.0 - DOM matchers for assertions
- jsdom 20.0.3 - JavaScript DOM implementation for testing

## Build & Development Tools

**Build:**
- @vitejs/plugin-react-swc 3.11.0 - Vite plugin using SWC for React Fast Refresh

**Linting & Code Quality:**
- ESLint 9.32.0 - JavaScript/TypeScript linter
- @eslint/js 9.32.0 - ESLint JavaScript config
- typescript-eslint 8.38.0 - TypeScript linting support
- eslint-plugin-react-hooks 5.2.0 - React Hooks linting rules
- eslint-plugin-react-refresh 0.4.20 - React Fast Refresh validation

**Development Utilities:**
- lovable-tagger 1.1.13 - Component tagging utility for Lovable integration

**Type Definitions:**
- @types/react 18.3.23 - React type definitions
- @types/react-dom 18.3.7 - React DOM type definitions
- @types/node 22.16.5 - Node.js type definitions
- globals 15.15.0 - Global variable type definitions

## Configuration Files

**TypeScript:**
- `tsconfig.json` - Main TypeScript configuration with baseUrl and path aliases
- `tsconfig.app.json` - Application-specific TypeScript settings (strict: false)
- `tsconfig.node.json` - Configuration for Node.js scripts

**Build:**
- `vite.config.ts` - Vite configuration with React SWC plugin, path alias for `@/`, and dev server settings (port 8080)
- `vitest.config.ts` - Vitest configuration with jsdom environment and test file patterns

**Styling:**
- `tailwind.config.ts` - Tailwind CSS theme customization
- `postcss.config.js` - PostCSS configuration with Tailwind and Autoprefixer

**Code Quality:**
- `eslint.config.js` - ESLint configuration with TypeScript support and React hooks rules
- `.eslintignore` or eslintignore in config - Ignores dist directory

**Component Library:**
- `components.json` - shadcn-ui configuration with path aliases and Tailwind settings

**Markup:**
- `index.html` - Main HTML entry point

## Development & Build Commands

```bash
npm run dev          # Start Vite dev server (localhost:8080)
npm run build        # Production build
npm run build:dev    # Development build
npm run preview      # Preview production build
npm run lint         # Run ESLint
npm test             # Run tests once (Vitest)
npm test:watch       # Run tests in watch mode
```

## Environment & Deployment

**Development:**
- Local development requires Node.js 20.x and npm
- Hot Module Replacement (HMR) enabled in Vite with overlay disabled
- Development server runs on port 8080

**Production:**
- Static SPA (Single Page Application) deployment
- Builds to `dist/` directory
- Can be deployed to any static hosting (Netlify, Vercel, GitHub Pages, etc.)
- Lovable platform integration for deployment and publishing

## Path Aliases

All source files use `@/` alias pointing to `src/`:
- `@/components` → `src/components`
- `@/ui` → `src/components/ui`
- `@/hooks` → `src/hooks`
- `@/lib` → `src/lib`

## Key Architectural Characteristics

**Module Type:**
- ECMAScript modules (type: "module" in package.json)

**Code Organization:**
- Components: Radix UI + Tailwind CSS based component library
- Hooks: Custom React hooks (`use-toast`, `use-mobile`)
- Utils: Helper functions for CSS class merging
- Pages: Page-level components with routing
- UI: Pre-built shadcn-ui components

**No Backend Runtime:**
- Frontend-only SPA application
- Client-side routing only (React Router)
- Data fetching would use TanStack Query (configured but not yet implemented with APIs)

---

*Stack analysis: 2026-02-05*
