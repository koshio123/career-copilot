# ADR-0011: Frontend UI and data stack

- Status: Accepted
- Date: 2026-08-31

## Context

ADR-0008 fixed the frontend as a Vite + React SPA and deferred the concrete UI
choice — "design system vs. headless kit" — to Phase 03, when real screens exist.
Phase 03's screens are small (a two-step login form, an app shell). The app is a
private dashboard, not a marketing site, and the developer is a backend engineer
who wants to spend little time on component infrastructure.

## Decision

- **Styling: Tailwind CSS v4** via `@tailwindcss/vite` (zero-config, one CSS
  `@import`). Utility classes, no CSS-in-JS.
- **Components: hand-rolled**, kept in `src/components/`. Reach for a headless
  primitive library (Radix) only when a component needs real accessibility
  behaviour that is tedious to get right — a dialog, combobox, menu. Not before.
- **Routing: React Router v7** in library mode (`<BrowserRouter>` + `<Routes>`),
  not the framework/SSR mode.
- **Server state: TanStack Query v5.** No Redux/Zustand — local component state
  plus Query covers this app.
- **Forms: React Hook Form + Zod** (`@hookform/resolvers`).
- **API client: `openapi-fetch`** over types generated from the backend's
  committed `openapi.json` (`openapi-typescript`). Same-origin, `credentials:
  'include'`, a middleware that echoes the `cc_csrf` cookie into the CSRF header.
- **Error tracking: `@sentry/react`**, a no-op unless `VITE_SENTRY_DSN` is set.

## Consequences

- Almost no UI-infra code to maintain; styling decisions live inline and in a
  handful of `src/components/` primitives.
- No component library's design language or bundle weight is imposed. The cost is
  that anything genuinely interactive (date picker, rich select) is either
  hand-built or pulls in Radix later.
- The API contract is enforced at build time: `backend/openapi.json` is committed
  and CI fails if either it or the generated `src/api/schema.ts` drifts from the
  code.
- Tailwind v4 is young; if it churns, the utility classes are portable and the
  `@tailwindcss/vite` plugin is the only integration point.

## Alternatives considered

- **shadcn/ui** (Radix + Tailwind, copy-in components) — great, but more moving
  parts than the current screens justify; can be adopted incrementally later
  since it is also Tailwind-based.
- **Mantine / Chakra / MUI** — full component kits; impose a design language and
  weight for little gain on a handful of forms.
- **Plain CSS Modules** — fine, but Tailwind is faster for iterating on a
  utilitarian UI and sets a consistent scale.
- **A data router with loaders** — more ceremony than needed; TanStack Query
  already owns fetching.
