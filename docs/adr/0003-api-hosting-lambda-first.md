# ADR-0003: API hosting — Lambda + API Gateway first

- Status: Accepted
- Date: 2026-08-30

## Context

`CLAUDE.local.md` allows "ECS Fargate or Lambda + API Gateway". The first user is
the developer alone; traffic is near zero with occasional bursts (a crawl batch
completing, a résumé analysis). An always-on Fargate task + ALB costs roughly
US$30–45/month at idle. FastAPI runs on Lambda via AWS Lambda Web Adapter or
Mangum with sub-second cold starts for a small app.

## Decision

Deploy the API as a Lambda function behind API Gateway (HTTP API), using the
Lambda Web Adapter so the same ASGI app runs unchanged locally and in the cloud.
CloudFront sits in front: `/api/*` → API Gateway, everything else → the SPA
bucket, giving the frontend a same-origin API.

## Consequences

- Idle cost is effectively zero; pay per request.
- No load balancer, no always-on container, simpler ops.
- Cold starts (~0.5–1s) are acceptable for a personal dashboard.
- Long-running work must not happen in the request path — it already goes to
  workers (ADR-0005).
- **Revisit when**: sustained traffic, websockets/SSE, response streaming needs,
  or cold starts become a felt problem → move the API to Fargate + ALB. The
  ASGI-app-behind-adapter shape makes that a deployment change, not a rewrite.

## Alternatives considered

- **Fargate + ALB from day one** — better for steady traffic, wasteful here.
- **App Runner** — simpler than Fargate but still always-on billing.
