# ADR-0001: Use PostgreSQL with SQLAlchemy Async as the Persistence Stack

## Status

Accepted

## Date

2026-03-16

## Context

The framework needs durable, queryable persistence for workflow runs, LLM calls, and escalation records. LLM calls are async by nature; blocking the event loop on DB I/O would create a bottleneck.

## Decision

Use PostgreSQL as the database and SQLAlchemy 2.x with the `asyncpg` driver as the ORM. All DB operations are `async`/`await`.

## Consequences

- DB I/O never blocks the async event loop.
- SQLAlchemy's declarative ORM provides typed models and handles dialect differences.
- `asyncpg` is Postgres-only — switching databases would require a driver change.
- Local dev requires Docker (`docker-compose.yml` provides a Postgres container).
