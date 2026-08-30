# LocalStack root module

A slim Terraform root that provisions only what local development needs in
LocalStack: SQS queues and S3 buckets. No VPC/RDS/ECS.

Added in Phase 04 alongside the async worker. Applied with `tflocal` (the
LocalStack Terraform wrapper). Postgres for local dev comes from
`docker-compose.yml`, not from here.
