from __future__ import annotations

import json

from outputguard.exceptions import ParseError, SchemaValidationError
from outputguard.models import RepairResult, ValidationError, ValidationResult
from outputguard.report import RepairReport
from outputguard import repairer as _repairer
from outputguard import retry as _retry
from outputguard import validator as _validator


class OutputGuard:
    def __init__(
        self,
        strategies: list[str] | None = None,
        max_repair_attempts: int = 3,
    ):
        self.strategies = strategies
        self.max_repair_attempts = max_repair_attempts

    def validate(self, text: str, schema: dict) -> ValidationResult:
        return _validator.validate(text, schema)

    def repair(
        self, text: str, *, report: bool = False
    ) -> RepairResult | tuple[RepairResult, RepairReport]:
        return _repairer.repair(text, self.strategies, report=report)

    def validate_and_repair(self, text: str, schema: dict) -> ValidationResult:
        """Validate, and if invalid, attempt repair then re-validate."""
        result = self.validate(text, schema)
        if result.valid:
            return result

        current_text = text
        for _attempt in range(self.max_repair_attempts):
            repair_result = _repairer.repair(current_text, self.strategies)
            if not repair_result.repaired:
                continue

            revalidation = self.validate(repair_result.text, schema)
            if revalidation.valid:
                revalidation.repaired = True
                revalidation.strategies_applied = repair_result.strategies_applied
                revalidation.original_text = text
                revalidation.repaired_text = repair_result.text
                return revalidation
            current_text = repair_result.text

        result.original_text = text
        return result

    def parse(self, text: str, schema: dict) -> dict | list:
        """Validate, repair, and return parsed data. Raises on failure.

        This is the simplest API: give it text and a schema, get back
        parsed data or an exception.

        Raises:
            ParseError: If the text cannot be parsed as JSON even after repair.
            SchemaValidationError: If the parsed JSON doesn't match the schema.
        """
        result = self.validate_and_repair(text, schema)
        if result.valid:
            return result.data

        if result.data is None:
            raise ParseError(
                "Could not parse JSON from LLM output",
                original_text=text,
                parse_error=result.errors[0].message if result.errors else None,
            )
        raise SchemaValidationError(
            f"JSON does not match schema: {len(result.errors)} error(s)",
            data=result.data,
            errors=result.errors,
            schema=schema,
        )

    def retry_prompt(
        self, text: str, schema: dict, errors: list[ValidationError]
    ) -> str:
        return _retry.retry_prompt(text, schema, errors)
