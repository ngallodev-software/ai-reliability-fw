import json
from typing import Any
from jsonschema import validate, ValidationError
from src.validators.base import BaseValidator, ValidationResult
from src.core.models import FailureCategory

class JsonSchemaValidator(BaseValidator):
    def __init__(self, schema: dict[str, Any]):
        self.name = "json_schema_validator" 
        self.schema = schema

    def validate(self, artifact: str, context: dict[str, Any] | None = None) -> ValidationResult:
        try:
            # 1. Check if it's even valid JSON
            data = json.loads(artifact)
            
            # 2. Check against the schema
            validate(instance=data, schema=self.schema)
            
            return ValidationResult(
                pass_=True,
                failure_category=None,
                severity="NONE",
                reasons={}
            )
        except json.JSONDecodeError as e:
            return ValidationResult(
                pass_=False,
                failure_category=FailureCategory.SCHEMA_VIOLATION,
                severity="ERROR",
                reasons={"error": "Invalid JSON format", "details": str(e)}
            )
        except ValidationError as e:
            return ValidationResult(
                pass_=False,
                failure_category=FailureCategory.SCHEMA_VIOLATION,
                severity="ERROR",
                reasons={"error": "Schema mismatch", "field": e.json_path, "message": e.message}
            )
