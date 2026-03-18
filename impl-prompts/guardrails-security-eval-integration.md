Guardrails for security-ai-eval-lab integration tasks in ai-reliability-fw:

Do not:
- redesign `PhaseExecutor`
- introduce a generalized orchestration framework
- add DAG/workflow composition features
- add queues, workers, schedulers, or background jobs
- add new persistence concepts just for eval-lab
- copy eval-lab code into ai-reliability-fw
- hard-code eval-lab-specific business logic into validators or repository code
- widen the public API beyond what eval-lab needs for this integration
- rewrite unrelated dirty files or revert existing local changes
- add UI, dashboards, or non-framework product features

Do:
- keep framework changes minimal and backward-safe
- preserve ai-reliability-fw ownership of workflows, prompts, workflow_runs, llm_calls, and escalation_records
- keep shared-database boundaries explicit and loose
- expose only the success metadata needed by eval-lab
- prefer additive or narrowly corrective changes over refactors
- keep imports, session usage, and repository patterns consistent with the current codebase
- make the integration easy to demo and easy to reason about
- verify current behavior before changing code
