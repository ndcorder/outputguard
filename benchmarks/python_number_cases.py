"""Construct numeric Python literals alongside their expected values."""

from __future__ import annotations

import json
import random
from pathlib import Path

from benchmarks.parsing_cases import expected_result


def number_fixture_cases() -> list[dict]:
    fixtures = json.loads(Path(__file__).with_name("python_numbers.json").read_text())
    cases = []
    for fixture in fixtures:
        for location in ["root"] if fixture.get("root_only") else ["root", "property", "list"]:
            text, data = fixture["text"], fixture.get("value")
            if location == "property":
                text, data = "{'value': " + text + "}", {"value": data}
            elif location == "list":
                text, data = "[" + text + "]", [data]
            case = {
                "name": f"python-number-{fixture['name']}-{location}",
                "format": "python",
                "schema": True,
            }
            if "value_kind" in fixture:
                # Infinity cannot be transported as JSON data. Unit tests check
                # the actual value; the shared runner checks batch classification.
                case.update(
                    operation="validate_batch",
                    texts=[text],
                    expected={
                        "summary": {
                            "total": 1,
                            "valid": 1,
                            "invalid": 0,
                            "repaired": 0,
                            "parse_failures": 0,
                            "schema_failures": 0,
                            "success_rate": 1,
                            "strategy_counts": {},
                            "formats": {"python": 1},
                        }
                    },
                )
            else:
                case.update(
                    operation="validate",
                    text=text,
                    expected=expected_result(
                        data if fixture["valid"] else None,
                        valid=fixture["valid"],
                        parse_failure=not fixture["valid"],
                    ),
                )
            cases.append(case)
    return cases


def generate_python_number_cases(count: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    fixtures = json.loads(Path(__file__).with_name("python_numbers.json").read_text())
    malformed = [case for case in fixtures if not case["valid"] and not case.get("root_only")]

    def digits(value):
        return "".join(
            ("_" if index and rng.randrange(3) == 0 else "") + char
            for index, char in enumerate(value)
        )

    cases = []
    for index in range(count):
        broken = rng.randrange(4) == 0
        if broken:
            text, data = rng.choice(malformed)["text"], None
        else:
            integer = rng.choice([True, False])
            if integer:
                data = rng.randrange(10**12) if rng.randrange(5) else 0
                base = rng.choice([2, 8, 10, 16])
                if base == 10:
                    text = digits(str(data))
                else:
                    specifier = {2: "b", 8: "o", 16: "x"}[base]
                    prefix = "0" + rng.choice([specifier, specifier.upper()])
                    body = format(data, specifier)
                    if rng.choice([True, False]):
                        body = body.upper()
                    text = prefix + rng.choice(["", "_"]) + digits(body)
            else:
                coefficient = rng.randrange(10**6) if rng.randrange(5) else 0
                scale, exponent = rng.randrange(7), rng.randrange(-3, 4)
                body = str(coefficient).zfill(scale + 1)
                point = len(body) - scale
                whole, fraction = (
                    digits("0" * rng.randrange(3) + body[:point]),
                    digits(body[point:]),
                )
                text = whole + "." + fraction
                if rng.choice([True, False]):
                    # All operands stay exactly representable as integers before
                    # division, giving one correctly rounded binary float.
                    text += (
                        rng.choice(["e", "E"])
                        + ("-" if exponent < 0 else "+")
                        + digits(str(abs(exponent)))
                    )
                else:
                    exponent = 0
                data = coefficient * 10 ** max(exponent, 0) / 10 ** (scale + max(-exponent, 0))
            for _ in range(rng.randrange(3)):
                text = "(" + text + ")"
            sign = rng.choice(["", "+", "-"])
            if sign:
                gap = rng.choice(["", " ", "\t", "\f", "\\\n", "\n", " # comment\n"])
                text = sign + gap + text
                if "\n" in gap and gap != "\\\n":
                    text = "(" + text + ")"
                if sign == "-":
                    data = -data
        for _ in range(rng.randrange(4)):
            if rng.choice([True, False]):
                text, data = "[" + text + ", 0]", [data, 0]
            else:
                key = rng.choice(["value", "a/b", "__proto__", "constructor", "Ω"])
                text, data = (
                    "{" + json.dumps(key, ensure_ascii=False) + ": " + text + "}",
                    {key: data},
                )
        valid = rng.randrange(4) != 0
        schema = rng.choice([True, {}, {"const": data}, {"enum": [data]}]) if valid else False
        if rng.choice([True, False]):
            schema = {"definitions": {"number": schema}, "$ref": "#/definitions/number"}
        cases.append(
            {
                "name": f"python-numbers-seed-{seed}-case-{index}",
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
