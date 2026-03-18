# Changelog

All notable changes to `ai-reliability-fw` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

---

## [0.1.0] — 2026-03-18

Initial release. Establishes the core reliability loop consumed by `security-ai-eval-lab`.

### Added
- `PhaseExecutor` — async single-phase orchestrator (validate → call LLM → validate → decide → persist)
- `decision_engine.decide()` — pure function mapping failure categories to RETRY / ESCALATE / COMPLETE
- Validators: `InputIntegrityValidator`, `JsonSchemaValidator`, `ContentValidator`, `SafetyValidator`
- `ReliabilityRepository` — async SQLAlchemy repository with idempotent inserts and read methods
- DB schema: `workflows`, `workflow_runs`, `prompts`, `llm_calls`, `escalation_records`
- Alembic migrations: `0001_initial_schema`, `0002_token_cost_and_content_error`
- `PhaseExecutor.execute()` SUCCESS response now includes full call metadata: `call_id`, `provider`, `model`, `latency_ms`, `input_tokens`, `output_tokens`, `token_cost_usd`
- `src/__init__.py` exposing `__version__ = "0.1.0"` — package now installable as a wheel

---

## Semver policy

| Change type | Version bump | Example |
|---|---|---|
| New public API, new validator, new DB columns (additive) | **MINOR** `0.x.0` | adding a new `FailureCategory` value |
| Breaking change to `execute()` return shape, DB schema destructive change, removed public class | **MAJOR** `x.0.0` | renaming a key in the SUCCESS response dict |
| Bug fix, internal refactor, doc update, no contract change | **PATCH** `0.0.x` | fixing an idempotency bug in `persist_llm_call` |

## Release process

```bash
# 1. Bump version in src/__init__.py and pyproject.toml
# 2. Update CHANGELOG.md — move Unreleased items under a new [x.y.z] heading
# 3. Commit:
git add src/__init__.py pyproject.toml CHANGELOG.md
git commit -m "chore: release v0.x.y"

# 4. Tag:
git tag v0.x.y
git push origin main --tags

# 5. Build wheel (for consumers to install from):
pip install build
python -m build
# produces dist/ai_reliability_fw-0.x.y-py3-none-any.whl
```

## Consuming this package (for security-ai-eval-lab)

Replace the `file://` path reference with a pinned git tag:

```toml
# pyproject.toml in security-ai-eval-lab
dependencies = [
    "ai-reliability-fw @ git+ssh://git@github.com/your-org/ai-reliability-fw.git@v0.1.0",
]
```

Or if installing from a built wheel dropped in a shared directory:

```toml
dependencies = [
    "ai-reliability-fw @ file:///lump/dist/ai_reliability_fw-0.1.0-py3-none-any.whl",
]
```
