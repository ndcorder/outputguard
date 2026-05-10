from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationError:
    message: str
    path: str  # JSON path, e.g. "$.items[0].name"
    schema_path: str  # Schema path that was violated
    value: Any = None


@dataclass
class ValidationResult:
    valid: bool
    data: Any = None
    errors: list[ValidationError] = field(default_factory=list)
    repaired: bool = False
    strategies_applied: list[str] = field(default_factory=list)
    original_text: str = ""
    repaired_text: str = ""
    format: str = "json"


@dataclass
class RepairResult:
    repaired: bool
    text: str
    strategies_applied: list[str] = field(default_factory=list)
    parse_error: str | None = None
    format: str = "json"
