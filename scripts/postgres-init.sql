-- Runs once on first container start (via /docker-entrypoint-initdb.d).
-- The main database (career_copilot) is created by POSTGRES_DB; this adds the
-- test database that the backend test suite / Alembic expect.
CREATE DATABASE career_copilot_test;
