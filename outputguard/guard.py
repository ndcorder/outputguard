from __future__ import annotations

from typing import Literal, overload

from outputguard import repairer as _repairer
from outputguard import retry as _retry
from outputguard import validator as _validator
from outputguard.exceptions import ParseError, SchemaValidationError
from outputguard.formats import format_label
from outputguard.models import RepairResult, ValidationError, ValidationResult
from outputguard.report import RepairReport


class OutputGuard:
    def __init__(
        self,
        strategies: list[str] | None = None,
        max_repair_attempts: int = 3,
        format: str = "json",
    ):
        self.strategies = strategies
        self.max_repair_attempts = max_repair_attempts
        self.format = format

    def validate(self, text: str, schema: dict, format: str | None = None) -> ValidationResult:
        return _validator.validate(text, schema, format or self.format)

    @overload
    def repair(self, text: str, *, format: str | None = ...) -> RepairResult: ...

    @overload
    def repair(
        self, text: str, *, report: Literal[True], format: str | None = ...
    ) -> tuple[RepairResult, RepairReport]: ...

    def repair(
        self, text: str, *, report: bool = False, format: str | None = None
    ) -> RepairResult | tuple[RepairResult, RepairReport]:
        data_format = format or self.format
        if report:
            return _repairer.repair(text, self.strategies, report=True, format=data_format)
        return _repairer.repair(text, self.strategies, format=data_format)

    def validate_and_repair(
        self, text: str, schema: dict, format: str | None = None
    ) -> ValidationResult:
        """Validate, and if invalid, attempt repair then re-validate."""
        data_format = format or self.format
        result = self.validate(text, schema, data_format)
        if result.valid:
            return result

        current_text = text
        for _attempt in range(self.max_repair_attempts):
            repair_result = _repairer.repair(current_text, self.strategies, format=data_format)
            if not repair_result.repaired:
                continue

            revalidation = self.validate(repair_result.text, schema, data_format)
            if revalidation.valid:
                revalidation.repaired = True
                revalidation.strategies_applied = repair_result.strategies_applied
                revalidation.original_text = text
                revalidation.repaired_text = repair_result.text
                return revalidation
            current_text = repair_result.text

        result.original_text = text
        return result

    def parse(self, text: str, schema: dict, format: str | None = None):
        """Validate, repair, and return parsed data. Raises on failure.

        This is the simplest API: give it text and a schema, get back
        parsed data or an exception.

        Raises:
            ParseError: If the text cannot be parsed even after repair.
            SchemaValidationError: If the parsed output doesn't match the schema.
        """
        data_format = format or self.format
        result = self.validate_and_repair(text, schema, data_format)
        if result.valid:
            assert result.data is not None
            return result.data

        if result.data is None:
            raise ParseError(
                f"Could not parse {format_label(data_format)} from LLM output",
                original_text=text,
                parse_error=result.errors[0].message if result.errors else None,
                format=data_format,
            )
        raise SchemaValidationError(
            f"{format_label(data_format)} does not match schema: {len(result.errors)} error(s)",
            data=result.data,
            errors=result.errors,
            schema=schema,
            format=data_format,
        )

    def retry_prompt(
        self,
        text: str,
        schema: dict,
        errors: list[ValidationError],
        format: str | None = None,
        include_message_history: bool = True,
    ) -> str:
        return _retry.retry_prompt(
            text,
            schema,
            errors,
            format or self.format,
            include_message_history=include_message_history,
        )
