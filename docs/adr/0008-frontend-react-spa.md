# ADR-0008: Frontend as a React SPA (Vite)

- Status: Accepted
- Date: 2026-08-30

## Context

`CLAUDE.local.md` says "Next.js etc. SPA" and lists "S3 + CloudFront" for
hosting. The product is an authenticated dashboard: résumé list, job list,
analysis and diff views. There are no public/SEO pages and no server-rendering
needs. Next.js App Router adds RSC, the server/client boundary, and a Node
hosting requirement (or an awkward static export) for benefits this app does not
use.

## Decision

Build the frontend as a client-rendered SPA with **Vite + React + React Router**,
deployed as static assets to S3 behind CloudFront. Data layer: TanStack Query.
Forms: React Hook Form + Zod. API client: types generated from the backend
OpenAPI schema (`openapi-typescript`) with `openapi-fetch`.

## Consequences

- Hosting is a static bucket + CDN — no SSR server, no Node runtime in prod.
- Simple mental model: the SPA talks to the API over `/api` (same origin via
  CloudFront), auth is the session cookie (ADR-0004).
- No SEO / first-paint SSR benefit — irrelevant for an authed tool.
- **Revisit when**: marketing/SEO pages are needed, or per-route SSR/streaming
  becomes valuable → introduce a framework then, likely for a separate public
  surface rather than the app.

## Alternatives considered

- **Next.js App Router** — complexity and a Node host for no benefit here.
- **Next.js static export** — loses much of what makes Next.js worthwhile.
- **Remix / TanStack Start** — same "needs a server" tradeoff as Next.js.
