"""Generate malformed JSON from known data without using a repair implementation."""

from __future__ import annotations

import json
import random

VALUES = {
    "NaN": None,
    "Infinity": None,
    "-Infinity": None,
    "+Infinity": None,
    "-NaN": None,
    "+NaN": None,
    "undefined": None,
    "True": True,
    "False": False,
    "None": None,
}


def expected_result(data, *, valid=True, repaired_text="", strategies=(), parse_failure=False):
    return {
        "valid": valid,
        "data": data,
        "repaired": bool(strategies),
        "repaired_text": repaired_text,
        "strategies": list(strategies),
        "parse_failure": parse_failure,
        "error_paths": [] if valid else ["$"],
        "error_values": [] if valid else [None if parse_failure else data],
    }


def generate_parsing_cases(count: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    cases = []
    marker = "__outputguard_generated_bare_value__"
    keys = [
        "value",
        "__proto__",
        "constructor",
        "toString",
        "valueOf",
        "a/b",
        "a~b",
        "",
        "Ω",
        'a"b',
        "a\\b",
    ]
    for index in range(count):
        tokens = rng.sample(list(VALUES), rng.randrange(1, 5))
        data = [VALUES[token] for token in tokens]
        text = "[" + ",".join(tokens) + "]"
        repaired = "[" + ",".join(json.dumps(value) for value in data) + "]"
        if len(tokens) == 1 and rng.choice([True, False]):
            text, data = tokens[0], data[0]
            repaired = json.dumps(data)
        for _ in range(rng.randrange(5)):
            if rng.choice([True, False]):
                text, data = "[" + text + ",0]", [data, 0]
                repaired = "[" + repaired + ",0]"
            else:
                key = rng.choice(keys)
                literal = rng.choice(list(VALUES)) + "\\" * rng.randrange(7)
                payload = {"path": "tail" + "\\" * rng.randrange(7), "literal": literal}
                # Put the malformed value after valid strings, including strings
                # ending in an even run of escaped backslashes.
                payload[key if key not in payload else "payload"] = marker
                template = json.dumps(payload, ensure_ascii=rng.choice([True, False]))
                text = template.replace(json.dumps(marker), text)
                repaired = template.replace(json.dumps(marker), repaired)
                data = {name: data if value == marker else value for name, value in payload.items()}
        schema_choice = rng.randrange(6)
        valid = schema_choice != 1
        if schema_choice == 5:
            valid = rng.choice([True, False])
            companion = {"different": seed} if valid else data
            text = "[" + text + "," + (json.dumps(companion) if valid else text) + "]"
            repaired = "[" + repaired + "," + (json.dumps(companion) if valid else repaired) + "]"
            data = [data, companion]
            schema = {"uniqueItems": True}
        else:
            schema = [True, False, {}, {"const": data}, {"enum": [{"different": seed}, data]}][
                schema_choice
            ]
        if rng.choice([True, False]):
            schema = {"definitions": {"check": schema}, "$ref": "#/definitions/check"}
        operation = rng.choice(["validate", "validate_and_repair", "validate_and_repair"])
        strategies = []
        if any(token not in {"True", "False", "None"} for token in tokens):
            strategies.append("fix_values")
        if any(token in {"True", "False", "None"} for token in tokens):
            strategies.append("fix_booleans")
        if operation == "validate":
            expected = expected_result(None, valid=False, parse_failure=True)
        else:
            expected = expected_result(
                data, valid=valid, repaired_text=repaired, strategies=strategies
            )
        cases.append(
            {
                "name": f"parsing-seed-{seed}-case-{index}",
                "operation": operation,
                "schema": schema,
                "text": text,
                "format": "json",
                "expected": expected,
            }
        )
    return cases
