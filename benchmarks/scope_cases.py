"""Generate schema-map and pointer-data scope cases with explicit outcomes."""

import json
import random
from urllib.parse import quote


def generate_scope_cases(count: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    maps = ["definitions", "properties", "patternProperties", "dependencies"]
    reserved = ["properties", "patternProperties", "definitions", "dependencies", "enum"]
    names = [*reserved, "%2F", "a/b", "$id", "__proto__"]
    values = [None, False, 0, 42, "wrong", [], {}]

    def pointer(*parts):
        path = "/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in parts)
        return "#" + quote(path, safe="" if rng.choice([True, False]) else "/~")

    def wrap(target):
        container = rng.choice(["dependencies", "items", "tupleItems"])
        if container == "dependencies":
            return {"dependencies": {"part": target}}, ["dependencies", "part"]
        if container == "items":
            return {"items": target}, ["items"]
        return {"items": [target]}, ["items", "0"]

    def resource():
        return {
            "$id": "folder/part.json",
            "definitions": {"leaf": {"$id": "leaf.json", "type": "integer"}},
            "properties": {"value": {"$ref": "leaf.json"}},
        }

    cases = []
    for index in range(count):
        mode = rng.randrange(12)
        value = rng.choice(values)
        failures = []
        unresolved = False
        if mode == 0:
            metadata = rng.choice([[], ["needed"], True, False, {"type": "null"}])
            schema = {
                "dependencies": {"$id": metadata, "part": {"type": "integer"}},
                "$ref": pointer("dependencies", "part"),
            }
            data = value
            if type(value) is not int:
                failures = [("$", value)]
        elif mode == 1:
            depth = rng.randrange(1, 4)
            target = {
                "$id": f"dir{depth - 1}/part.json",
                "definitions": {"leaf": {"$id": "leaf.json", "type": "integer"}},
                "properties": {"value": {"$ref": "leaf.json"}},
            }
            parts = []
            for level in reversed(range(depth)):
                keyword, name = rng.choice(maps), rng.choice(names)
                if level:
                    target = {"$id": f"dir{level - 1}/part.json", keyword: {name: target}}
                else:
                    target = {keyword: {name: target}}
                parts = [keyword, name, *parts]
            schema = target
            schema["$ref"] = (
                pointer(*parts)
                if rng.choice([True, False])
                else "/".join(f"dir{level}" for level in range(depth)) + "/part.json"
            )
            data = {"value": value}
            if type(value) is not int:
                failures = [("$.value", value)]
        elif mode in {2, 3}:
            registered = rng.choice([True, False])
            annotation = {
                "$id": "other.json" if registered else "unregistered.json",
                "properties": {"value": {"$ref": "#/definitions/integer"}},
            }
            keyword = rng.choice(["const", "default", "enum", "examples", "extension", "$async"])
            array = keyword in {"enum", "examples"}
            if mode == 3:
                annotation = {"properties": {"child": annotation}}
            schema, parts = wrap({keyword: [annotation] if array else annotation})
            schema["definitions"] = {"integer": {"type": "integer"}}
            if registered:
                schema["definitions"]["other"] = {
                    "$id": "other.json",
                    "definitions": {"integer": {"type": "string"}},
                }
            parts += [keyword, *(["0"] if array else [])]
            if mode == 3 and rng.choice([True, False]):
                schema["$ref"] = pointer(*parts)
                data = {"child": {"value": value}}
                unresolved = not registered
                if registered and not isinstance(value, str):
                    failures = [("$.child.value", value)]
            else:
                schema["$ref"] = pointer(*parts, *(["properties", "child"] if mode == 3 else []))
                data = {"value": value}
                if type(value) is not int:
                    failures = [("$.value", value)]
        elif mode == 4:
            keyword = rng.choice(maps)
            literal = {"flag": False, "ref": "#%2Fdefinitions%2Fpart"}
            schema = {keyword: {"const": literal}, "$ref": pointer(keyword)}
            changed = rng.choice([True, False])
            data = {**literal, "flag": 0} if changed else literal
            if changed:
                failures = [("$", data)]
        elif mode == 5:
            name = rng.choice(reserved)
            schema = {"properties": {name: resource()}, "additionalProperties": False}
            data = {name: {"value": value}}
            if type(value) is not int:
                failures = [("$." + name + ".value", value)]
            if rng.choice([True, False]):
                data["outputguardAsync0Data0"] = 0
                failures.insert(0, ("$", data))
        elif mode == 6:
            keyword, name = rng.choice(maps), rng.choice(reserved)
            schema = {"definitions": {"integer": {"type": "integer"}}}
            schema.setdefault(keyword, {})[name] = {
                "$id": "ignored.json",
                "$ref": "#/definitions/integer",
                "type": "string",
            }
            unresolved = rng.choice([True, False])
            schema["$ref"] = "ignored.json" if unresolved else pointer(keyword, name)
            data = value
            if not unresolved and type(value) is not int:
                failures = [("$", value)]
        elif mode == 7:
            schema = {
                "dependencies": {"$id": ["needed"], "part": {"properties": {"blocked": False}}},
                "properties": {"payload": {"$ref": pointer("dependencies", "part")}},
            }
            data = {"$id": None, "payload": {}}
            if rng.choice([True, False]):
                data["payload"]["blocked"] = value
                failures.append(("$.payload.blocked", value))
            if rng.choice([True, False]):
                data["needed"] = 0
            else:
                failures.insert(0, ("$", data))
        elif mode == 8:
            keyword, name = rng.choice(maps), rng.choice(reserved)
            schema = {
                keyword: {
                    name: {
                        "$id": "folder/node.json",
                        "type": "object",
                        "properties": {"next": {"$ref": "#"}, "blocked": False},
                    }
                },
                "$ref": pointer(keyword, name),
            }
            invalid = rng.choice([True, False])
            depth = rng.randrange(1, 5)
            data = {"blocked": value} if invalid else {}
            if invalid:
                failures = [("$" + ".next" * depth + ".blocked", value)]
            for _ in range(depth):
                data = {"next": data}
        elif mode == 9:
            shared = {rng.choice(reserved): resource()}
            name = next(iter(shared))
            schema = {
                "definitions": shared,
                "properties": {
                    "literal": {"const": shared},
                    "value": {"$ref": pointer("definitions", name)},
                },
            }
            changed = rng.choice([True, False])
            other = {name: {**shared[name], "$id": "wrong.json"}} if changed else shared
            data = {"literal": other, "value": {"value": value}}
            if changed:
                failures.append(("$.literal", other))
            if type(value) is not int:
                failures.append(("$.value.value", value))
        elif mode == 10:
            schema = {
                "definitions": {
                    "integer": {"type": "integer"},
                    "const": {
                        "$id": "other.json",
                        "definitions": {"integer": {"type": "string"}},
                        "properties": {"value": {"$ref": "#/definitions/integer"}},
                    },
                },
                "properties": {
                    "first": {"$ref": pointer("definitions")},
                    "second": {"$ref": pointer("definitions", "const")},
                },
            }
            data = {"first": 0, "second": {"value": value}}
            failures = [("$.first", 0)]
            if not isinstance(value, str):
                failures.append(("$.second.value", value))
        else:
            node = {
                "$id": "part.json",
                "definitions": {"integer": {"type": "integer"}},
                "dependencies": {
                    "part": {
                        "extension": {
                            "$id": "other.json",
                            "properties": {"value": {"$ref": "#/definitions/integer"}},
                        }
                    }
                },
            }
            location = rng.choice(
                [
                    *maps,
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
            )
            if location in maps:
                field = {"resource": node}
            elif location in {"allOf", "anyOf", "oneOf", "tupleItems"}:
                field = [node]
            else:
                field = node
            schema = {
                "items" if location == "tupleItems" else location: field,
                "$ref": "part.json" + pointer("dependencies", "part", "extension"),
            }
            schema.setdefault("definitions", {})["other"] = {
                "$id": "other.json",
                "definitions": {"integer": {"type": "string"}},
            }
            data = {"value": value}
            if type(value) is not int:
                failures = [("$.value", value)]
        if rng.choice([True, False]):
            schema = {"$id": "root.json", **schema}
        failures.sort(key=lambda entry: entry[0])
        expected = (
            {"schema_error": "unresolvable"}
            if unresolved
            else {
                "valid": not failures,
                "paths": [path for path, _ in failures],
                "values": [actual for _, actual in failures],
            }
        )
        cases.append(
            {
                "name": f"scopes-seed-{seed}-case-{index}",
                "schema": schema,
                "text": json.dumps(data),
                "expected_result": expected,
            }
        )
    return cases
