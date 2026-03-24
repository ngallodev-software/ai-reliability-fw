# Database Schema — ER Diagram

PostgreSQL `reliability` schema. All tables use `reliability.` as the schema prefix.

```mermaid
erDiagram

    workflows {
        UUID workflow_id PK "uuid4"
        String name "NOT NULL"
        String version "NOT NULL"
        JSONB definition_json "NOT NULL"
    }

    workflow_runs {
        UUID run_id PK "uuid4"
        UUID workflow_id FK
        Enum status "RUNNING|COMPLETED|FAILED|ESCALATED|REPLAYING"
        DateTime created_at
    }

    prompts {
        UUID prompt_id PK "uuid4"
        Text content "NOT NULL"
        String prompt_hash "unique — deduplication key"
        String version_tag "NOT NULL"
    }

    llm_calls {
        UUID call_id PK "uuid5 DETERMINISTIC\n= uuid5(run_id:phase_id:prompt_id:attempt_num)"
        UUID run_id FK
        UUID phase_id "no FK — caller-owned opaque grouping key"
        UUID prompt_id FK
        String provider "NOT NULL"
        String model "NOT NULL"
        Integer retry_attempt_num "default 0"
        Enum failure_category "nullable — first failure category if any"
        Integer latency_ms
        Text response_raw
        Integer input_tokens "nullable"
        Integer output_tokens "nullable"
        Float token_cost_usd "nullable"
        DateTime created_at
    }

    escalation_records {
        UUID escalation_id PK "uuid4"
        UUID run_id FK
        UUID phase_id "no FK — caller-owned"
        UUID llm_call_id FK "nullable — absent for pre-call escalations"
        Integer retry_attempt_num "NOT NULL"
        Enum failure_category "NOT NULL"
        String trigger_reason "max 500 chars"
        DateTime escalated_at
    }

    workflows ||--o{ workflow_runs : "has"
    workflow_runs ||--o{ llm_calls : "produces (one per attempt)"
    workflow_runs ||--o{ escalation_records : "triggers"
    prompts ||--o{ llm_calls : "used by"
    llm_calls ||--o| escalation_records : "may cause"
```

## Key Schema Decisions

| Decision | ADR | Rationale |
|---|---|---|
| Deterministic `call_id` via uuid5 | ADR-0004 | Replaying same inputs deduplicates silently — idempotent by design |
| `ON CONFLICT DO NOTHING` on all persists | ADR-0005 | Safe to replay without coordination or duplicate rows |
| No `phases` table — `phase_id` is opaque UUID | ADR-0008 | Keeps schema simple; no phase-level metadata needed for MVP |
| `reliability` schema namespace | ADR-0003 | Isolates fw tables from caller's application schema |
