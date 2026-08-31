# ADR-0010: Authentication via email OTP and server-side sessions

- Status: Accepted
- Date: 2026-08-31
- Supersedes: [ADR-0004](0004-cookie-session-auth.md)

## Context

ADR-0004 chose app-implemented email + password auth with an opaque session
cookie backed by DynamoDB. Revisiting before Phase 02:

- **Passwords are the largest security-critical surface in the app**: hashing,
  reset request + token issue/store/email, breach-password checks, enumeration
  resistance, login rate-limiting, lockout tuning, "change password kills other
  sessions". Every mistake is an incident, and this is a solo project.
- For this product's reference class — a developer tool / startup SaaS whose
  users are job-seeking engineers — **passwordless is the mainstream default**,
  and greenfield best-practice guidance (Stytch, Clerk, WorkOS, Auth0) is
  "passkeys primary, email OTP / magic link as fallback, password optional".
- The frontend is a **same-origin SPA** (CloudFront routes `/api/*` → API
  Gateway, `/` → S3), so `SameSite=Lax` cookies work with no CORS-credentials
  dance and the CSRF surface is small.
- DynamoDB at this scale is **effectively free** (always-free tier is 25 GB +
  25 provisioned WCU/RCU ≈ 200M req/mo; on-demand is fractions of a cent for one
  user, single-digit cents for a small user base; TTL deletes are free), so
  cost is not a reason to avoid it.

## Decision

### First factor: email 6-digit OTP. No passwords.

- User enters email → server emails a 6-digit code.
- Code: cryptographically random, **10-minute TTL**, one active code per email,
  **only its hash stored** (SHA-256), **max 5 verify attempts** then invalidated.
- `POST /auth/otp/request` always returns `202` regardless of whether the email
  exists (no account enumeration). First successful verify also sets
  `email_verified_at` and creates the user if new.
- An `otp_challenge` cookie is set on request and required on verify (binds the
  ceremony to one browser).
- Rate limited per email **and** per source IP; API Gateway throttling is the
  coarse backstop.
- Delivery: Amazon SES in the cloud; console / MailHog locally.
- The Phase 01 `users.password_hash` column is dropped in the Phase 02 migration;
  `argon2-cffi` is removed from dependencies. Re-adding a password credential
  later is a small additive change.

### Session: opaque token in an httpOnly cookie (unchanged from ADR-0004)

- 256-bit random token; cookie is `HttpOnly; Secure; SameSite=Lax; Path=/`.
- Server-side record; **only the token hash is stored**.
- 30-day expiry, sliding (extended on use); the `last_seen_at` / TTL write is
  throttled to ~once/hour so steady traffic costs ~zero writes.
- `GET/DELETE /auth/sessions` lets a user list and revoke sessions; logout and
  "revoke all" delete the record(s) — instant, no token-blacklist machinery.

### Store: DynamoDB, on-demand, TTL-cleaned

Behind `SessionStore` / `OtpStore` interfaces so a move to Postgres or Redis is
localised.

| table | key | attributes | TTL |
|---|---|---|---|
| `sessions` | `pk = token_hash` | `user_id`, `created_at`, `expires_at`, `last_seen_at`, `ua`, `ip` | `expires_at` |
| `otp_codes` | `pk = email_hash` | `code_hash`, `attempts`, `created_at` | 10 min |
| `auth_rate_limits` | `pk` (`email#…` / `ip#…`) | `count` (atomic `ADD`) | window |

On-demand billing (no capacity planning); provisioned 5/5 within the always-free
tier is the fallback for a hard $0 guarantee.

### CSRF

`SameSite=Lax` + JSON-only API (reject form-encoded) + a double-submit token on
state-changing requests. No state-changing `GET`s.

### Authorization (unchanged)

Every query is scoped to the authenticated user. A repository base class requires
a `user_id`, so "forgot the `WHERE user_id =`" is a type error, not a leak.
Postgres RLS as a DB-level backstop is a Phase 09 consideration (own ADR if
adopted).

### Later, additively

Passkeys (WebAuthn) as the fast daily-login path — OTP stays as the recovery
path. Then Google / LinkedIn OAuth as extra identity providers onto the same
session model.

## Consequences

- The password attack surface — reset flow, hashing, HIBP, lockout, enumeration —
  simply does not exist.
- **Email deliverability becomes a hard dependency**: SES domain setup,
  SPF/DKIM/DMARC, bounce/complaint handling. Login latency tracks mail latency.
- Email-account compromise grants app access — true of every email-recovery
  system; OTP does not make it worse.
- One new infra piece (DynamoDB tables: Terraform module + LocalStack), accepted;
  cost is effectively $0 and TTL cleanup is free.
- SHA-256 + constant-time compare is correct here (session tokens are 256-bit
  random; OTP is protected by rate-limit + attempt cap + short TTL, not hash
  cost) — no argon2 needed.

## Alternatives considered

- **Password + argon2 (ADR-0004)** — more code, all of it security-critical;
  passwordless is the modern default for this product class.
- **Magic link** — equivalent security; email OTP chosen for deliverability and
  UX (links break in mail scanners, some clients, in-app browsers).
- **Passkey-first now** — better end state, more ceremony to build up front; OTP
  first, passkey as a fast-follow, OTP remains recovery.
- **Postgres session store** — zero new infra and viable, but cost was the only
  argument against DynamoDB and it does not apply; keeping DynamoDB also keeps
  auth-transient state off the primary DB.
- **Cognito / Clerk / WorkOS / self-hosted IdP** — rejected in ADR-0004's
  analysis (clunky / vendor lock-in / per-MAU cost / always-on infra); unchanged.
