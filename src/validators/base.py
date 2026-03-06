from dataclasses import dataclass
from typing import Any
from src.core.models import FailureCategory

@dataclass
class ValidationResult:
    pass_: bool
    failure_category: FailureCategory | None
    severity: str  # "WARNING" or "ERROR"
    reasons: dict[str, Any]

class BaseValidator:
    """
    Hard-contract for all post-call and pre-call validators.
    Ensures structured reasons are returned rather than free text.
    """
    name: str

    def validate(self, artifact: Any, context: dict[str, Any] | None = None) -> ValidationResult:
        raise NotImplementedError("Each validator must implement the validate method.")