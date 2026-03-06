# Modern type hints used instead of typing.List, typing.Optional
from dataclasses import dataclass
from src.core.models import FailureCategory

@dataclass
class RetryRule:
    failure_category: FailureCategory
    retry_strategy: str
    backoff_strategy: str | None = None

@dataclass
class RetryPolicy:
    max_retries: int
    rules: list[RetryRule]

    def get_rule(self, category: FailureCategory) -> RetryRule | None:
        for rule in self.rules:
            if rule.failure_category == category:
                return rule
        return None

@dataclass
class DecisionResult:
    action: str  # "RETRY", "ESCALATE", "COMPLETE"
    retry_strategy: str | None = None
    reason: str = ""

def decide(
    failures: list[FailureCategory],
    policy: RetryPolicy,
    attempt_num: int
) -> DecisionResult:
    if not failures:
        return DecisionResult(action="COMPLETE", reason="No failures detected.")

    # High-priority immediate escalations
    for f in failures:
        if f in [FailureCategory.SAFETY_FLAG, FailureCategory.INPUT_VALIDATION_ERROR]:
            return DecisionResult(action="ESCALATE", reason=f"Critical failure: {f.value}")

    # Check retry budget
    if attempt_num >= policy.max_retries:
        return DecisionResult(action="ESCALATE", reason=f"Retries exhausted ({attempt_num})")

    # Evaluate the most severe failure (first in list)
    primary_failure = failures[0]
    rule = policy.get_rule(primary_failure)

    if not rule:
        return DecisionResult(action="ESCALATE", reason=f"No retry rule for {primary_failure.value}")

    return DecisionResult(
        action="RETRY",
        retry_strategy=rule.retry_strategy,
        reason=f"Retrying {primary_failure.value} using {rule.retry_strategy}"
    )