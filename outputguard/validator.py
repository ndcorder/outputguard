import json
import re
from collections import deque

from referencing.exceptions import Unresolvable

from outputguard._inputs import require_schema
from outputguard.evaluation import Draft7Validator, begin_evaluation, end_evaluation
from outputguard.exceptions import SchemaEvaluationError
from outputguard.formats import FormatParseError, parse_document
from outputguard.models import Schema, ValidationError, ValidationResult
from outputguard.schema import (
    _FALSE_SCHEMA,
    prepare_pointer_document,
    prepare_reference_lookup,
    prepare_schema,
)
from outputguard.schema_formats import SCHEMA_FORMAT_CHECKER

_IDENTIFIER = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*\Z")
_SURROGATES = re.compile("[\ud800-\udfff]")


def _quote_path_segment(segment) -> str:
    quoted = json.dumps(str(segment), ensure_ascii=False)
    if _SURROGATES.search(quoted):
        # JSON.stringify emits well-formed JSON: paired UTF-16 surrogates become
        # their code point, while lone surrogates retain an explicit escape.
        quoted = quoted.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "surrogatepass")
        quoted = quoted.encode("utf-8", "backslashreplace").decode("utf-8")
    return quoted


def _deque_to_json_path(path: deque) -> str:
    """Convert a jsonschema absolute_path deque to a JSON path string."""
    parts = ["$"]
    for segment in path:
        if isinstance(segment, int):
            parts.append(f"[{segment}]")
        elif isinstance(segment, str) and _IDENTIFIER.fullmatch(segment):
            parts.append(f".{segment}")
        else:
            parts.append(f"[{_quote_path_segment(segment)}]")
    return "".join(parts)


def _path_sort_key(path: deque) -> tuple[tuple[int, int | str], ...]:
    # Python literal mappings can mix integer and string keys, which cannot be
    # compared directly. Keep array indexes numeric while ordering other keys.
    return tuple((0, part) if isinstance(part, int) else (1, str(part)) for part in path)


def _schema_errors(data, schema: Schema):
    try:
        return list(
            Draft7Validator(
                prepare_pointer_document(schema), format_checker=SCHEMA_FORMAT_CHECKER
            ).iter_errors(data)
        )
    except (Unresolvable, AttributeError):
        # Retry only when document views can repair encoded fragment resolution
        # or legacy dependency discovery and pointer scopes, without changing data.
        prepared = prepare_reference_lookup(schema)
        if prepared is schema:
            raise
        return list(
            Draft7Validator(prepared, format_checker=SCHEMA_FORMAT_CHECKER).iter_errors(data)
        )


def invalidate_schema(schema: Schema) -> None:
    """Mark a changed schema for subsequent validation.

    Python evaluates schemas on each call, so no compiled validator needs to be
    discarded here. The matching JavaScript API invalidates its identity cache.
    """
    require_schema(schema)


def _recursion_failure(error: BaseException) -> bool:
    if isinstance(error, RecursionError):
        return True
    # rpds can promote a failed Python equality callback into a PyO3 panic.
    # Only its observed recursion signature is an evaluation-depth failure.
    kind = type(error)
    return (
        kind.__module__ == "pyo3_runtime"
        and kind.__name__ == "PanicException"
        and "RecursionError" in str(error)
    )


def validate(text: str, schema: Schema, format: str = "json") -> ValidationResult:
    """Parse text as a structured format, then validate against a JSON Schema."""
    require_schema(schema)
    try:
        data = parse_document(text, format)
    except FormatParseError as e:
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
            format=format,
            parse_error=str(e),
        )

    scope = begin_evaluation()
    try:
        return _validate_parsed(text, data, schema, format)
    except BaseException as error:
        if not _recursion_failure(error):
            raise
        raise SchemaEvaluationError(
            "Schema evaluation could not complete because of excessive recursion",
            data,
            schema,
            format,
        ) from error
    finally:
        end_evaluation(scope)


def _validate_parsed(text: str, data, schema: Schema, format: str) -> ValidationResult:
    native_errors = _schema_errors(data, schema)
    # Rewrite boolean diagnostics only for affected native errors.
    if isinstance(schema, dict) and any(error.schema is False for error in native_errors):
        prepared = prepare_schema(schema)
        if prepared is not schema:
            native_errors = _schema_errors(data, prepared)
    errors: list[ValidationError] = []

    for error in sorted(native_errors, key=lambda e: _path_sort_key(e.absolute_path)):
        false_schema = error.schema is _FALSE_SCHEMA and error.validator == "not"
        schema_path = error.absolute_schema_path.copy()
        if false_schema:
            schema_path.pop()  # Remove the internal equivalent constraint's keyword.
        errors.append(
            ValidationError(
                message=f"False schema does not allow {error.instance!r}"
                if false_schema
                else error.message,
                path=_deque_to_json_path(error.absolute_path),
                schema_path=_deque_to_json_path(schema_path),
                value=error.instance,
            )
        )

    return ValidationResult(
        valid=len(errors) == 0,
        data=data,
        errors=errors,
        original_text=text,
        format=format,
    )
