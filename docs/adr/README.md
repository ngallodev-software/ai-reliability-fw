# Architecture Decision Records

This directory contains Architecture Decision Records for `ai-reliability-fw`.

The numbered ADRs follow the Nygard template:
- `Status`
- `Date`
- `Context`
- `Decision`
- `Consequences`

`ADR.md` is a rolling architecture summary for the repository. The numbered files are the canonical decision records.

## Index

| ADR | Title | Status | Date |
|---|---|---|---|
| [ADR-0001](./0001-postgresql-sqlalchemy-async-persistence.md) | Use PostgreSQL with SQLAlchemy Async as the Persistence Stack | Accepted | 2026-03-16 |
| [ADR-0002](./0002-alembic-for-migrations.md) | Use Alembic for Schema Migrations | Accepted | 2026-03-16 |
| [ADR-0003](./0003-six-layer-unidirectional-architecture.md) | Six-Layer Unidirectional Architecture | Accepted | 2026-03-16 |
| [ADR-0004](./0004-deterministic-uuid5-call-ids.md) | Deterministic UUID5 for LLM Call IDs | Accepted | 2026-03-16 |
| [ADR-0005](./0005-on-conflict-do-nothing-idempotent-inserts.md) | ON CONFLICT DO NOTHING for Idempotent Inserts | Accepted | 2026-03-16 |
| [ADR-0006](./0006-validators-list-ordering-convention.md) | `validators[0]` Is Always the Input Validator | Accepted | 2026-03-16 |
| [ADR-0007](./0007-pure-function-decision-engine.md) | Decision Engine as a Pure Function | Accepted | 2026-03-16 |
| [ADR-0008](./0008-no-phases-table-phase-id-as-opaque-uuid.md) | No `phases` Table, `phase_id` Is a Caller-Supplied Opaque UUID | Accepted | 2026-03-16 |
| [ADR-0009](./0009-manual-constructor-dependency-injection.md) | Manual Constructor Dependency Injection | Accepted | 2026-03-16 |
| [ADR-0010](./0010-environment-variable-only-configuration.md) | Environment Variables as the Only Configuration Mechanism | Accepted | 2026-03-16 |
| [ADR-0011](./0011-phase-executor-llm-call-contract.md) | PhaseExecutor Owns the LLM Call Contract and Success Metadata | Accepted | 2026-03-17 |
