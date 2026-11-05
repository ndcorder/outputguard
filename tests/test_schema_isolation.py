import json

import pytest
from referencing.exceptions import Unresolvable

import outputguard

PROTOTYPE_NAMES = [
    "__proto__",
    "constructor",
    "toString",
    "toLocaleString",
    "valueOf",
    "hasOwnProperty",
    "isPrototypeOf",
    "propertyIsEnumerable",
    "__defineGetter__",
    "__defineSetter__",
    "__lookupGetter__",
    "__lookupSetter__",
]


@pytest.mark.parametrize("identifier", PROTOTYPE_NAMES)
def test_prototype_names_are_valid_relative_root_identifiers(identifier):
    schema = {"$id": identifier, "type": "integer"}
    assert outputguard.validate("42", schema).valid
    assert not outputguard.validate('"wrong"', schema).valid
    assert outputguard.validate("42", schema.copy()).valid


@pytest.mark.parametrize("root_id", [None, "root.json", "https://outputguard.test/root.json"])
@pytest.mark.parametrize("identifier", PROTOTYPE_NAMES)
def test_prototype_names_are_valid_embedded_identifiers(root_id, identifier):
    schema = {
        **({"$id": root_id} if root_id else {}),
        "definitions": {"part": {"$id": identifier, "type": "integer"}},
        "$ref": identifier,
    }
    assert outputguard.validate("42", schema).valid
    assert not outputguard.validate('"wrong"', schema).valid


@pytest.mark.parametrize("identifier", PROTOTYPE_NAMES)
def test_missing_prototype_named_external_resources_do_not_resolve(identifier):
    with pytest.raises(Unresolvable, match=identifier):
        outputguard.validate("42", {"$ref": identifier})


@pytest.mark.parametrize("name", ["__proto__", "constructor", "constructor/prototype", "toString"])
def test_missing_prototype_named_pointer_properties_do_not_resolve(name):
    with pytest.raises(Unresolvable):
        outputguard.validate("42", {"definitions": {}, "$ref": f"#/definitions/{name}"})


@pytest.mark.parametrize("name", PROTOTYPE_NAMES)
def test_explicit_prototype_named_pointer_properties_resolve(name):
    schema = {"definitions": {name: {"type": "integer"}}, "$ref": f"#/definitions/{name}"}
    assert outputguard.validate("42", schema).valid
    assert not outputguard.validate('"wrong"', schema).valid


def test_recursion_through_relative_root_identifier():
    schema = {
        "$id": "constructor",
        "properties": {"value": {"type": "integer"}, "next": {"$ref": "constructor"}},
    }
    assert outputguard.validate('{"value":1,"next":{"value":2}}', schema).valid
    failed = outputguard.validate('{"value":1,"next":{"value":"wrong"}}', schema)
    assert not failed.valid
    assert failed.errors[0].path == "$.next.value"


def test_caller_identifiers_resembling_javascript_internal_base_do_not_collide():
    schema = {
        "$id": "constructor",
        "definitions": {"string": {"$id": "outputguard-document-0:/constructor", "type": "string"}},
        "properties": {
            "local": {"$ref": "constructor"},
            "external": {"$ref": "outputguard-document-0:/constructor"},
        },
        "type": "object",
    }
    assert outputguard.validate('{"local":{},"external":"text"}', schema).valid
    assert not outputguard.validate('{"local":"wrong","external":"text"}', schema).valid
    assert not outputguard.validate('{"external":42}', schema).valid


@pytest.mark.parametrize(
    "identifier", ["root.json", "../part.json", "../../part.json", "/part.json"]
)
def test_anonymous_roots_are_distinct_from_embedded_resources(identifier):
    schema = {
        "definitions": {"part": {"$id": identifier, "type": "integer"}},
        "$ref": identifier,
    }
    assert outputguard.validate("42", schema).valid
    assert not outputguard.validate('"wrong"', schema).valid


def test_parent_relative_local_and_rooted_resource_ids_are_distinct():
    schema = {
        "definitions": {
            "parent": {"$id": "../part.json", "type": "integer"},
            "grandparent": {"$id": "../../part.json", "type": "null"},
            "local": {"$id": "part.json", "type": "string"},
            "rooted": {"$id": "/part.json", "type": "boolean"},
        },
        "properties": {
            "parent": {"$ref": "../part.json"},
            "grandparent": {"$ref": "../../part.json"},
            "local": {"$ref": "part.json"},
            "rooted": {"$ref": "/part.json"},
        },
    }
    assert outputguard.validate(
        '{"parent":42,"grandparent":null,"local":"text","rooted":true}', schema
    ).valid
    for key, value in [("parent", "wrong"), ("grandparent", 42), ("local", 42), ("rooted", 42)]:
        failed = outputguard.validate(json.dumps({key: value}), schema)
        assert not failed.valid
        assert failed.errors[0].path == f"$.{key}"


@pytest.mark.parametrize(
    "path", ["/outputguard-document-0/part.json", "/outputguard-document-%30/part.json"]
)
def test_caller_paths_resembling_javascript_internal_namespace_do_not_collide(path):
    schema = {
        "definitions": {
            "local": {"$id": "part.json", "type": "integer"},
            "rooted": {"$id": path, "type": "string"},
        },
        "properties": {"local": {"$ref": "part.json"}, "rooted": {"$ref": path}},
    }
    assert outputguard.validate('{"local":42,"rooted":"text"}', schema).valid
    assert not outputguard.validate('{"local":"wrong"}', schema).valid
    assert not outputguard.validate('{"rooted":42}', schema).valid


