"""Compare validation decisions for reproducible generated schemas across ports."""

from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
from pathlib import Path
from urllib.parse import quote

from referencing.exceptions import Unresolvable

from benchmarks.comparison import same_json
from benchmarks.evaluation_cases import generate_evaluation_cases
from benchmarks.format_cases import generate_format_cases
from benchmarks.numeric_cases import generate_numeric_cases
from benchmarks.regex_cases import generate_regex_cases
from benchmarks.run import positive_int
from benchmarks.scope_cases import generate_scope_cases
from outputguard import validate

_NODE_RUNNER = """
import { MissingRefError } from 'ajv';
import { validate } from './dist/index.js';
process.stdin.setEncoding('utf8');
let input = '';
for await (const chunk of process.stdin) input += chunk;
const cases = JSON.parse(input);
const results = cases.map(entry => {
  try {
    const result = validate(entry.text, entry.schema);
    const valid = result.valid;
    if (typeof valid !== 'boolean') {
      valid?.catch?.(() => {});
      throw new Error('Synchronous validation must return a boolean valid field');
    }
    if (entry.expected_result && !entry.expected_result.paths) return {valid};
    if (entry.expected_paths || entry.expected_result?.paths) {
      const errors = [...result.errors]
        .sort((left, right) => left.path < right.path ? -1 : left.path > right.path ? 1 : 0);
      return {valid, paths: errors.map(error => error.path),
        values: errors.map(error => error.value ?? null)};
    }
    return valid;
  } catch (error) {
    if (entry.expected_result && error instanceof MissingRefError) {
      return {schema_error: 'unresolvable'};
    }
    process.stderr.write(JSON.stringify(entry, null, 2) + '\\n' + error.stack + '\\n');
    process.exit(1);
  }
});
process.stdout.write(JSON.stringify(results));
"""


