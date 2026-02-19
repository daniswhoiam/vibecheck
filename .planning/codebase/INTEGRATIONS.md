# External Integrations

**Analysis Date:** 2026-02-05

## APIs & External Services

**Not Currently Implemented:**
- No external APIs are currently integrated
- TanStack React Query (`@tanstack/react-query` v5.83.0) is configured but not actively used for data fetching
- Infrastructure for API integration is in place but awaiting implementation

## Data Storage

**Databases:**
- None - This is a frontend-only SPA with no backend database

**File Storage:**
- None - No file storage integration configured

**Caching:**
- TanStack React Query (v5.83.0) provides client-side caching infrastructure for future API calls
- In-memory cache management ready to be implemented

**Client-Side State:**
- Local component state via React hooks
- Toast notifications stored in memory via `useToast` hook in `src/hooks/use-toast.ts`

## Authentication & Identity

**Auth Provider:**
- None currently implemented
- No authentication system configured
- No OAuth or login mechanism in place

## Monitoring & Observability

**Error Tracking:**
- None - No error tracking service configured

**Logs:**
- Browser console logging only
- 404 page logs unhandled routes to console in `src/pages/NotFound.tsx`: `console.error("404 Error: User attempted to access non-existent route:", location.pathname)`

## CI/CD & Deployment

**Hosting:**
- Lovable platform (https://lovable.dev/projects/REPLACE_WITH_PROJECT_ID)
- Static SPA deployment capable (can be deployed to Vercel, Netlify, GitHub Pages, AWS S3, etc.)

**CI Pipeline:**
- None configured in repository
- Lovable handles automatic deployments from git commits

**Build Artifacts:**
- Builds to `dist/` directory (Vite standard)

## Environment Configuration

**Environment Variables:**
- None required currently
- No `.env` files present in repository
- Vite supports `VITE_*` prefixed environment variables if needed in future

**Development Server:**
- Vite dev server: localhost:8080 (configured in `vite.config.ts`)
- HMR (Hot Module Replacement) enabled with overlay disabled

## Webhooks & Callbacks

**Incoming:**
- None configured

**Outgoing:**
- None configured

## Frontend Service Dependencies

**Component Library CDN/Network:**
- shadcn-ui components are bundled locally (not CDN-based)
- Radix UI primitives bundled with application
- Lucide icons bundled locally

**Icon Library:**
- Lucide React (v0.462.0) - local SVG icon assets, no external API

**Google Fonts:**
- None explicitly configured
- Uses system fonts or Tailwind CSS defaults

## Future Integration Points

**Ready for Implementation:**
- TanStack React Query is configured for API data fetching (`src/App.tsx` initializes `QueryClient` but no queries exist yet)
- Zod schema validation (`zod` v3.25.76) ready for form and API response validation
- React Hook Form (v7.61.1) configured for form handling

**Recommended Integration Architecture:**
- Use `@tanstack/react-query` for server state management with configured `QueryClient` in `src/App.tsx`
- Create API service functions in `src/lib/api/` or `src/services/`
- Use Zod for schema validation of API responses
- Leverage React Hook Form with Zod resolvers for form validation

## Third-Party UI Component Sources

**shadcn-ui Components Configured:**
- Configuration in `components.json` with aliases pointing to:
  - `@/components` for all component files
  - `@/lib/utils` for utility functions
  - Tailwind CSS base color: slate
  - CSS variables enabled for theme customization

**Pre-built Components Available in `src/components/ui/`:**
- Accordion, Alert Dialog, Aspect Ratio, Avatar, Checkbox
- Collapsible, Context Menu, Dialog, Dropdown Menu, Hover Card
- Label, Menubar, Navigation Menu, Popover, Progress
- Radio Group, Scroll Area, Select, Separator, Slider
- Switch, Tabs, Toast, Toggle, Toggle Group, Tooltip
- Card, Input, Pagination, Resizable, Sheet, Chart

## Development Tool Integrations

**Lovable IDE Integration:**
- lovable-tagger (v1.1.13) component tagging for Lovable UI builder
- Runs in development mode only (configured in `vite.config.ts`)

**Version Control:**
- Git repository for source control
- Lovable auto-commits changes made via its UI

## Summary

This codebase is a **frontend-only SPA with no external integrations currently active**. It provides the infrastructure for future API integration through:
- TanStack React Query for data fetching and caching
- Zod for schema validation
- React Hook Form for form handling
- Fetch API for HTTP requests (not explicitly wrapped yet)

The application is production-ready for static deployment but requires custom development to add:
- Backend API endpoints
- Authentication system
- Database connectivity
- External service integrations

---

*Integration audit: 2026-02-05*
