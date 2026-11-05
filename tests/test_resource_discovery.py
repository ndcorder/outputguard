import json

import pytest
from referencing.exceptions import Unresolvable

import outputguard

ANNOTATIONS = [
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
]


def annotation(keyword, target):
    if keyword in {"$defs", "dependentSchemas"}:
        return {"part": target}, f"#/{keyword}/part"
    if keyword in {"enum", "examples", "prefixItems"}:
        return [target], f"#/{keyword}/0"
    return target, f"#/{keyword}"


@pytest.mark.parametrize(
    "keyword",
    [
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
    ],
)
def test_draft_seven_schema_locations_declare_resource_ids(keyword):
    part = {"$id": "part.json", "type": "integer"}
    if keyword in {"definitions", "properties", "patternProperties", "dependencies"}:
        value = {"part": part}
    elif keyword in {"allOf", "anyOf", "oneOf", "tupleItems"}:
        value = [part]
    else:
        value = part
    schema = {"items" if keyword == "tupleItems" else keyword: value, "$ref": "part.json"}
    assert outputguard.validate("42", schema).valid
    assert not outputguard.validate('"wrong"', schema).valid


@pytest.mark.parametrize("identifier", ["", "#", "#/fake"])
def test_id_fragments_cannot_replace_the_document_or_pointer_targets(identifier):
    schema = {"definitions": {"part": {"$id": identifier, "type": "integer"}}, "type": "object"}
    assert outputguard.validate("{}", schema).valid
    assert outputguard.validate("42", {**schema, "$ref": "#/definitions/part"}).valid
    with pytest.raises(Unresolvable):
        outputguard.validate("42", {**schema, "$ref": "#/fake"})
    assert outputguard.validate(
        '"text"', {**schema, "fake": {"type": "string"}, "$ref": "#/fake"}
    ).valid


@pytest.mark.parametrize("keyword", ANNOTATIONS)
def test_annotation_ids_are_not_registered_but_explicit_pointers_work(keyword):
    value, pointer = annotation(keyword, {"$id": "part.json", "type": "integer"})
    with pytest.raises(Unresolvable):
        outputguard.validate("42", {keyword: value, "$ref": "part.json"})
    schema = {keyword: value, "$ref": pointer}
    assert outputguard.validate("42", schema).valid
    assert not outputguard.validate('"wrong"', schema).valid


@pytest.mark.parametrize("keyword", ["$anchor", "$dynamicAnchor"])
def test_later_draft_anchors_are_ignored(keyword):
    target = {keyword: "part", "type": "integer"}
    with pytest.raises(Unresolvable):
        outputguard.validate("42", {"definitions": {"part": target}, "$ref": "#part"})
    assert outputguard.validate(
        "42", {"definitions": {"part": target}, "$ref": "#/definitions/part"}
    ).valid
    assert outputguard.validate("42", {keyword: "invalid anchor!", "type": "integer"}).valid
    for allowed in [True, False]:
        assert (
            outputguard.validate("null", {keyword: allowed, "$ref": f"#/{keyword}"}).valid
            is allowed
        )


def test_reference_id_siblings_do_not_declare_resources_or_change_pointer_scope():
    definitions = {
        "part": {"$id": "folder/part.json", "$ref": "#/definitions/integer"},
        "integer": {"type": "integer"},
    }
    with pytest.raises(Unresolvable):
        outputguard.validate("42", {"definitions": definitions, "$ref": "folder/part.json"})
    schema = {"definitions": definitions, "$ref": "#/definitions/part"}
    assert outputguard.validate("42", schema).valid
    assert not outputguard.validate('"wrong"', schema).valid


def test_root_id_beside_reference_does_not_change_relative_child_resolution():
    schema = {
        "$id": "folder/root.json",
        "definitions": {"part": {"$id": "part.json", "type": "integer"}},
    }
    assert outputguard.validate("42", {**schema, "$ref": "part.json"}).valid
    with pytest.raises(Unresolvable):
        outputguard.validate("42", {**schema, "$ref": "../folder/part.json"})


def test_legacy_fragment_anchors_remain_available_on_reference_nodes():
    schema = {
        "definitions": {
            "part": {"$id": "#part", "$ref": "#/definitions/integer"},
            "integer": {"type": "integer"},
        },
        "$ref": "#part",
    }
    assert outputguard.validate("42", schema).valid
    assert not outputguard.validate('"wrong"', schema).valid


def test_annotation_id_is_ignored_when_a_pointer_selects_it():
    schema = {
        "definitions": {"integer": {"type": "integer"}},
        "extension": {"$id": "folder/part.json", "$ref": "#/definitions/integer"},
        "$ref": "#/extension",
    }
    assert outputguard.validate("42", schema).valid
    assert not outputguard.validate('"wrong"', schema).valid


def test_annotation_descendant_scope_remains_distinct_from_declared_resources():
    child = {"$id": "../part.json", "properties": {"next": {"$ref": "#"}}}
    schema = {
        "definitions": {"unrelated": {"$id": "/part.json", "type": "object"}},
        "extension": {"properties": {"child": child}},
        "$ref": "#/extension",
    }
    with pytest.raises(Unresolvable):
        outputguard.validate('{"child":{"next":{}}}', schema)
    assert outputguard.validate(
        '{"next":{}}', {**schema, "$ref": "#/extension/properties/child"}
    ).valid


