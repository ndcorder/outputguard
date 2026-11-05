from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, overload

from outputguard import repairer as _repairer
from outputguard import retry as _retry
from outputguard import validator as _validator
from outputguard._inputs import require_schema
from outputguard.configuration import attempt_limit, select_format
from outputguard.exceptions import ParseError, SchemaValidationError
from outputguard.formats import format_label
from outputguard.models import RepairResult, Schema, ValidationError, ValidationResult
from outputguard.report import RepairReport
from outputguard.strategies import get_strategies, select_strategy_names


class OutputGuard:
    def __init__(
        self,
        strategies: Sequence[str] | None = None,
        max_repair_attempts: int | float = 3,
        format: str | None = "json",
    ):
        self.strategies = select_strategy_names(strategies)
        self.max_repair_attempts = attempt_limit(max_repair_attempts, "max_repair_attempts")
        self.format = select_format(format)

    @property
    def strategy_names(self) -> list[str]:
        """Selected strategy names in execution order, returned as a fresh list."""
        return [name for name, _ in get_strategies(self.strategies)]

    def validate(self, text: str, schema: Schema, format: str | None = None) -> ValidationResult:
        return _validator.validate(text, schema, select_format(format, self.format))

    @overload
    def repair(
        self, text: str, *, report: Literal[False] = False, format: str | None = ...
    ) -> RepairResult: ...

    @overload
    def repair(
        self, text: str, *, report: Literal[True], format: str | None = ...
    ) -> tuple[RepairResult, RepairReport]: ...

    @overload
    def repair(
        self, text: str, *, report: bool, format: str | None = ...
    ) -> RepairResult | tuple[RepairResult, RepairReport]: ...

    def repair(
        self, text: str, *, report: bool = False, format: str | None = None
    ) -> RepairResult | tuple[RepairResult, RepairReport]:
        data_format = select_format(format, self.format)
        if report:
            return _repairer.repair(text, self.strategies, report=True, format=data_format)
        return _repairer.repair(text, self.strategies, format=data_format)

    def validate_and_repair(
        self, text: str, schema: Schema, format: str | None = None
    ) -> ValidationResult:
        """Validate, and if invalid, attempt repair then re-validate."""
        data_format = select_format(format, self.format)
        attempts = attempt_limit(self.max_repair_attempts, "max_repair_attempts")
        strategies = select_strategy_names(self.strategies)
        require_schema(schema)
        result = self.validate(text, schema, data_format)
        if result.valid or result.parse_error is None:
            return result

        current_text = text
        applied: list[str] = []
        for _attempt in range(attempts):
            repair_result = _repairer.repair(current_text, strategies, format=data_format)
            if not repair_result.repaired or repair_result.text == current_text:
                break

            applied = list(dict.fromkeys([*applied, *repair_result.strategies_applied]))
            revalidation = self.validate(repair_result.text, schema, data_format)
            revalidation.repaired = True
            revalidation.strategies_applied = applied
            revalidation.original_text = text
            revalidation.repaired_text = repair_result.text
            result = revalidation
            # Syntax repair cannot fix schema errors in an already parsed document.
            if result.valid or result.parse_error is None:
                return result
            current_text = repair_result.text

        result.original_text = text
        return result

    def parse(self, text: str, schema: Schema, format: str | None = None):
        """Validate, repair, and return parsed data. Raises on failure.

        This is the simplest API: give it text and a schema, get back
        parsed data or an exception.

        Raises:
            ParseError: If the text cannot be parsed even after repair.
            SchemaValidationError: If the parsed output doesn't match the schema.
        """
        data_format = select_format(format, self.format)
        result = self.validate_and_repair(text, schema, data_format)
        if result.valid:
            return result.data

        if result.parse_error is not None:
            raise ParseError(
                f"Could not parse {format_label(data_format)} from LLM output",
                original_text=text,
                parse_error=result.parse_error,
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
        schema: Schema,
        errors: list[ValidationError],
        format: str | None = None,
        include_message_history: bool = True,
    ) -> str:
        return _retry.retry_prompt(
            text,
            schema,
            errors,
            select_format(format, self.format),
            include_message_history=include_message_history,
        )
