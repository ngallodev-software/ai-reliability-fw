# ADR-0002: Use Alembic for Schema Migrations

## Status

Accepted

## Date

2026-03-16

## Context

The schema will evolve (new columns, new enum values, indexes). Ad-hoc SQL scripts are error-prone and hard to roll back.

## Decision

Use Alembic with sequentially numbered migration files (`0001_`, `0002_`, …) in `migrations/versions/`. Every migration must implement both `upgrade()` and `downgrade()`.

## Consequences

- Schema changes are versioned, reproducible, and reversible.
- Developers run `alembic upgrade head` after pulling; CI can validate schema state.
- Alembic must be kept in sync with SQLAlchemy models — drift causes runtime errors.
