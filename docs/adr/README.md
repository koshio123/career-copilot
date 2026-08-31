# Architecture Decision Records

Short, immutable records of decisions with lasting architectural impact and their
rationale. Format: [MADR](https://adr.github.io/madr/)-lite.

## Process

1. Copy `template.md` to `NNNN-title.md` (next number, kebab-case title).
2. Open it as `Proposed` in the PR that implements or motivates it.
3. Merge as `Accepted`. Don't edit an accepted ADR — supersede it with a new one
   and set the old one's status to `Superseded by ADR-XXXX`.

## Index

| # | Title | Status |
|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-monorepo-layout.md) | Monorepo layout | Accepted |
| [0003](0003-api-hosting-lambda-first.md) | API hosting: Lambda + API Gateway first | Accepted |
| [0004](0004-cookie-session-auth.md) | Authentication via httpOnly cookie sessions | Superseded by 0010 |
| [0005](0005-worker-split-lambda-fargate.md) | Async workers split across Lambda and Fargate | Accepted |
| [0006](0006-job-ingestion-hybrid.md) | Job ingestion: ATS API → JSON-LD → LLM hybrid | Accepted |
| [0007](0007-sensitive-data-protection.md) | Sensitive data protection baseline | Accepted |
| [0008](0008-frontend-react-spa.md) | Frontend as a React SPA (Vite) | Accepted |
| [0009](0009-data-model-and-job-dedup.md) | Data model shape and job deduplication | Accepted |
| [0010](0010-auth-email-otp-and-sessions.md) | Authentication via email OTP and server-side sessions | Accepted |
| [0011](0011-frontend-ui-stack.md) | Frontend UI and data stack | Accepted |
