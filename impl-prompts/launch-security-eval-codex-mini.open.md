Run the `ai-reliability-fw` repo-local integration pack using `gpt-5.4-mini` subagents.

This launch prompt is isolated to one repo only:
- `/lump/apps/ai-reliability-fw`

Do not create branches, worktrees, edits, or commits in `security-ai-eval-lab` from this prompt.

## Guardrails

- All tasks must follow `/lump/apps/ai-reliability-fw/impl-prompts/guardrails-security-eval-integration.md`.
- Do not let any subagent work directly in the current live working tree.
- Do not reset, discard, or overwrite existing user changes.
- Keep all writes inside `ai-reliability-fw`.

## Preflight

1. Inspect this repo only:
   - current branch
   - `git status --short`
   - whether the expected `impl-prompts` files exist
2. Preserve dirty state before creating worktrees:
   - create one repo-level safety branch from the current branch tip
   - create one local-only WIP preservation commit containing the current dirty state
   - do not push it
3. Create a fresh execution branch from the preserved commit SHA.
4. Create isolated worktrees under `/tmp/codex-worktrees/ai-reliability-fw`.

## Branch names

- Repo-level execution branch: `plan/ai-reliability-fw-security-eval-integration`
- Task branches:
  - `task/t01-contract-alignment`
  - `task/t02-framework-verification`

## Worktree roots

- `/tmp/codex-worktrees/ai-reliability-fw/t01-contract-alignment`
- `/tmp/codex-worktrees/ai-reliability-fw/t02-framework-verification`

## Task registry

- `t01` -> `/lump/apps/ai-reliability-fw/impl-prompts/task-01-contract-and-success-metadata.open.md`
- `t02` -> `/lump/apps/ai-reliability-fw/impl-prompts/task-02-framework-verification.open.md`

Launch order:
- Start `t01` as soon as preflight and worktrees are ready.
- Start `t02` only after `t01` has landed or you have reviewed its diff and can integrate it safely.

## Spawn settings

- Use `spawn_agent` with `agent_type=worker` for both tasks.
- Use model `gpt-5.4-mini`.
- Use `reasoning_effort=high` for both tasks.
- Do not delegate the main orchestration loop. The parent agent owns preflight, worktree creation, integration review, metrics updates, and final verification handling.

## Integration rules

- Review every agent diff before merging it back.
- Merge task results into the repo-level execution branch, not into the original working tree.
- Preserve unrelated local changes.
- If `t02` finds a concrete defect, create one follow-up corrective task row and patch only the minimum required scope in this repo.

## Metrics ledger

Keep this table updated in this file as tasks progress.

| task_id | branch | worktree | agent_id | status | tokens_used | elapsed_seconds | errors_encountered | tests_run | changed_files |
|---|---|---|---|---|---:|---:|---|---|---|
| t01 | task/t01-contract-alignment | /tmp/codex-worktrees/ai-reliability-fw/t01-contract-alignment | pending | pending | 0 | 0 | none | none | none |
| t02 | task/t02-framework-verification | /tmp/codex-worktrees/ai-reliability-fw/t02-framework-verification | pending | pending | 0 | 0 | none | none | none |

Update rules:
- Set status to `running` when an agent starts.
- Set status to `completed` or `blocked` when it finishes.
- Copy `TOKENS_USED`, `ELAPSED_SECONDS`, and `ERRORS_ENCOUNTERED` exactly from the subagent footer.
- Record `TESTS_RUN` and `CHANGED_FILES` exactly as reported.
- If verification spawns a corrective task, append a new row instead of overwriting the original task record.

## Required final state

Before you finish:
- all task rows must be updated in the metrics ledger
- the repo-level execution branch must contain the accepted task changes
- verification must have either no findings or a minimal corrective patch set
- summarize token usage, elapsed time, and errors per task from the ledger
