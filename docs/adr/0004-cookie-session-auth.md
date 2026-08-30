# ADR-0004: Authentication via httpOnly cookie sessions

- Status: Accepted
- Date: 2026-08-30

## Context

`CLAUDE.local.md` suggests "Cognito, or app-implemented + RDS". The app holds
highly sensitive data (résumés, job-search activity). The frontend is a
same-origin SPA (ADR-0008, ADR-0003). Tokens kept in `localStorage` are readable
by any XSS and hard to revoke.

## Decision

App-implemented auth:

- Opaque, random session token in a cookie: `HttpOnly`, `Secure`,
  `SameSite=Lax`, `Path=/`.
- Server-side session records in **DynamoDB** with a TTL attribute (auto-expiry,
  serverless, no idle cost — fits ADR-0003).
- Passwords hashed with **argon2id**.
- CSRF defense for state-changing requests (double-submit token or origin check);
  `SameSite=Lax` already blocks the common cross-site cases.
- Email + password first. Google / LinkedIn OAuth added later as additional
  identity providers onto the same session model.

## Consequences

- JS never sees the credential; XSS cannot exfiltrate a long-lived token.
- Revocation = delete the session row; no token-blacklist machinery.
- Requires a shared session store (DynamoDB) — accepted.
- Must implement CSRF protection, which JWT-in-header would have sidestepped.
- Not using Cognito means we own the flows (verification, reset), but also keep
  full control of the UX and avoid its per-MAU pricing and lock-in.

## Alternatives considered

- **JWT access/refresh in JS-accessible storage** — XSS-exfiltratable, awkward
  revocation.
- **JWT in an httpOnly cookie** — removes the storage risk but keeps stateless
  revocation problems; the DynamoDB lookup per request is cheap here.
- **Cognito** — viable, but heavier than a solo project needs and less flexible.