@pytest.mark.parametrize("constraint", [False, {"type": "integer"}])
def test_prototype_constraints_work_under_unregistered_scopes(constraint):
    schema = {
        "extension": {
            "properties": {"child": {"$id": "part.json", "properties": {"__proto__": constraint}}}
        },
        "$ref": "#/extension",
    }
    assert outputguard.validate('{"child":{}}', schema).valid
    failed = outputguard.validate('{"child":{"__proto__":"wrong"}}', schema)
    assert not failed.valid
    assert failed.errors[0].path == "$.child.__proto__"
    assert failed.errors[0].value == "wrong"


def test_duplicate_annotation_ids_do_not_collide_with_each_other_or_real_resources():
    schema = {
        "extension": {"first": {"$id": "part.json"}, "second": {"$id": "part.json"}},
        "type": "integer",
    }
    assert outputguard.validate("42", schema).valid
    assert outputguard.validate(
        "42",
        {
            **schema,
            "definitions": {"actual": {"$id": "part.json", "type": "integer"}},
            "$ref": "part.json",
        },
    ).valid
    with pytest.raises(Unresolvable):
        outputguard.validate("42", {**schema, "$ref": "part.json"})


def test_literal_metadata_keeps_original_values():
    literal = {"$id": "part.json", "$anchor": "invalid anchor!", "$async": True}
    before = literal.copy()
    assert outputguard.validate(json.dumps(literal), {"const": literal}).valid
    assert not outputguard.validate('{"$id":"wrong"}', {"const": literal}).valid
    assert literal == before


@pytest.mark.parametrize("other", [[], ["needed"], True, False])
@pytest.mark.parametrize("schema_first", [True, False])
@pytest.mark.parametrize("identifier", ["part.json", "../part.json", "#part", "__proto__"])
def test_mixed_dependencies_discover_schema_ids_in_either_order(other, schema_first, identifier):
    entries = [("flag", other), ("part", {"$id": identifier, "type": "integer"})]
    if schema_first:
        entries.reverse()
    schema = {"dependencies": dict(entries), "$ref": identifier}
    before = json.dumps(schema)
    assert outputguard.validate("42", schema).valid
    failed = outputguard.validate('"wrong"', schema)
    assert not failed.valid
    assert failed.errors[0].path == "$"
    assert failed.errors[0].value == "wrong"
    assert json.dumps(schema) == before


@pytest.mark.parametrize("schema_first", [True, False])
def test_mixed_dependencies_keep_assertions_pointer_targets_and_false_paths(schema_first):
    entries = [
        ("flag", ["needed"]),
        ("part", {"$id": "part.json", "properties": {"blocked": False}}),
        ("forbidden", False),
    ]
    if schema_first:
        entries.reverse()
    schema = {"dependencies": dict(entries), "properties": {"payload": {"$ref": "part.json"}}}
    assert outputguard.validate('{"flag":null,"needed":0,"payload":{}}', schema).valid
    failed = outputguard.validate('{"flag":null,"payload":{"blocked":42}}', schema)
    assert not failed.valid
    assert [(error.path, error.value) for error in failed.errors] == [
        ("$", {"flag": None, "payload": {"blocked": 42}}),
        ("$.payload.blocked", 42),
    ]
    forbidden = outputguard.validate('{"forbidden":null,"payload":{}}', schema)
    assert not forbidden.valid
    assert forbidden.errors[0].schema_path == "$.dependencies.forbidden"
    assert outputguard.validate("{}", {**schema, "$ref": "#/dependencies/part"}).valid
    assert not outputguard.validate("null", {**schema, "$ref": "#/dependencies/forbidden"}).valid


def test_mixed_dependencies_preserve_nested_scopes_and_later_missing_lookups():
    schema = {
        "definitions": {
            "container": {
                "$id": "folder/container.json",
                "dependencies": {
                    "flag": ["needed"],
                    "part": {"$id": "part.json", "properties": {"blocked": False}},
                },
            }
        },
        "$ref": "folder/part.json",
    }
    assert outputguard.validate("{}", schema).valid
    failed = outputguard.validate('{"blocked":42}', schema)
    assert failed.errors[0].path == "$.blocked"
    with pytest.raises(Unresolvable):
        outputguard.validate("{}", {**schema, "$ref": "folder/missing.json"})


def test_mixed_dependencies_do_not_promote_annotation_ids_or_change_literal_data():
    dependencies = {"flag": ["needed"], "part": {"$id": "part.json", "type": "integer"}}
    literal = {"dependencies": dependencies}
    assert outputguard.validate(json.dumps(literal), {"const": literal}).valid
    with pytest.raises(Unresolvable):
        outputguard.validate("42", {"extension": literal, "$ref": "part.json"})
    assert outputguard.validate("{}", {"extension": literal, "$ref": "#/extension"}).valid
