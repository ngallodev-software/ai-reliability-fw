from typing import Any

from src.core.models import FailureCategory
from src.validators.base import BaseValidator, ValidationResult


class SafetyValidator(BaseValidator):
    name = "safety_validator"

    def __init__(self, blocklist: list[str]):
        self.blocklist = blocklist

    def validate(self, artifact: str, context: dict[str, Any] | None = None) -> ValidationResult:  # noqa: ARG002
        artifact_lower = artifact.lower()
        # Intentional substring match (not word-boundary): "harm" will match "harmful" and "Harmless".
        # Keep blocklist terms specific enough to avoid false positives.
        detected = [term for term in self.blocklist if term.lower() in artifact_lower]

        if detected:
            return ValidationResult(
                pass_=False,
                failure_category=FailureCategory.SAFETY_FLAG,
                severity="ERROR",
                reasons={"detected_terms": detected},
            )

        return ValidationResult(
            pass_=True,
            failure_category=None,
            severity="OK",
            reasons={},
        )
