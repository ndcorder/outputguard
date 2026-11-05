"""Construct YAML documents and expected data independently of the parser."""

from __future__ import annotations

import json
import random
from pathlib import Path

from benchmarks.parsing_cases import expected_result


def _nested(text: str, prefix: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return prefix + "\n  " + text.replace("\n", "\n  ")


def yaml_fixture_cases() -> list[dict]:
    fixtures = json.loads(Path(__file__).with_name("yaml_cases.json").read_text())
    cases = []
    for fixture in fixtures:
        for location in ["root"] if fixture.get("root_only") else ["root", "property", "list"]:
            text, data = fixture["text"], fixture.get("value")
            if location == "property":
                text, data = _nested(text, "holder:"), {"holder": data}
            elif location == "list":
                text, data = _nested(text, "-"), [data]
            case = {
                "name": f"yaml-core-{fixture['name']}-{location}",
                "format": "yaml",
                "schema": True,
            }
            if "value_kind" in fixture:
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
                            "formats": {"yaml": 1},
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


def generate_yaml_cases(count: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    fixtures = json.loads(Path(__file__).with_name("yaml_cases.json").read_text())
    portable = [case for case in fixtures if not case.get("root_only")]
    atoms = [case for case in portable if case["valid"] and "value_kind" not in case]
    malformed = [case for case in portable if not case["valid"]]
    cases = []
    for index in range(count):
        broken = rng.randrange(5) == 0
        if broken:
            text, data = rng.choice(malformed)["text"], None
        elif rng.randrange(3):
            atom = rng.choice(atoms)
            text, data = atom["text"], atom["value"]
        else:
            coefficient = rng.randrange(10**6)
            if rng.choice([True, False]):
                base = rng.choice([8, 10, 16])
                text = (
                    "0o" + format(coefficient, "o")
                    if base == 8
                    else "0x" + format(coefficient, "x")
                    if base == 16
                    else "0" * rng.randrange(3) + str(coefficient)
                )
                data = coefficient
            else:
                scale, exponent = rng.randrange(7), rng.randrange(-6, 7)
                body = str(coefficient).zfill(scale + 1)
                point = len(body) - scale
                text = body[:point] + "." + body[point:] + "e" + str(exponent)
                data = coefficient * 10 ** max(exponent, 0) / 10 ** (scale + max(-exponent, 0))
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        flow = (
            not broken
            and "\n" not in text
            and bool(text)
            and not text.startswith(("#", "|", ">"))
            and ": " not in text
            and not text.endswith(":")
        )
        for depth in range(rng.randrange(4)):
            key = rng.choice(["value", "a/b", "__proto__", "constructor", "Ω"])
            if flow and rng.choice([True, False]):
                if rng.choice([True, False]):
                    anchor = f"generated{depth}"
                    text, data = f"[&{anchor} " + text + f", *{anchor}]", [data, data]
                else:
                    text, data = (
                        "{" + json.dumps(key) + ": " + text + ", marker: false}",
                        {key: data, "marker": False},
                    )
            elif rng.choice([True, False]):
                text, data = _nested(text, json.dumps(key) + ":"), {key: data}
                flow = False
            else:
                text, data = _nested(text, "-"), [data]
                flow = False
        valid = rng.randrange(4) != 0
        schema = rng.choice([True, {}, {"const": data}, {"enum": [data]}]) if valid else False
        if flow and rng.randrange(6) == 0:
            text, data = "[&unique " + text + ", *unique]", [data, data]
            schema, valid = {"uniqueItems": True}, False
        if rng.choice([True, False]):
            schema = {"definitions": {"value": schema}, "$ref": "#/definitions/value"}
        format_name = rng.choice(["yaml", "yml", "auto", "forced-json-off"])
        if format_name in {"auto", "forced-json-off"}:
            text = "---\n" + text
        cases.append(
            {
                "name": f"yaml-seed-{seed}-case-{index}",
                "operation": "validate"
                if broken
                else rng.choice(["validate", "validate_and_repair"]),
                "text": text,
                "schema": schema,
                "format": format_name,
                "expected": expected_result(
                    None if broken else data, valid=valid and not broken, parse_failure=broken
                ),
            }
        )
    return cases
