import unittest

from src.core.models import FailureCategory
from src.engine.decision_engine import RetryPolicy, RetryRule, decide


def _policy(max_retries: int = 3, rules: list[RetryRule] | None = None) -> RetryPolicy:
    return RetryPolicy(max_retries=max_retries, rules=rules or [])


def _rule(category: FailureCategory, strategy: str = "exponential_backoff") -> RetryRule:
    return RetryRule(failure_category=category, retry_strategy=strategy)


class DecisionEngineTests(unittest.TestCase):

    # 1. No failures → COMPLETE
    def test_no_failures_returns_complete(self):
        result = decide(failures=[], policy=_policy(), attempt_num=0)
        self.assertEqual(result.action, "COMPLETE")
        self.assertIn("No failures", result.reason)

    # 2. Single SAFETY_FLAG → ESCALATE immediately (attempt 0, even with retry rules)
    def test_safety_flag_escalates_immediately(self):
        policy = _policy(rules=[_rule(FailureCategory.SAFETY_FLAG)])
        result = decide(
            failures=[FailureCategory.SAFETY_FLAG],
            policy=policy,
            attempt_num=0,
        )
        self.assertEqual(result.action, "ESCALATE")
        self.assertIn("SAFETY_FLAG", result.reason)

    def test_safety_flag_escalates_even_with_retries_remaining(self):
        policy = _policy(max_retries=10, rules=[_rule(FailureCategory.SAFETY_FLAG)])
        result = decide(
            failures=[FailureCategory.SAFETY_FLAG],
            policy=policy,
            attempt_num=1,
        )
        self.assertEqual(result.action, "ESCALATE")
        self.assertIn("SAFETY_FLAG", result.reason)

    # 3. Single INPUT_VALIDATION_ERROR → ESCALATE immediately
    def test_input_validation_error_escalates_immediately(self):
        policy = _policy(rules=[_rule(FailureCategory.INPUT_VALIDATION_ERROR)])
        result = decide(
            failures=[FailureCategory.INPUT_VALIDATION_ERROR],
            policy=policy,
            attempt_num=0,
        )
        self.assertEqual(result.action, "ESCALATE")
        self.assertIn("INPUT_VALIDATION_ERROR", result.reason)

    def test_input_validation_error_escalates_regardless_of_attempt(self):
        policy = _policy(max_retries=5)
        result = decide(
            failures=[FailureCategory.INPUT_VALIDATION_ERROR],
            policy=policy,
            attempt_num=2,
        )
        self.assertEqual(result.action, "ESCALATE")

    # 4. SAFETY_FLAG mixed with other failures → ESCALATE immediately
    def test_safety_flag_mixed_with_other_failures_escalates(self):
        policy = _policy(rules=[_rule(FailureCategory.SCHEMA_VIOLATION)])
        result = decide(
            failures=[FailureCategory.SCHEMA_VIOLATION, FailureCategory.SAFETY_FLAG],
            policy=policy,
            attempt_num=0,
        )
        self.assertEqual(result.action, "ESCALATE")
        self.assertIn("SAFETY_FLAG", result.reason)

    def test_safety_flag_last_in_list_still_escalates(self):
        policy = _policy(
            rules=[
                _rule(FailureCategory.SCHEMA_VIOLATION),
                _rule(FailureCategory.HALLUCINATION_SIGNAL),
            ]
        )
        result = decide(
            failures=[
                FailureCategory.HALLUCINATION_SIGNAL,
                FailureCategory.SCHEMA_VIOLATION,
                FailureCategory.SAFETY_FLAG,
            ],
            policy=policy,
            attempt_num=0,
        )
        self.assertEqual(result.action, "ESCALATE")
        self.assertIn("SAFETY_FLAG", result.reason)

    # 5. INPUT_VALIDATION_ERROR mixed with SCHEMA_VIOLATION → ESCALATE immediately
    def test_input_validation_error_mixed_with_schema_violation_escalates(self):
        policy = _policy(rules=[_rule(FailureCategory.SCHEMA_VIOLATION)])
        result = decide(
            failures=[FailureCategory.SCHEMA_VIOLATION, FailureCategory.INPUT_VALIDATION_ERROR],
            policy=policy,
            attempt_num=0,
        )
        self.assertEqual(result.action, "ESCALATE")
        self.assertIn("INPUT_VALIDATION_ERROR", result.reason)

    # 6. Retries exhausted (attempt_num == max_retries) → ESCALATE "Retries exhausted"
    def test_retries_exhausted_exact_boundary_escalates(self):
        policy = _policy(max_retries=3, rules=[_rule(FailureCategory.TIMEOUT)])
        result = decide(
            failures=[FailureCategory.TIMEOUT],
            policy=policy,
            attempt_num=3,
        )
        self.assertEqual(result.action, "ESCALATE")
        self.assertIn("Retries exhausted", result.reason)
        self.assertIn("3", result.reason)

    # 7. Retries exhausted (attempt_num > max_retries) → ESCALATE
    def test_retries_exhausted_over_limit_escalates(self):
        policy = _policy(max_retries=3, rules=[_rule(FailureCategory.TIMEOUT)])
        result = decide(
            failures=[FailureCategory.TIMEOUT],
            policy=policy,
            attempt_num=5,
        )
        self.assertEqual(result.action, "ESCALATE")
        self.assertIn("Retries exhausted", result.reason)

    # 8. No retry rule for primary failure → ESCALATE "No retry rule for..."
    def test_no_retry_rule_for_primary_failure_escalates(self):
        policy = _policy(max_retries=3, rules=[_rule(FailureCategory.TIMEOUT)])
        result = decide(
            failures=[FailureCategory.HALLUCINATION_SIGNAL],
            policy=policy,
            attempt_num=0,
        )
        self.assertEqual(result.action, "ESCALATE")
        self.assertIn("No retry rule", result.reason)
        self.assertIn("HALLUCINATION_SIGNAL", result.reason)

    # 9. Has retry rule, under budget → RETRY with correct retry_strategy
    def test_has_retry_rule_under_budget_returns_retry(self):
        policy = _policy(max_retries=3, rules=[_rule(FailureCategory.TIMEOUT, "linear_backoff")])
        result = decide(
            failures=[FailureCategory.TIMEOUT],
            policy=policy,
            attempt_num=1,
        )
        self.assertEqual(result.action, "RETRY")
        self.assertEqual(result.retry_strategy, "linear_backoff")
        self.assertIn("TIMEOUT", result.reason)
        self.assertIn("linear_backoff", result.reason)

    # 10. Has retry rule for SCHEMA_VIOLATION → RETRY with correct strategy
    def test_schema_violation_with_rule_returns_retry(self):
        policy = _policy(max_retries=5, rules=[_rule(FailureCategory.SCHEMA_VIOLATION, "immediate")])
        result = decide(
            failures=[FailureCategory.SCHEMA_VIOLATION],
            policy=policy,
            attempt_num=2,
        )
        self.assertEqual(result.action, "RETRY")
        self.assertEqual(result.retry_strategy, "immediate")

    # 11. Has retry rule for MISSING_REQUIRED_FIELD → RETRY
    def test_missing_required_field_with_rule_returns_retry(self):
        policy = _policy(
            max_retries=4,
            rules=[_rule(FailureCategory.MISSING_REQUIRED_FIELD, "prompt_expansion")],
        )
        result = decide(
            failures=[FailureCategory.MISSING_REQUIRED_FIELD],
            policy=policy,
            attempt_num=0,
        )
        self.assertEqual(result.action, "RETRY")
        self.assertEqual(result.retry_strategy, "prompt_expansion")

    # 12. Multiple failures, first one has a rule → RETRY on primary failure
    def test_multiple_failures_first_has_rule_retries_on_primary(self):
        policy = _policy(
            max_retries=5,
            rules=[_rule(FailureCategory.SCHEMA_VIOLATION, "schema_repair")],
        )
        result = decide(
            failures=[FailureCategory.SCHEMA_VIOLATION, FailureCategory.HALLUCINATION_SIGNAL],
            policy=policy,
            attempt_num=0,
        )
        self.assertEqual(result.action, "RETRY")
        self.assertEqual(result.retry_strategy, "schema_repair")
        self.assertIn("SCHEMA_VIOLATION", result.reason)

    # 13. Multiple failures, first is SAFETY_FLAG → ESCALATE immediately
    def test_multiple_failures_first_is_safety_flag_escalates(self):
        policy = _policy(
            max_retries=5,
            rules=[
                _rule(FailureCategory.SAFETY_FLAG, "manual_review"),
                _rule(FailureCategory.TIMEOUT, "exponential_backoff"),
            ],
        )
        result = decide(
            failures=[FailureCategory.SAFETY_FLAG, FailureCategory.TIMEOUT],
            policy=policy,
            attempt_num=0,
        )
        self.assertEqual(result.action, "ESCALATE")
        self.assertIn("SAFETY_FLAG", result.reason)

    # 14. Empty policy rules (no rules at all) → ESCALATE "No retry rule for..."
    def test_empty_policy_rules_escalates_with_no_rule_message(self):
        policy = _policy(max_retries=5, rules=[])
        result = decide(
            failures=[FailureCategory.PROVIDER_ERROR],
            policy=policy,
            attempt_num=0,
        )
        self.assertEqual(result.action, "ESCALATE")
        self.assertIn("No retry rule", result.reason)
        self.assertIn("PROVIDER_ERROR", result.reason)

    # 15. attempt_num=0 with rule → RETRY
    def test_attempt_zero_with_rule_returns_retry(self):
        policy = _policy(max_retries=1, rules=[_rule(FailureCategory.TIMEOUT, "fast_retry")])
        result = decide(
            failures=[FailureCategory.TIMEOUT],
            policy=policy,
            attempt_num=0,
        )
        self.assertEqual(result.action, "RETRY")
        self.assertEqual(result.retry_strategy, "fast_retry")

    # 16. attempt_num = max_retries - 1 (still has budget) → RETRY
    def test_one_retry_remaining_still_returns_retry(self):
        policy = _policy(max_retries=3, rules=[_rule(FailureCategory.VALIDATION_FAILURE, "revalidate")])
        result = decide(
            failures=[FailureCategory.VALIDATION_FAILURE],
            policy=policy,
            attempt_num=2,  # max_retries - 1
        )
        self.assertEqual(result.action, "RETRY")
        self.assertEqual(result.retry_strategy, "revalidate")

    # 17. attempt_num = max_retries → ESCALATE
    def test_attempt_equals_max_retries_escalates(self):
        policy = _policy(max_retries=3, rules=[_rule(FailureCategory.VALIDATION_FAILURE, "revalidate")])
        result = decide(
            failures=[FailureCategory.VALIDATION_FAILURE],
            policy=policy,
            attempt_num=3,  # == max_retries
        )
        self.assertEqual(result.action, "ESCALATE")
        self.assertIn("Retries exhausted", result.reason)

    # Additional edge cases

    def test_decision_result_complete_has_no_retry_strategy(self):
        result = decide(failures=[], policy=_policy(), attempt_num=0)
        self.assertEqual(result.action, "COMPLETE")
        self.assertIsNone(result.retry_strategy)

    def test_decision_result_retry_carries_strategy(self):
        policy = _policy(max_retries=2, rules=[_rule(FailureCategory.TIMEOUT, "my_strategy")])
        result = decide(failures=[FailureCategory.TIMEOUT], policy=policy, attempt_num=0)
        self.assertEqual(result.retry_strategy, "my_strategy")

    def test_escalate_result_has_no_retry_strategy(self):
        policy = _policy(max_retries=1, rules=[])
        result = decide(failures=[FailureCategory.PROVIDER_ERROR], policy=policy, attempt_num=0)
        self.assertEqual(result.action, "ESCALATE")
        self.assertIsNone(result.retry_strategy)

    def test_human_escalated_without_rule_escalates(self):
        policy = _policy(max_retries=5, rules=[])
        result = decide(
            failures=[FailureCategory.HUMAN_ESCALATED],
            policy=policy,
            attempt_num=0,
        )
        self.assertEqual(result.action, "ESCALATE")
        self.assertIn("No retry rule", result.reason)

    def test_multiple_rules_correct_rule_is_selected(self):
        policy = _policy(
            max_retries=5,
            rules=[
                _rule(FailureCategory.SCHEMA_VIOLATION, "schema_fix"),
                _rule(FailureCategory.TIMEOUT, "timeout_backoff"),
                _rule(FailureCategory.MISSING_REQUIRED_FIELD, "field_fill"),
            ],
        )
        result = decide(
            failures=[FailureCategory.TIMEOUT],
            policy=policy,
            attempt_num=1,
        )
        self.assertEqual(result.action, "RETRY")
        self.assertEqual(result.retry_strategy, "timeout_backoff")

    def test_reason_is_non_empty_string_for_all_outcomes(self):
        cases = [
            # COMPLETE
            ([], _policy(), 0),
            # ESCALATE - safety flag
            ([FailureCategory.SAFETY_FLAG], _policy(), 0),
            # ESCALATE - exhausted
            ([FailureCategory.TIMEOUT], _policy(max_retries=1, rules=[_rule(FailureCategory.TIMEOUT)]), 1),
            # ESCALATE - no rule
            ([FailureCategory.PROVIDER_ERROR], _policy(max_retries=3, rules=[]), 0),
            # RETRY
            ([FailureCategory.TIMEOUT], _policy(max_retries=3, rules=[_rule(FailureCategory.TIMEOUT)]), 0),
        ]
        for failures, policy, attempt_num in cases:
            with self.subTest(failures=failures, attempt_num=attempt_num):
                result = decide(failures=failures, policy=policy, attempt_num=attempt_num)
                self.assertIsInstance(result.reason, str)
                self.assertGreater(len(result.reason), 0)


if __name__ == "__main__":
    unittest.main()
