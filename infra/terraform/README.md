# Terraform

AWS infrastructure. Populated from Phase 10 (`docs/development-plan.md`).

Planned module layout:

```
modules/
  network/     VPC, subnets, security groups
  database/    RDS for PostgreSQL
  queue/       SQS queues + DLQs
  api/         Lambda + API Gateway (HTTP API)  [→ Fargate + ALB later]
  workers/     Lambda (SQS ESM) + Fargate worker service
  storage/     S3 buckets (résumés, raw HTML)
  frontend/    S3 + CloudFront (SPA; /api/* → API Gateway)
  scheduler/   EventBridge Scheduler → dispatcher Lambda
  sessions/    DynamoDB session table
envs/
  dev/         the only environment until public launch
```

State: S3 backend (`backend.hcl` per env). Secrets: SSM Parameter Store
(SecureString) initially — see ADR-0003.