def generate_cases(count: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    cases = []
    values = [None, False, 0, 42, "wrong", [], {}]
    for index in range(count):
        kind = rng.choice(["integer", "string", "null", "boolean", "array", "object", True, False])
        constraint = kind if isinstance(kind, bool) else {"type": kind}
        if isinstance(constraint, dict) and rng.choice([True, False]):
            constraint["$async"] = True
        schema = {"properties": {"__proto__": constraint}}
        data = {"__proto__": rng.choice(values)}
        for _ in range(rng.randrange(1, 5)):
            choice = rng.randrange(11)
            if choice == 0:
                key = rng.choice(["child", "a/b", "a~b", "a%b", "", "__proto__"])
                schema, data = {"properties": {key: schema}}, {key: data}
            elif choice == 1:
                schema, data = {"items": schema}, [data]
            elif choice == 2:
                schema = {"allOf": [schema]}
            elif choice == 3:
                schema = {"anyOf": [schema, {"type": "null"}]}
            elif choice == 4:
                schema = {"oneOf": [schema, {"type": "null"}]}
            elif choice == 5:
                schema = {"not": schema}
            elif choice == 6:
                schema, data = {"additionalProperties": schema}, {"child": data}
            elif choice == 7:
                pattern = rng.choice(["^child$", "__proto__"])
                schema, data = (
                    {"patternProperties": {pattern: schema}},
                    {
                        "child": data,
                        "__proto__": data,
                    },
                )
            elif choice == 8:
                schema, data = {"items": [schema], "additionalItems": False}, [data]
            elif choice == 9:
                trigger = rng.choice(["__proto__", "constructor", "flag"])
                schema, data = (
                    {"dependencies": {trigger: ["needed"]}, "properties": {"payload": schema}},
                    {trigger: None, "payload": data},
                )
                if rng.choice([True, False]):
                    data["needed"] = 0
            else:
                trigger = rng.choice(["__proto__", "constructor", "flag"])
                schema = {"dependencies": {trigger: schema}}
                data = (
                    {**data, trigger: None}
                    if isinstance(data, dict)
                    else {trigger: None, "payload": data}
                )
            if rng.randrange(3) == 0:
                schema = {"$async": rng.choice([True, False, 1, "annotation", []]), **schema}
        embedded_identifier = None
        reference_mode = rng.randrange(3)
        if reference_mode == 0:
            keyword = rng.choice(["const", "enum", "default", "extension"])
            schema = {
                "$async": True,
                keyword: [schema] if keyword == "enum" else schema,
                "$ref": f"#/{keyword}/0" if keyword == "enum" else f"#/{keyword}",
            }
        elif reference_mode == 1:
            # Wrap only after composition so fragment references stay rooted at
            # this document, rather than being moved by subsequent wrappers.
            name = rng.choice(["generated", "__proto__", "constructor", "toString"])
            schema = {
                "definitions": {name: schema},
                "$ref": f"#/definitions/{name}",
                "type": rng.choice(["string", "integer", "array"]),
                "required": ["siblingOnly"],
            }
            if rng.choice([True, False]):
                identifier = rng.choice(
                    [
                        "part.json",
                        "root.json",
                        "../part.json",
                        "../../part.json",
                        "/part.json",
                        "__proto__",
                        "constructor",
                        "toString",
                    ]
                )
                embedded_identifier = identifier
                schema["definitions"][name] = {
                    "$id": identifier,
                    **schema["definitions"][name],
                }
                if rng.choice([True, False]):
                    schema["$ref"] = identifier
        if rng.choice([True, False]):
            # Repeated IDs belong to independent documents, including when
            # embedded resources use the same relative identifier.
            identifier = rng.choice(
                [
                    f"https://outputguard.test/generated/{index % 3}.json",
                    "root.json",
                    "__proto__",
                    "constructor",
                    "toString",
                ]
            )
            # Keep IDs unique within a document: resolving an embedded ID to
            # its root's URI would produce an ambiguous resource definition.
            if identifier == embedded_identifier:
                identifier += ".json"
            schema = {"$id": identifier, **schema}
        cases.append(
            {"name": f"seed-{seed}-case-{index}", "schema": schema, "text": json.dumps(data)}
        )
    return cases


def generate_diagnostic_cases(count: int, seed: int) -> list[dict]:
    """Compose false constraints with independently tracked instance locations."""
    rng = random.Random(seed)
    keys = [
        ("child", ".child"),
        ("__proto__", ".__proto__"),
        ("a/b", '["a/b"]'),
        ("a~b", '["a~b"]'),
        ("a%b", '["a%b"]'),
        ("", '[""]'),
        ("0", '["0"]'),
        ("é", '["é"]'),
        ("$id", ".$id"),
        ("$schema", ".$schema"),
        ("$ref", ".$ref"),
    ]
    cases = []
    for index in range(count):
        schema: bool | dict = False
        data = rng.choice([None, False, 0, 42, "wrong", [], {}])
        locations: list[tuple[str, list[str | int]]] = [("", [])]
        for _ in range(rng.randrange(1, 6)):
            choice = rng.randrange(6)
            if choice == 0:
                key, fragment = rng.choice(keys)
                schema, data = {"properties": {key: schema}}, {key: data}
                locations = [(fragment + path, [key, *steps]) for path, steps in locations]
            elif choice == 1:
                schema, data = {"items": schema}, [data, data]
                locations = [
                    (f"[{item}]" + path, [item, *steps])
                    for item in range(2)
                    for path, steps in locations
                ]
            elif choice == 2:
                schema, data = {"items": [True, schema]}, [None, data]
                locations = [("[1]" + path, [1, *steps]) for path, steps in locations]
            elif choice == 3:
                schema = {"allOf": [schema]}
            elif choice == 4:
                key = rng.choice(["entry", "__proto__", "x"])
                pattern = "^" + re.escape(key) + "$(?![\\s\\S])"
                schema, data = {"patternProperties": {pattern: schema}}, {key: data}
                locations = [(f".{key}" + path, [key, *steps]) for path, steps in locations]
            elif isinstance(schema, dict):
                schema, data = {"additionalProperties": schema}, {"entry": data}
                locations = [(".entry" + path, ["entry", *steps]) for path, steps in locations]
            else:
                schema = {"allOf": [schema]}

        keyword = rng.choice(["const", "enum", "default", "examples", "extension", "$async"])
        array = keyword in {"enum", "examples"}
        value = [schema] if array else schema
        if rng.choice([True, False]):
            schema = {keyword: value, "$ref": f"#/{keyword}/0" if array else f"#/{keyword}"}
        else:
            reference = f"#/definitions/holder/{keyword}" + ("/0" if array else "")
            schema = {
                "definitions": {
                    "resource": {
                        "$id": "part.json",
                        "definitions": {"holder": {keyword: value}},
                        "properties": {"value": {"$ref": reference}},
                    }
                },
                "$ref": "part.json",
            }
            data = {"value": data}
            locations = [(".value" + path, ["value", *steps]) for path, steps in locations]

        expected = []
        for path, steps in locations:
            value = data
            for step in steps:
                value = value[step]
            expected.append(("$" + path, value))
        expected.sort(key=lambda entry: entry[0])
        cases.append(
            {
                "name": f"diagnostics-seed-{seed}-case-{index}",
                "schema": schema,
                "text": json.dumps(data),
                "expected_paths": [path for path, _ in expected],
                "expected_values": [value for _, value in expected],
            }
        )
    return cases


def generate_resource_cases(count: int, seed: int) -> list[dict]:
    """Check resource declarations and pointer scopes against explicit outcomes."""
    rng = random.Random(seed)
    maps = {"definitions", "properties", "patternProperties", "dependencies"}
    arrays = {"allOf", "anyOf", "oneOf", "tupleItems"}
    declared = [
        "definitions",
        "properties",
        "patternProperties",
        "dependencies",
        "allOf",
        "anyOf",
        "oneOf",
        "items",
        "tupleItems",
        "additionalItems",
        "additionalProperties",
        "contains",
        "propertyNames",
        "not",
        "if",
        "then",
        "else",
    ]
    annotations = [
        "extension",
        "$defs",
        "dependentSchemas",
        "contentSchema",
        "unevaluatedProperties",
        "unevaluatedItems",
        "prefixItems",
        "const",
        "enum",
        "default",
        "examples",
        "$async",
    ]
    identifiers = [
        "part.json",
        "../part.json",
        "/part.json",
        "__proto__",
        "constructor",
        "urn:outputguard:resource",
        "#part",
    ]
    cases = []
    for index in range(count):
        mode = rng.randrange(13)
        identifier = rng.choice(identifiers)
        data = rng.choice([None, False, 0, 42, "wrong", [], {}])
        expected = {"valid": type(data) is int}
        unresolved = {"schema_error": "unresolvable"}
        target = {"$id": identifier, "type": "integer"}
        if mode in {0, 9}:
            keyword = "dependencies" if mode == 9 else rng.choice(declared)
            value = (
                {"part": target} if keyword in maps else [target] if keyword in arrays else target
            )
            schema = {"items" if keyword == "tupleItems" else keyword: value, "$ref": identifier}
            if mode == 9:
                entries = [("flag", rng.choice([[], ["needed"], True, False])), ("part", target)]
                if rng.choice([True, False]):
                    entries.reverse()
                schema["dependencies"] = dict(entries)
        elif mode in {1, 2}:
            keyword = rng.choice(annotations)
            if keyword in {"$defs", "dependentSchemas"}:
                value, pointer = {"part": target}, f"#/{keyword}/part"
            elif keyword in {"enum", "examples", "prefixItems"}:
                value, pointer = [target], f"#/{keyword}/0"
            else:
                value, pointer = target, f"#/{keyword}"
            schema = {keyword: value, "$ref": identifier if mode == 1 else pointer}
            if mode == 1:
                expected = unresolved
        elif mode == 3:
            schema = {
                "definitions": {
                    "part": {rng.choice(["$anchor", "$dynamicAnchor"]): "part", "type": "integer"}
                },
                "$ref": "#part",
            }
            expected = unresolved
        elif mode in {4, 5}:
            schema = {
                "definitions": {
                    "part": {"$id": identifier, "$ref": "#/definitions/integer"},
                    "integer": {"type": "integer"},
                },
                "$ref": identifier if mode == 4 else "#/definitions/part",
            }
            if mode == 4 and identifier != "#part":
                expected = unresolved
        elif mode == 6:
            literal = {"$id": identifier, "$anchor": "invalid anchor!", "$async": True, "value": 42}
            schema = {"const": literal}
            matches = rng.choice([True, False])
            data = literal if matches else {**literal, "value": "wrong"}
            expected = {"valid": matches}
        else:
            child = {
                "$id": rng.choice(
                    ["unregistered.json", "../unregistered.json", "../../unregistered.json"]
                ),
                "properties": {"next": {"$ref": "#"}},
            }
            schema = {
                "definitions": {"unrelated": {"$id": "/registered.json", "type": "object"}},
                "extension": {"properties": {"child": child}},
                "$ref": "#/extension" if mode == 7 else "#/extension/properties/child",
            }
            data = {"child": {"next": {}}} if mode == 7 else {"next": {}}
            expected = unresolved if mode == 7 else {"valid": True}
        if rng.choice([True, False]):
            schema["otherAnnotation"] = {
                "first": {"$id": identifier},
                "second": {"$id": identifier},
            }
        if rng.choice([True, False]):
            schema = {"$id": "folder/root.json", **schema}
        cases.append(
            {
                "name": f"resources-seed-{seed}-case-{index}",
                "schema": schema,
                "text": json.dumps(data),
                "expected_result": expected,
            }
        )
    return cases


def generate_fragment_cases(count: int, seed: int) -> list[dict]:
    """Check encoded references against independent validity and diagnostics."""
    rng = random.Random(seed)
    keys = ["part", "__proto__", "a/b", "a~b", "%2F", "%252F", "é", ""]
    values = [None, False, 0, 42, "wrong", [], {}]

    def pointer(*parts):
        text = "/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in parts)
        encoded = quote(text, safe="" if rng.choice([True, False]) else "/~")
        if encoded.startswith("/") and rng.choice([True, False]):
            encoded = rng.choice(["%2F", "%2f"]) + encoded[1:]
        return "#" + encoded

    cases = []
    for index in range(count):
        mode = rng.randrange(10)
        key = rng.choice(keys)
        data = rng.choice(values)
        failures = []
        unresolved = False
        if mode in {0, 2, 3}:
            integer = rng.choice([True, False])
            target = {"type": "integer"} if integer else False
            valid = integer and type(data) is int
            if not valid:
                failures = [("$", data)]
            if mode == 0:
                schema = {"definitions": {key: target}, "$ref": pointer("definitions", key)}
            elif mode == 2:
                keyword = rng.choice(["const", "default", "$async", "extension"])
                entries = [
                    ("flag", rng.choice([[], ["needed"], True, False])),
                    ("part", {"$id": "part.json", keyword: target}),
                ]
                if rng.choice([True, False]):
                    entries.reverse()
                schema = {"dependencies": dict(entries), "$ref": "part.json" + pointer(keyword)}
            else:
                name = rng.choice(
                    ["part", "UPPER", "node:part", "node.part", "node-part", "node_part"]
                )
                anchor = "#" + "".join(f"%{byte:02X}" for byte in name.encode())
                schema = {
                    "definitions": {key: {"$id": "#" + name, "allOf": [target]}},
                    "$ref": anchor,
                }
        elif mode == 1:
            keyword = rng.choice(["const", "enum", "default", "examples", "extension", "$async"])
            array = keyword in {"enum", "examples"}
            target = {"properties": {key: False}}
            parts = [keyword, "0"] if array else [keyword]
            schema = {keyword: [target] if array else target, "$ref": pointer(*parts)}
            if rng.choice([True, False]):
                data = {key: data}
                path = (
                    "." + key
                    if key in {"part", "__proto__"}
                    else "[" + json.dumps(key, ensure_ascii=False) + "]"
                )
                failures = [("$" + path, data[key])]
            else:
                data = {}
        elif mode == 4:
            schema = {
                "definitions": {"part": {"type": "integer"}},
                "$ref": pointer("definitions", "missing"),
            }
            unresolved = True
        elif mode == 5:
            literal = {"$ref": pointer("definitions", "part"), "type": "string"}
            schema = {
                "definitions": {"part": {"type": "integer"}},
                "default": literal,
                "properties": {
                    "value": {"$ref": pointer("default")},
                    "literal": {"const": literal},
                },
            }
            changed = rng.choice([True, False])
            value = rng.choice([42, "wrong"])
            other = {**literal, "type": "boolean"} if changed else literal
            data = {"value": value, "literal": other}
            if changed:
                failures.append(("$.literal", other))
            if value == "wrong":
                failures.append(("$.value", value))
        elif mode == 6:
            schema = {
                "definitions": {
                    "node": {
                        "type": "object",
                        "properties": {
                            "next": {"$ref": pointer("definitions", "node")},
                            "blocked": False,
                        },
                    }
                },
                "$ref": pointer("definitions", "node"),
            }
            invalid = rng.choice([True, False])
            data = {"blocked": data} if invalid else {}
            depth = rng.randrange(1, 5)
            if invalid:
                failures = [("$" + ".next" * depth + ".blocked", data["blocked"])]
            for _ in range(depth):
                data = {"next": data}
        elif mode == 7:
            schema = {"examples": [{"items": False}], "$ref": pointer("examples", "0")}
            data = [rng.choice(values) for _ in range(rng.randrange(3))]
            failures = [(f"$[{item}]", value) for item, value in enumerate(data)]
        elif mode in {8, 9}:
            token = rng.choice(
                ["0", "1", "01", "00", "-1", "-0", "+1", " 1", "1 ", "١", "１", "-", "2", "1.0", ""]
            )
            if mode == 8:
                keyword = rng.choice(
                    ["items", "allOf", "anyOf", "oneOf", "default", "enum", "examples", "extension"]
                )
                schema = {keyword: [{"type": "integer"}, {"type": "string"}]}
                parts = [keyword, token]
                unresolved = token not in {"0", "1"}
                valid = type(data) is int if token == "0" else isinstance(data, str)
            else:
                schema = {"definitions": {token: {"type": "integer"}}}
                parts = ["definitions", token]
                valid = type(data) is int
            if rng.choice([True, False]):
                schema = {"default": [schema]}
                parts = ["default", "0", *parts]
            reference = pointer(*parts)
            if rng.choice([True, False]):
                schema = {"definitions": {"resource": {"$id": "part.json", **schema}}}
                reference = "part.json" + reference
            schema["$ref"] = reference
            if not unresolved and not valid:
                failures = [("$", data)]
        else:
            if mode == 10:
                target = rng.choice([None, 0, 42, 1.5, "", "text", [], [True], [[False]]])
                unresolved = True
            elif mode == 11:
                target = rng.choice([True, False])
                if target is False:
                    failures = [("$", data)]
            else:
                target = rng.choice([None, 42, "text", True, False])
                unresolved = True
            keyword = rng.choice(["default", "const", "extension", "enum", "examples"])
            array = keyword in {"enum", "examples"}
            schema = {keyword: [target] if array else target}
            parts = [keyword, *(["0"] if array else [])]
            if mode == 12:
                parts.append(rng.choice(["0", "not", "$id"]))
            if rng.choice([True, False]):
                schema = {"default": [schema]}
                parts = ["default", "0", *parts]
            reference = pointer(*parts)
            if rng.choice([True, False]):
                schema = {
                    "dependencies": {"flag": ["needed"], "resource": {"$id": "part.json", **schema}}
                }
                reference = "part.json" + reference
            schema["$ref"] = reference
        if rng.choice([True, False]):
            schema = {"$id": "folder/root.json", **schema}
        failures.sort(key=lambda entry: entry[0])
        expected = (
            {"schema_error": "unresolvable"}
            if unresolved
            else {
                "valid": not failures,
                "paths": [path for path, _ in failures],
                "values": [value for _, value in failures],
            }
        )
        cases.append(
            {
                "name": f"fragments-seed-{seed}-case-{index}",
                "schema": schema,
                "text": json.dumps(data),
                "expected_result": expected,
            }
        )
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--js-repo", type=Path, default=Path("../outputguard-js"))
    parser.add_argument("--cases", type=positive_int, default=1200)
    parser.add_argument("--seed", type=int, default=2107)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--diagnostics",
        action="store_true",
        help="Check independently tracked error paths and values",
    )
    modes.add_argument(
        "--resources",
        action="store_true",
        help="Check expected resource discovery and pointer scopes",
    )
    modes.add_argument(
        "--fragments",
        action="store_true",
        help="Check URI-encoded references and diagnostics",
    )
    modes.add_argument(
        "--scopes",
        action="store_true",
        help="Check schema-map and pointer-data scopes",
    )
    modes.add_argument(
        "--evaluation",
        action="store_true",
        help="Check independently expected if/contains/not/oneOf resource scopes",
    )
    modes.add_argument(
        "--numeric",
        action="store_true",
        help="Check decimal multipleOf validity and source diagnostics",
    )
    modes.add_argument(
        "--formats",
        action="store_true",
        help="Check schema-format assertions and source diagnostics",
    )
    modes.add_argument(
        "--regex", action="store_true", help="Check ECMAScript matches and diagnostics"
    )
    args = parser.parse_args()
    cases = (
        generate_regex_cases(args.cases, args.seed)
        if args.regex
        else generate_format_cases(args.cases, args.seed)
        if args.formats
        else generate_numeric_cases(args.cases, args.seed)
        if args.numeric
        else generate_evaluation_cases(args.cases, args.seed)
        if args.evaluation
        else generate_scope_cases(args.cases, args.seed)
        if args.scopes
        else generate_fragment_cases(args.cases, args.seed)
        if args.fragments
        else generate_resource_cases(args.cases, args.seed)
        if args.resources
        else generate_diagnostic_cases(args.cases, args.seed)
        if args.diagnostics
        else generate_cases(args.cases, args.seed)
    )
    expected = []
    for case in cases:
        try:
            if (
                args.resources
                or args.fragments
                or args.scopes
                or args.evaluation
                or args.numeric
                or args.formats
                or args.regex
            ):
                try:
                    result = validate(case["text"], case["schema"])
                    actual = {"valid": result.valid}
                    if "paths" in case["expected_result"]:
                        errors = sorted(result.errors, key=lambda error: error.path)
                        actual.update(
                            paths=[error.path for error in errors],
                            values=[error.value for error in errors],
                        )
                except Unresolvable:
                    actual = {"schema_error": "unresolvable"}
                wanted = case["expected_result"]
                if not same_json(actual, wanted):
                    raise ValueError(json.dumps({"expected": wanted, "actual": actual}))
                expected.append(wanted)
                continue
            result = validate(case["text"], case["schema"])
            if args.diagnostics:
                errors = sorted(result.errors, key=lambda error: error.path)
                actual = {
                    "valid": result.valid,
                    "paths": [error.path for error in errors],
                    "values": [error.value for error in errors],
                }
                wanted = {
                    "valid": False,
                    "paths": case["expected_paths"],
                    "values": case["expected_values"],
                }
                if not same_json(actual, wanted):
                    raise ValueError(json.dumps({"expected": wanted, "actual": actual}))
                expected.append(wanted)
            else:
                expected.append(result.valid)
        except Exception as error:
            raise SystemExit(
                f"Python schema runner failed for {json.dumps(case, indent=2)}\n{error}"
            ) from error
    completed = subprocess.run(
        ["node", "--input-type=module", "--eval", _NODE_RUNNER],
        cwd=args.js_repo.resolve(),
        input=json.dumps(cases),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise SystemExit(f"JavaScript schema runner failed:\n{completed.stderr}")
    actual = json.loads(completed.stdout)
    if len(actual) != len(cases):
        raise SystemExit(f"Expected {len(cases)} results, received {len(actual)}")
    for case, python_valid, js_valid in zip(cases, expected, actual, strict=True):
        if not same_json(python_valid, js_valid):
            raise SystemExit(
                json.dumps(
                    {
                        **case,
                        "python_valid": python_valid,
                        "javascript_valid": js_valid,
                    },
                    indent=2,
                )
            )
    comparison = (
        "ECMAScript regex results"
        if args.regex
        else "Schema-format assertions"
        if args.formats
        else "Decimal numeric results"
        if args.numeric
        else "Evaluation scopes"
        if args.evaluation
        else "Schema map scopes"
        if args.scopes
        else "Encoded reference diagnostics"
        if args.fragments
        else "Resource resolution"
        if args.resources
        else "Validation diagnostics"
        if args.diagnostics
        else "Validation decisions"
    )
    print(f"{comparison} match for {len(cases)} generated cases (seed {args.seed})")


if __name__ == "__main__":
    main()