def test_pointers_use_the_referenced_resource():
    schema = {
        "definitions": {
            "constructor": {"type": "integer"},
            "resource": {
                "$id": "part.json",
                "definitions": {},
                "$ref": "#/definitions/constructor",
            },
        },
        "$ref": "part.json",
    }
    with pytest.raises(Unresolvable):
        outputguard.validate("42", schema)


def test_unused_unresolved_references_are_not_evaluated():
    schema = {
        "definitions": {"unused": {"$ref": "#/definitions/constructor"}},
        "type": "integer",
    }
    assert outputguard.validate("42", schema).valid


def test_missing_prototype_named_meta_schema_pointer_does_not_resolve():
    with pytest.raises(Unresolvable):
        outputguard.validate(
            "42", {"$ref": "http://json-schema.org/draft-07/schema#/definitions/__proto__"}
        )


@pytest.mark.parametrize(
    "identifier",
    [
        "urn:outputguard:repeated-root",
        "https://outputguard.test/repeated-root.json",
        "repeated-root.json",
    ],
)
def test_independent_copies_can_reuse_root_identifiers(identifier):
    for _ in range(3):
        assert outputguard.validate("42", {"$id": identifier, "type": "integer"}).valid


def test_reused_ids_do_not_share_constraints():
    integer = {"$id": "urn:outputguard:changed-root", "type": "integer"}
    string = {"$id": integer["$id"], "type": "string"}
    for _ in range(3):
        assert outputguard.validate("42", integer).valid
        assert outputguard.validate('"text"', string).valid
        assert not outputguard.validate('"text"', integer).valid
        assert not outputguard.validate("42", string).valid


def test_nested_resources_are_local_to_each_document():
    def document(type_name):
        return {
            "$id": "https://outputguard.test/resource-root.json",
            "definitions": {"part": {"$id": "part.json", "type": type_name}},
            "$ref": "part.json",
        }

    integer, string = document("integer"), document("string")
    assert outputguard.validate("42", integer).valid
    assert outputguard.validate('"text"', string).valid
    assert not outputguard.validate('"text"', integer).valid
    assert not outputguard.validate("42", string).valid


def test_anonymous_documents_can_reuse_nested_identifiers():
    for type_name, text in [("integer", "42"), ("string", '"text"')]:
        schema = {
            "definitions": {
                "part": {"$id": "urn:outputguard:anonymous-resource", "type": type_name}
            },
            "$ref": "urn:outputguard:anonymous-resource",
        }
        assert outputguard.validate(text, schema).valid


def test_prior_documents_do_not_supply_missing_resources():
    identifier = "urn:outputguard:root-with-resource"
    resource = "urn:outputguard:previous-resource"
    assert outputguard.validate(
        "42",
        {
            "$id": identifier,
            "definitions": {"slot": {"$id": resource, "type": "integer"}},
            "$ref": resource,
        },
    ).valid
    with pytest.raises(Unresolvable, match=resource):
        outputguard.validate(
            '"text"',
            {"$id": identifier, "definitions": {"slot": {"type": "string"}}, "$ref": resource},
        )
    with pytest.raises(Unresolvable, match=resource):
        outputguard.validate("42", {"$ref": resource})


def test_root_identifiers_are_not_registered_for_subsequent_calls():
    identifier = "urn:outputguard:unregistered-external"
    assert outputguard.validate("42", {"$id": identifier, "type": "integer"}).valid
    with pytest.raises(Unresolvable, match=identifier):
        outputguard.validate("42", {"$ref": identifier})


def test_recursive_documents_can_share_an_id():
    def document(type_name):
        return {
            "$id": "urn:outputguard:recursive-isolation",
            "type": "object",
            "properties": {"value": {"type": type_name}, "next": {"$ref": "#"}},
        }

    integer, string = document("integer"), document("string")
    assert outputguard.validate('{"value":1,"next":{"value":2}}', integer).valid
    assert outputguard.validate('{"value":"a","next":{"value":"b"}}', string).valid
    result = outputguard.validate('{"value":1,"next":{"value":"wrong"}}', integer)
    assert not result.valid
    assert result.errors[0].path == "$.next.value"


def test_failed_reference_compilations_do_not_reserve_identifiers():
    identifier = "urn:outputguard:failed-reference"
    with pytest.raises(Unresolvable, match="urn:outputguard:missing"):
        outputguard.validate("42", {"$id": identifier, "$ref": "urn:outputguard:missing"})
    assert outputguard.validate("42", {"$id": identifier, "type": "integer"}).valid


def test_compatibility_preparation_does_not_mix_identifiers():
    for type_name, value in [("integer", 42), ("string", "text")]:
        schema = {
            "$id": "urn:outputguard:prepared-id",
            "properties": {"__proto__": {"type": type_name}},
            "dependencies": {"__proto__": ["required"]},
        }
        assert outputguard.validate(json.dumps({"__proto__": value, "required": 0}), schema).valid
        result = outputguard.validate(json.dumps({"__proto__": value}), schema)
        assert len(result.errors) == 1


def test_guards_and_batch_helpers_do_not_share_id_registrations():
    identifier = "urn:outputguard:guard-isolation"
    assert outputguard.OutputGuard().validate("42", {"$id": identifier, "type": "integer"}).valid
    assert outputguard.OutputGuard().validate('"text"', {"$id": identifier, "type": "string"}).valid
    batch = outputguard.validate_batch(["42", '"text"'], {"$id": identifier, "type": "integer"})
    assert batch.summary.valid == 1
    assert outputguard.validate_and_repair(
        '```json\n"text"\n```', {"$id": identifier, "type": "string"}
    ).valid


def test_builtin_meta_schema_references_are_available():
    schema = {"$ref": "http://json-schema.org/draft-07/schema#"}
    assert outputguard.validate('{"type":"integer"}', schema).valid
    assert not outputguard.validate('{"type":"invalid"}', schema).valid
