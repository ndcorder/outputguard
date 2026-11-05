"""Compose Python literals from explicit string fixtures and known values."""

from __future__ import annotations

import json
import random
from pathlib import Path

from benchmarks.parsing_cases import expected_result


def string_fixture_cases() -> list[dict]:
    fixtures = json.loads(Path(__file__).with_name("python_strings.json").read_text())
    cases = []
    for fixture in fixtures:
        for location in ["root"] if fixture.get("root_only") else ["root", "property", "list"]:
            text, data = fixture["text"], fixture.get("value")
            if location == "property":
                text, data = "{'value': " + text + "}", {"value": data}
            elif location == "list":
                text, data = "[" + text + "]", [data]
            cases.append(
                {
                    "name": f"python-string-{fixture['name']}-{location}",
                    "operation": "validate",
                    "format": "python",
                    "text": text,
                    "schema": True,
                    "expected": expected_result(
                        data if fixture["valid"] else None,
                        valid=fixture["valid"],
                        parse_failure=not fixture["valid"],
                    ),
                }
            )
    return cases


def generate_python_string_cases(count: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    fixtures = json.loads(Path(__file__).with_name("python_strings.json").read_text())
    atoms = [
        case
        for case in fixtures
        if case["valid"]
        and not case.get("root_only")
        and not case["text"].startswith("(")
        # Two separately escaped surrogates can become one JS UTF-16 pair.
        # Those native string representations are tested as individual fixtures.
        and not any(0xD800 <= ord(char) <= 0xDFFF for char in case["value"])
    ]
    malformed = [case for case in fixtures if not case["valid"] and not case.get("root_only")]
    cases = []
    for index in range(count):
        broken = rng.randrange(4) == 0
        if broken:
            text, data = rng.choice(malformed)["text"], None
        else:
            parts = rng.choices(atoms, k=rng.randrange(1, 6))
            gap = rng.choice([" ", "\t", "\f", "\\\n", " # comment\n", "\n"])
            text, data = (
                gap.join(case["text"] for case in parts),
                "".join(case["value"] for case in parts),
            )
            # Parentheses allow physical newlines and comments between atoms.
            if "\n" in gap or rng.choice([True, False]):
                text = "(" + text + ")"
        for _ in range(rng.randrange(4)):
            if rng.choice([True, False]):
                text, data = "[" + text + ", 'tail']", [data, "tail"]
            else:
                key = rng.choice(["value", "a/b", "__proto__", "constructor", "Ω"])
                text = "{" + json.dumps(key, ensure_ascii=False) + ": " + text + "}"
                data = {key: data}
        valid = rng.randrange(4) != 0
        schema = rng.choice([True, {}, {"const": data}, {"enum": [data]}]) if valid else False
        if rng.choice([True, False]):
            schema = {"definitions": {"value": schema}, "$ref": "#/definitions/value"}
        cases.append(
            {
                "name": f"python-strings-seed-{seed}-case-{index}",
                "operation": "validate"
                if broken
                else rng.choice(["validate", "validate_and_repair"]),
                "text": text,
                "schema": schema,
                "format": rng.choice(["python", "python-literal", "py", "literal"]),
                "expected": expected_result(
                    None if broken else data, valid=valid and not broken, parse_failure=broken
                ),
            }
        )
    return cases
