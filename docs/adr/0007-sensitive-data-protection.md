# ADR-0007: Sensitive data protection baseline

- Status: Accepted
- Date: 2026-08-30

## Context

Résumés, work history, and job-search activity are sensitive personal data. An
earlier plan draft defaulted to application-layer column encryption (KMS
envelope). That breaks search/sort/indexing, complicates key rotation, is easy to
get subtly wrong, and gives little marginal protection here: the app decrypts
this data on nearly every request to run LLM analysis on it, and each user only
ever accesses their own rows.

## Decision

Baseline controls, applied everywhere:

- RDS encryption at rest (KMS); S3 buckets SSE-KMS; TLS on every hop.
- Least-privilege IAM and security groups; RDS in private subnets.
- PII never written to logs or LLM prompts beyond what a task strictly needs.
- Explicit retention limits; hard delete on account closure.
- Row-level authorization: every query is scoped to the authenticated user.

Application-layer field encryption is **not** the default. It is considered only
for a narrow set of fields (e.g. contact details) and only via its own ADR that
states the threat it addresses.

## Consequences

- Standard query patterns keep working; no encryption-aware data layer.
- Protects against lost disks, snapshot leaks, and bucket misconfiguration — not
  against a fully compromised application host (which column encryption would
  also largely fail to stop, given runtime decryption).
- If a specific regulatory or threat requirement appears, revisit with a
  field-level ADR rather than reworking the whole schema.

## Alternatives considered

- **App-layer column encryption by default** — high complexity, low marginal
  benefit for this workload.
- **pgcrypto in the database** — keys transit the DB, still breaks indexing,
  limited threat-model gain.
