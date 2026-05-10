from __future__ import annotations

import ast
import json
from typing import Any, Literal, TypeAlias

import yaml

try:  # pragma: no cover - Python version dependent import
    import tomllib  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover - covered on Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]


Format: TypeAlias = Literal["json", "yaml", "toml", "python", "auto", "forced-json-off"]
CanonicalFormat: TypeAlias = Literal["json", "yaml", "toml", "python", "auto"]

SUPPORTED_FORMATS = ("json", "yaml", "toml", "python", "auto", "forced-json-off")
CLI_FORMAT_CHOICES = (
    "json",
    "yaml",
    "yml",
    "toml",
    "python",
    "python-literal",
    "literal",
    "auto",
    "forced-json-off",
)

_ALIASES: dict[str, CanonicalFormat] = {
    "json": "json",
    "yaml": "yaml",
    "yml": "yaml",
    "toml": "toml",
    "python": "python",
    "py": "python",
    "python-literal": "python",
    "literal": "python",
    "auto": "auto",
    "forced-json-off": "auto",
    "forced_json_off": "auto",
}


class FormatParseError(ValueError):
    """Raised when a document cannot be parsed as the requested structured format."""


def normalize_format(format_name: str) -> CanonicalFormat:
    key = format_name.lower().strip()
    try:
        return _ALIASES[key]
    except KeyError as exc:
        supported = ", ".join(CLI_FORMAT_CHOICES)
        raise ValueError(
            f"Unsupported format: {format_name}. Supported formats: {supported}"
        ) from exc


def format_label(format_name: str) -> str:
    canonical = normalize_format(format_name)
    if format_name == "forced-json-off":
        return "forced-JSON-off structured output"
    labels = {
        "json": "JSON",
        "yaml": "YAML",
        "toml": "TOML",
        "python": "Python literal",
        "auto": "structured output",
    }
    return labels[canonical]


def parse_document(text: str, format_name: str = "json") -> Any:
    canonical = normalize_format(format_name)
    if canonical == "auto":
        return _parse_auto(text)
    return _parse_with_format(text, canonical)


def _parse_auto(text: str) -> Any:
    errors: list[str] = []
    for candidate in ("json", "toml", "python", "yaml"):
        try:
            return _parse_with_format(text, candidate)
        except FormatParseError as exc:
            errors.append(f"{candidate}: {exc}")
    raise FormatParseError("; ".join(errors))


def _parse_with_format(text: str, format_name: CanonicalFormat) -> Any:
    try:
        if format_name == "json":
            return json.loads(text)
        if format_name == "yaml":
            return yaml.safe_load(text)
        if format_name == "toml":
            return tomllib.loads(text)
        if format_name == "python":
            return ast.literal_eval(text)
    except Exception as exc:
        raise FormatParseError(str(exc)) from exc
    raise ValueError(f"Unsupported format: {format_name}")
