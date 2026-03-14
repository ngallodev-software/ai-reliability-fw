from typing import Any
from src.validators.base import BaseValidator, ValidationResult
from src.core.models import FailureCategory

class InputIntegrityValidator(BaseValidator):
    def __init__(self, required_fields: list[str]):
        self.name = "input_integrity_validator"
        self.required_fields = required_fields
        # Simple injection keywords for Phase 1 demo
        self.injection_blacklist = ["ignore previous instructions", "system prompt", "developer mode"]

    def validate(self, artifact: dict[str, Any], context: dict[str, Any] | None = None) -> ValidationResult:
        # 1. Check for Required Fields
        missing = [f for f in self.required_fields if not artifact.get(f)]
        if missing:
            return ValidationResult(
                pass_=False,
                failure_category=FailureCategory.MISSING_REQUIRED_FIELD,
                severity="ERROR",
                reasons={"missing_fields": missing}
            )

        # 2. Basic Security Check (Demonstration of Safety Gates)
        input_str = str(artifact).lower()
        found_threats = [word for word in self.injection_blacklist if word in input_str]
        if found_threats:
            return ValidationResult(
                pass_=False,
                failure_category=FailureCategory.SAFETY_FLAG,
                severity="ERROR",
                reasons={"detected_injection_terms": found_threats}
            )

        return ValidationResult(pass_=True, failure_category=None, severity="NONE", reasons={})