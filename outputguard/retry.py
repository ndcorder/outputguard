from __future__ import annotations

from outputguard.formats import format_label
from outputguard.models import ValidationError


def _describe_schema(schema: dict, depth: int = 0, max_depth: int = 2) -> list[str]:
    """Extract a human-readable summary from a JSON schema, recursively up to max_depth."""
    lines: list[str] = []
    schema_type = schema.get("type", "any")
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    indent = "  " * depth

    if properties:
        prop_descriptions: list[str] = []
        for name, prop_schema in properties.items():
            prop_type = prop_schema.get("type", "any")
            req_marker = " (required)" if name in required else ""
            prop_descriptions.append(f"{name} ({prop_type}{req_marker})")

            if depth < max_depth and prop_type in ("object", "array"):
                if prop_type == "object":
                    nested = prop_schema
                elif prop_type == "array":
                    nested = prop_schema.get("items", {})
                else:
                    nested = {}

                sub_lines = _describe_schema(nested, depth + 1, max_depth)
                lines.extend(sub_lines)

        if prop_descriptions:
            if depth == 0:
                desc = f"{indent}- A root {schema_type} with properties: "
                desc += ", ".join(prop_descriptions)
                lines.insert(0, desc)
            else:
                lines.append(f"{indent}- Contains properties: {', '.join(prop_descriptions)}")

    elif schema_type == "array":
        items_schema = schema.get("items", {})
        items_type = items_schema.get("type", "any")
        lines.append(f"{indent}- An array of {items_type}")
        if depth < max_depth:
            sub_lines = _describe_schema(items_schema, depth + 1, max_depth)
            lines.extend(sub_lines)

    return lines


def _truncate(text: str, max_len: int = 500) -> str:
    """Truncate text if longer than max_len, keeping start and end."""
    if len(text) <= max_len:
        return text
    half = max_len // 2
    return text[:half] + "\n...\n" + text[-half:]


def retry_prompt(
    text: str,
    schema: dict,
    errors: list[ValidationError],
    format: str = "json",
    include_message_history: bool = True,
) -> str:
    """Generate a correction prompt for the LLM."""
    label = format_label(format)
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
