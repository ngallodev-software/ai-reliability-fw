# ai-reliability-fw — Diagrams

---

## 1. Entity-Relationship Diagram (Database Schema)

```mermaid
erDiagram
    workflows {
        UUID workflow_id PK
        String name
        String version
        JSONB definition_json
    }

    workflow_runs {
        UUID run_id PK
        UUID workflow_id FK
        Enum status
        DateTime created_at
    }

    prompts {
        UUID prompt_id PK
        Text content
        String prompt_hash UK
        String version_tag
    }

    llm_calls {
        UUID call_id PK "uuid5 deterministic"
        UUID run_id FK
        UUID phase_id "no FK — caller-owned"
        UUID prompt_id FK
        String provider
        String model
        Integer retry_attempt_num
        Enum failure_category "nullable"
        Integer latency_ms
        Text response_raw
        Integer input_tokens "nullable"
        Integer output_tokens "nullable"
        Float token_cost_usd "nullable"
        DateTime created_at
    }

    escalation_records {
        UUID escalation_id PK
        UUID run_id FK
        UUID phase_id "no FK — caller-owned"
        UUID llm_call_id FK "nullable"
        Integer retry_attempt_num
        Enum failure_category
        String trigger_reason
        DateTime escalated_at
    }

    workflows ||--o{ workflow_runs : "has"
    workflow_runs ||--o{ llm_calls : "produces"
    workflow_runs ||--o{ escalation_records : "triggers"
    prompts ||--o{ llm_calls : "used by"
    llm_calls ||--o| escalation_records : "may cause"
```

---

## 2. Class Diagram (Domain Model)

```mermaid
classDiagram

    %% ── Enums ────────────────────────────────────────────────
    class FailureCategory {
        <<enumeration>>
        SCHEMA_VIOLATION
        HALLUCINATION_SIGNAL
        MISSING_REQUIRED_FIELD
        SAFETY_FLAG
        TIMEOUT
        PROVIDER_ERROR
        HUMAN_ESCALATED
        VALIDATION_FAILURE
        INPUT_VALIDATION_ERROR
        OUTPUT_CONTENT_ERROR
    }

    class RunStatus {
        <<enumeration>>
        RUNNING
        COMPLETED
        FAILED
        ESCALATED
        REPLAYING
    }

    %% ── Validators ───────────────────────────────────────────
    class BaseValidator {
        <<abstract>>
        +name: str
        +validate(artifact, context) ValidationResult
    }

    class ValidationResult {
        +pass_: bool
        +failure_category: FailureCategory
        +severity: str
        +reasons: dict
    }

    class InputIntegrityValidator {
        +required_fields: list
        +validate(artifact, context) ValidationResult
    }

    class JsonSchemaValidator {
        +schema: dict
        +validate(artifact, context) ValidationResult
    }

    class ContentValidator {
        +required_patterns: list
        +forbidden_patterns: list
        +validate(artifact, context) ValidationResult
    }

    class SafetyValidator {
        +blocklist: list
        +validate(artifact, context) ValidationResult
    }

    BaseValidator <|-- InputIntegrityValidator
    BaseValidator <|-- JsonSchemaValidator
    BaseValidator <|-- ContentValidator
    BaseValidator <|-- SafetyValidator
    BaseValidator ..> ValidationResult : returns
    ValidationResult --> FailureCategory

    %% ── LLM Clients ──────────────────────────────────────────
    class BaseLLMClient {
        <<abstract>>
        +call(prompt, model) dict
    }

    class CLIProvider {
        +call(prompt, model) dict
    }

    BaseLLMClient <|-- CLIProvider

    %% ── Decision Engine ──────────────────────────────────────
    class RetryRule {
        +failure_category: FailureCategory
        +retry_strategy: str
        +backoff_strategy: str
    }

    class RetryPolicy {
        +max_retries: int
        +rules: list~RetryRule~
        +get_rule(category) RetryRule
    }

    class DecisionResult {
        +action: str
        +retry_strategy: str
        +reason: str
    }

    RetryPolicy --> RetryRule
    RetryRule --> FailureCategory
    DecisionResult --> FailureCategory

    %% ── Engine ───────────────────────────────────────────────
    class PhaseExecutor {
        +repo: ReliabilityRepository
        +llm: BaseLLMClient
        +validators: list~BaseValidator~
        +execute(run_id, phase_id, prompt_id, input_artifact, retry_policy) dict
    }

    PhaseExecutor --> BaseLLMClient
    PhaseExecutor --> BaseValidator
    PhaseExecutor --> RetryPolicy
    PhaseExecutor ..> DecisionResult : uses

    %% ── Repository ───────────────────────────────────────────
    class ReliabilityRepository {
        +session
        +persist_workflow(data)
        +persist_prompt(data)
        +persist_run(data)
        +persist_llm_call(data)
        +create_escalation(data)
        +update_run_status(run_id, status)
        +get_run(run_id)
        +get_calls_for_run(run_id)
        +get_escalations_for_run(run_id)
    }

    PhaseExecutor --> ReliabilityRepository
    ReliabilityRepository --> RunStatus
```

