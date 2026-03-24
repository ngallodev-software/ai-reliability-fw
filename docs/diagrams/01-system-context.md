# System Context Diagram

`ai-reliability-fw` is a Python library/framework that wraps any async LLM client
with structured validation, retry logic, escalation handling, and full DB persistence.
It is consumed by `/lump/apps/security-ai-eval-lab` as the LLM execution control plane.

```mermaid
C4Context
    title ai-reliability-fw — System Context

    Person(dev, "Developer / Integrator", "Wires up PhaseExecutor with a LLM client, validators, and retry policy. Calls execute() per LLM phase.")
    Person(ops, "Operator", "Monitors workflow_runs, llm_calls, and escalation_records. Investigates failures.")

    System_Boundary(fw, "ai-reliability-fw") {
        System(engine, "PhaseExecutor + DecisionEngine", "Orchestrates a single LLM phase: input validation → LLM call → output validation → retry/escalate decision.")
        System(validators, "Validator Chain", "Pre-call and post-call validators: InputIntegrity, JsonSchema, Content, Safety.")
        System(repo, "ReliabilityRepository", "Async SQLAlchemy repository. Persists workflows, runs, prompts, LLM calls, and escalation records.")
        SystemDb(pg, "PostgreSQL (reliability schema)", "Structured audit log of every LLM call attempt, outcome, token cost, and escalation event.")
    }

    System_Ext(llm, "LLM Provider", "Any async client implementing call(prompt, model=None). Production: Anthropic/OpenAI API. Tests: FakeLLMClient.")
    System_Ext(caller, "Caller / Orchestrator", "Manages Workflow, WorkflowRun, and Prompt rows. Calls PhaseExecutor.execute() per phase.")
    System_Ext(eval, "security-ai-eval-lab", "Calls PhaseExecutor via PhaseExecutorAdapter; stores evaluation tables with reliability UUID references.")

    Rel(dev, caller, "Implements")
    Rel(caller, engine, "execute(run_id, phase_id, prompt_id, artifact, retry_policy)")
    Rel(engine, validators, "validate(artifact)")
    Rel(engine, llm, "call(prompt, model=None)")
    Rel(engine, repo, "persist_llm_call, create_escalation, update_run_status")
    Rel(repo, pg, "SQLAlchemy async / asyncpg")
    Rel(ops, pg, "Direct query or monitoring tool")
    Rel(eval, caller, "Adapter wires inputs/outputs + reliability IDs")
```
