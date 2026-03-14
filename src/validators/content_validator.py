import re
from typing import Any

from src.core.models import FailureCategory
from src.validators.base import BaseValidator, ValidationResult


class ContentValidator(BaseValidator):
    name = "content_validator"

    def __init__(
        self,
        required_patterns: list[str] | None = None,
        forbidden_patterns: list[str] | None = None,
    ):
        self.required_patterns = required_patterns or []
        self.forbidden_patterns = forbidden_patterns or []

    def validate(self, artifact: str, context: dict[str, Any] | None = None) -> ValidationResult:
        missing = [p for p in self.required_patterns if not re.search(p, artifact)]
        if missing:
            return ValidationResult(
                pass_=False,
                failure_category=FailureCategory.OUTPUT_CONTENT_ERROR,
                severity="ERROR",
                reasons={"missing_patterns": missing},
            )

        matched = [p for p in self.forbidden_patterns if re.search(p, artifact)]
        if matched:
            return ValidationResult(
                pass_=False,
                failure_category=FailureCategory.OUTPUT_CONTENT_ERROR,
                severity="ERROR",
                reasons={"forbidden_patterns_matched": matched},
            )

        return ValidationResult(
            pass_=True,
            failure_category=None,
            severity="OK",
            reasons={},
        )
