# ADR-0010: Environment Variables as the Only Configuration Mechanism

## Status

Accepted

## Date

2026-03-16

## Context

The framework needs to be configurable across local dev, CI, and production without shipping environment-specific config files. YAML/TOML config files add parsing complexity; a settings class adds another abstraction layer.

## Decision

All runtime configuration is read from environment variables. The only current variable is `DATABASE_URL` (default: `postgresql+asyncpg://user:pass@localhost:5432/reliability_fw`). A `.env` file can be used locally; in production, variables are exported in the shell environment.

## Consequences

- No config file format to define or parse.
- Works natively with Docker, Docker Compose, and CI environment injection.
- Secrets (DB credentials) are kept out of source control.
- There is no validation of env vars at startup — misconfiguration surfaces as a runtime connection error, not an early startup failure.
