import json
from collections import deque

import jsonschema

from outputguard.models import ValidationError, ValidationResult


def _deque_to_json_path(path: deque) -> str:
    """Convert a jsonschema absolute_path deque to a JSON path string."""
    parts = ["$"]
    for segment in path:
        if isinstance(segment, int):
            parts.append(f"[{segment}]")
        else:
            parts.append(f".{segment}")
    return "".join(parts)


def validate(text: str, schema: dict) -> ValidationResult:
    """Parse text as JSON, validate against schema."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return ValidationResult(
            valid=False,
            data=None,
            errors=[
                ValidationError(
                    message=str(e),
                    path="$",
                    schema_path="",
                )
            ],
            original_text=text,
        )

    validator = jsonschema.Draft7Validator(schema)
    errors: list[ValidationError] = []

    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
        errors.append(
            ValidationError(
                message=error.message,
                path=_deque_to_json_path(error.absolute_path),
                schema_path=_deque_to_json_path(error.absolute_schema_path),
                value=error.instance,
            )
        )

    return ValidationResult(
        valid=len(errors) == 0,
        data=data,
        errors=errors,
        original_text=text,
    )
