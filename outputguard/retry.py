from __future__ import annotations

from outputguard._inputs import require_schema, require_text
from outputguard.formats import format_label
from outputguard.models import Schema, ValidationError


def _schema_type(schema: Schema) -> str:
    if isinstance(schema, bool):
        return "any" if schema else "forbidden"
    if isinstance(schema.get("$ref"), str):
        return "referenced schema"
    value = schema.get("type", "any")
    return " or ".join(value) if isinstance(value, list) else value


def _allows_type(schema: dict, kind: str) -> bool:
    types = schema.get("type")
    return "type" not in schema or types == kind or isinstance(types, list) and kind in types


def _has_structure(schema: Schema) -> bool:
    if isinstance(schema, bool) or isinstance(schema.get("$ref"), str):
        return False
    return (
        _allows_type(schema, "object")
        and bool(schema.get("properties"))
        or _allows_type(schema, "array")
        and ("items" in schema or "type" in schema)
    )


def _property_items(properties: dict[str, Schema]) -> list[tuple[str, Schema]]:
    # JavaScript enumerates canonical array-index names first, then other names
    # in insertion order. Bound conversion before considering arbitrarily long keys.
    indexed: list[tuple[int, str, Schema]] = []
    other: list[tuple[str, Schema]] = []
    for name, child in properties.items():
        if (
            isinstance(name, str)
            and 0 < len(name) <= 10
            and name.isascii()
            and name.isdecimal()
            and (name == "0" or name[0] != "0")
        ):
            index = int(name)
            if index < 2**32 - 1:
                indexed.append((index, name, child))
                continue
        other.append((name, child))
    indexed.sort(key=lambda item: item[0])
    return [(name, child) for _, name, child in indexed] + other


def _describe_schema(schema: Schema, depth: int = 0, max_depth: int = 2) -> list[str]:
    """Extract a human-readable summary from a JSON schema, recursively up to max_depth."""
    lines: list[str] = []
    indent = "  " * depth
    if isinstance(schema, bool):
        description = "Any parsed value is allowed" if schema else "No value is allowed"
        return [f"{indent}- {description} by this schema."]
    if isinstance(schema.get("$ref"), str):
        return []  # Draft 7 ignores sibling assertions; errors describe the referenced constraint.
    schema_type = _schema_type(schema)
    properties = schema.get("properties", {})

    if properties and _allows_type(schema, "object"):
        prop_items = _property_items(properties)
        required = set(schema.get("required", []))
        prop_descriptions: list[str] = []
        for name, prop_schema in prop_items:
            prop_type = _schema_type(prop_schema)
            req_marker = " (required)" if name in required else ""
            prop_descriptions.append(f"{name} ({prop_type}{req_marker})")

        if prop_descriptions:
            if depth == 0:
                desc = f"{indent}- A root {schema_type} with properties: "
                desc += ", ".join(prop_descriptions)
                lines.insert(0, desc)
            else:
                prefix = (
                    "Contains properties"
                    if schema_type == "object"
                    else "For object values, contains properties"
                )
                lines.append(f"{indent}- {prefix}: {', '.join(prop_descriptions)}")

        if depth < max_depth:
            for _, prop_schema in prop_items:
                if _has_structure(prop_schema):
                    lines.extend(_describe_schema(prop_schema, depth + 1, max_depth))

    if _allows_type(schema, "array") and ("items" in schema or "type" in schema):
        items_schema = schema.get("items", {})
        prefix = "An array" if schema_type == "array" else "For array values, an array"
        if items_schema is False:
            lines.append(f"{indent}- {prefix} that must be empty (items: false)")
        elif isinstance(items_schema, list):
            descriptions = [
                f"{index} ({_schema_type(item)})" for index, item in enumerate(items_schema)
            ]
            lines.append(f"{indent}- {prefix} with positional items: {', '.join(descriptions)}")
            if depth < max_depth:
                for item in items_schema:
                    if _has_structure(item):
                        lines.extend(_describe_schema(item, depth + 1, max_depth))
        else:
            lines.append(f"{indent}- {prefix} of {_schema_type(items_schema)}")
            if depth < max_depth and _has_structure(items_schema):
                lines.extend(_describe_schema(items_schema, depth + 1, max_depth))

    return lines


def _truncate(text: str, max_len: int = 500) -> str:
    """Truncate text if longer than max_len, keeping start and end."""
    if len(text) <= max_len:
        return text
    half = max_len // 2
    return text[:half] + "\n...\n" + text[-half:]


def retry_prompt(
    text: str,
    schema: Schema,
    errors: list[ValidationError],
    format: str = "json",
    include_message_history: bool = True,
) -> str:
    """Generate a correction prompt for the LLM."""
    label = format_label(format)
    require_text(text)
    require_schema(schema)
    parts: list[str] = [
        f"The {label} output you provided does not match the required schema. "
        f"Please fix the following errors and return ONLY valid {label} with "
        "no additional text or markdown formatting:",
        "",
        "Errors found:",
    ]

    for i, err in enumerate(errors, 1):
        parts.append(f"{i}. At {err.path}: {err.message}")

    schema_summary = _describe_schema(schema)
    if schema_summary:
        parts.append("")
        parts.append("The expected schema requires:")
        parts.extend(schema_summary)

    if include_message_history:
        parts.append("")
        parts.append("Original output:")
        parts.append(_truncate(text))
    parts.append("")
    parts.append(f"Return ONLY the corrected {label}.")

    return "\n".join(parts)
