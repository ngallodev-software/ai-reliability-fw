# ADR-0011: Semantic Versioning with Git Tags as the Release Mechanism

## Status

Accepted

## Date

2026-03-18

## Context

`security-ai-eval-lab` consumes `ai-reliability-fw` via a `file:///` path reference in its `pyproject.toml`. This is fragile: it breaks on any machine where the absolute path differs, makes it impossible to pin a known-good version, and gives the consumer no signal when breaking changes land.

The package also lacked `__init__.py` files in each subpackage, meaning it was not installable as a wheel and could only be used via editable path reference.

## Decision

1. Add `__init__.py` to all `src/` subpackages so the package builds correctly as a wheel.
2. Expose `__version__` in `src/__init__.py` as the single source of truth for the version string.
3. Use [Semantic Versioning](https://semver.org/) (MAJOR.MINOR.PATCH) with the following policy:
   - **PATCH** — bug fixes, internal refactors, no public contract change
   - **MINOR** — additive changes: new validators, new DB columns, new public classes
   - **MAJOR** — breaking changes to `execute()` return shape, removed public API, destructive DB schema changes
4. Releases are cut by: bumping `__version__` + `pyproject.toml version`, updating `CHANGELOG.md`, committing, and pushing a `vX.Y.Z` git tag.
5. Consumers pin via git tag reference: `ai-reliability-fw @ git+ssh://...@vX.Y.Z` or a wheel file, never a `file:///` path.

## Consequences

- `security-ai-eval-lab` (and future consumers) can pin an exact version and know precisely what contract they're on.
- Breaking changes require a MAJOR bump, giving consumers an explicit signal to update their integration.
- The build artifact (wheel) is reproducible from any tag: `python -m build` at that tag produces the same package.
- The `file:///` path reference in `security-ai-eval-lab` must be replaced — see `CHANGELOG.md` for the correct dependency syntax.
- Maintaining discipline on semver bumps is the responsibility of whoever merges to `main`.