---

## 3. Sequence Diagram (PhaseExecutor.execute — all paths)

```mermaid
sequenceDiagram
    actor Caller
    participant PE as PhaseExecutor
    participant V0 as validators[0]<br/>(InputIntegrityValidator)
    participant LLM as llm_client
    participant Vn as validators[1:]<br/>(post-call)
    participant DE as decide()
    participant DB as ReliabilityRepository

    Caller->>PE: execute(run_id, phase_id, prompt_id, input_artifact, retry_policy)

    PE->>V0: validate(input_artifact)
    V0-->>PE: ValidationResult

    alt input invalid
        PE->>DB: create_escalation(INPUT_VALIDATION_ERROR)
        PE->>DB: update_run_status(ESCALATED)
        PE-->>Caller: {status: HALTED}
    else input valid — retry loop
        loop attempt_num ≤ max_retries
            Note over PE: call_id = uuid5(run_id:phase_id:prompt_id:attempt_num)
            PE->>LLM: call(str(input_artifact))
            LLM-->>PE: {response_raw, latency_ms, provider, model, tokens...}

            PE->>Vn: validate(response_raw) for each
            Vn-->>PE: ValidationResult[]

            PE->>DB: persist_llm_call(call_record)

            PE->>DE: decide(failures, retry_policy, attempt_num)
            DE-->>PE: DecisionResult

            alt action == COMPLETE
                PE->>DB: update_run_status(COMPLETED)
                PE-->>Caller: {status: SUCCESS, artifact, call_id, provider,<br/>model, latency_ms, tokens...}
            else action == ESCALATE
                PE->>DB: create_escalation(failure_category)
                PE->>DB: update_run_status(ESCALATED)
                PE-->>Caller: {status: ESCALATED, reason}
            else action == RETRY
                Note over PE: attempt_num += 1, loop continues
            end
        end

        PE-->>Caller: {status: FAILED, reason: max retries exceeded}
    end
```

---

## 4. Component / Layer Diagram

```mermaid
graph TD
    subgraph Entry["Entry Points"]
        DEMO[demo/failure_path_runner.py]
        TESTS[tests/]
    end

    subgraph Engine["Engine Layer"]
        PE[PhaseExecutor]
        DE[decision_engine.decide]
        PE --> DE
    end

    subgraph Validators["Validators Layer"]
        BV[BaseValidator]
        IIV[InputIntegrityValidator]
        JSV[JsonSchemaValidator]
        CV[ContentValidator]
        SV[SafetyValidator]
        BV --> IIV & JSV & CV & SV
    end

    subgraph LLM["LLM Layer"]
        BLC[BaseLLMClient]
        CLI[CLIProvider]
        BLC --> CLI
    end

    subgraph DB["DB Layer"]
        RR[ReliabilityRepository]
        SES[session / get_db]
        RR --> SES
    end

    subgraph Core["Core Layer"]
        MOD[models.py<br/>ORM tables + enums]
    end

    INFRA[(PostgreSQL)]

    Entry --> Engine
    Entry --> DB
    Engine --> Validators
    Engine --> LLM
    Engine --> DB
    DB --> Core
    Core --> INFRA

    style Entry fill:#2d3748,color:#e2e8f0
    style Engine fill:#2b4c7e,color:#e2e8f0
    style Validators fill:#2d6a4f,color:#e2e8f0
    style LLM fill:#6b3fa0,color:#e2e8f0
    style DB fill:#7b3f00,color:#e2e8f0
    style Core fill:#4a1942,color:#e2e8f0
    style INFRA fill:#1a1a2e,color:#e2e8f0
```

---

## 5. Decision Engine State Machine

```mermaid
stateDiagram-v2
    [*] --> Evaluating : failures list received

    Evaluating --> COMPLETE : no failures

    Evaluating --> ESCALATE_IMMEDIATE : SAFETY_FLAG or\nINPUT_VALIDATION_ERROR present

    Evaluating --> ESCALATE_BUDGET : attempt_num >= max_retries

    Evaluating --> ESCALATE_NO_RULE : primary failure has\nno RetryRule

    Evaluating --> RETRY : retry budget remaining\nAND rule exists for\nprimary failure

    RETRY --> [*] : DecisionResult(action=RETRY)
    COMPLETE --> [*] : DecisionResult(action=COMPLETE)
    ESCALATE_IMMEDIATE --> [*] : DecisionResult(action=ESCALATE)
    ESCALATE_BUDGET --> [*] : DecisionResult(action=ESCALATE)
    ESCALATE_NO_RULE --> [*] : DecisionResult(action=ESCALATE)
```
