import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from jsonschema import Draft7Validator, SchemaError

from outputguard import guarded_generate, validate, validate_and_repair, validate_batch
from outputguard.regex import _runtime, search

CASES = json.loads((Path(__file__).parents[1] / "benchmarks/regex_cases.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
@pytest.mark.parametrize("location", ["root", "property", "reference"])
def test_ecmascript_pattern_assertions(case, location):
    schema = {"pattern": case["pattern"]}
    data, path = case["text"], "$"
    if location == "property":
        schema = {"properties": {"a/b": schema}}
        data, path = {"a/b": data}, '$["a/b"]'
    elif location == "reference":
        schema = {"default": schema, "$ref": "#/default"}
    result = validate(json.dumps(data), schema)
    assert result.valid is case["valid"]
    assert result.parse_error is None and result.data == data
    assert [(error.path, error.value) for error in result.errors] == (
        [] if case["valid"] else [(path, case["text"])]
    )
    if not case["valid"]:
        assert result.errors[0].schema_path.endswith(".pattern")


@pytest.mark.parametrize("case", [case for case in CASES if isinstance(case["text"], str)])
def test_pattern_properties_and_closed_objects_use_the_same_engine(case):
    # A matched key is schema-rejected; an unmatched key is accepted by its
    # additional-property schema. This exposes both matching and classification.
    schema = {
        "patternProperties": {case["pattern"]: {"type": "string"}},
        "additionalProperties": {"type": "number"},
    }
    text = json.dumps({case["text"]: 1})
    result = validate(text, schema)
    assert result.valid is not case["valid"]
    if case["valid"]:
        assert result.errors[0].value == 1
    schema = {"patternProperties": {case["pattern"]: True}, "additionalProperties": False}
    assert validate(text, schema).valid is case["valid"]


@pytest.mark.parametrize("expression", ["[", "(", "*", r"(?P<name>a)", r"\q", r"a\Z"])
@pytest.mark.parametrize("keyword", ["pattern", "patternProperties"])
def test_invalid_pattern_schemas_raise_schema_errors(expression, keyword):
    schema = {keyword: expression if keyword == "pattern" else {expression: False}}
    with pytest.raises(SchemaError, match="Invalid ECMAScript regular expression"):
        validate('"a"', schema)


def test_patterns_with_duplicate_capture_names_stay_independent():
    schema = {
        "patternProperties": {r"^(?<part>a)$": True, r"^(?<part>b)$": True},
        "additionalProperties": False,
    }
    assert validate('{"a":1,"b":2}', schema).valid
    assert not validate('{"c":3}', schema).valid


def test_property_patterns_preserve_independent_numeric_backreferences_and_empty_patterns():
    schema = {
        "patternProperties": {r"^(a)\1$": True, r"^(b)\1$": True},
        "additionalProperties": False,
    }
    assert validate('{"aa":1,"bb":2}', schema).valid
    result = validate('{"x":1}', {"patternProperties": {"": False}, "additionalProperties": False})
    assert [(error.path, error.value) for error in result.errors] == [("$.x", 1)]


@pytest.mark.parametrize("count", [1, 7, 8, 9, 31, 1000])
def test_property_map_matching_preserves_partial_matches_and_declared_keys(count):
    schema = {
        "properties": {"__proto__": True},
        "patternProperties": {r"^even_(?<index>[0-9]+)$": {"type": "integer"}},
        "additionalProperties": {"type": "string"},
    }
    data = {"__proto__": None}
    for index in range(count):
        data[f"even_{index}"] = index
        data[f"odd_{index}"] = str(index)
    assert validate(json.dumps(data), schema).valid
    for key, value in [("even_0", "wrong"), ("odd_0", 0)]:
        result = validate(json.dumps({**data, key: value}), schema)
        assert [(error.path, error.value) for error in result.errors] == [("$." + key, value)]


@pytest.mark.parametrize(
    "key,path",
    [
        ("\ud800", '$["\\ud800"]'),
        ("\udc00", '$["\\udc00"]'),
        ("😀", '$["😀"]'),
        ("Ω", '$["Ω"]'),
        ("a\\b", '$["a\\\\b"]'),
    ],
)
@pytest.mark.parametrize("keyword", ["patternProperties", "additionalProperties"])
def test_regex_key_error_paths_use_well_formed_json(key, path, keyword):
    constraint = {"type": "string"}
    schema = {keyword: {".*": constraint} if keyword == "patternProperties" else constraint}
    result = validate(json.dumps({key: 1}), schema)
    assert [(error.path, error.value) for error in result.errors] == [(path, 1)]


@pytest.mark.parametrize("format", ["json", "yaml", "python", "toml"])
def test_ecmascript_checks_after_each_document_parser(format):
    text = 'value = "１２"' if format == "toml" else '{"value":"１２"}'
    result = validate(text, {"properties": {"value": {"pattern": r"^\d+$"}}}, format=format)
    assert not result.valid and result.parse_error is None
    assert [(error.path, error.value) for error in result.errors] == [("$.value", "１２")]


def test_ecmascript_schema_failures_survive_repairs_and_generation_feedback():
    schema = {"properties": {"value": {"pattern": r"^\d+$"}}}
    result = validate_and_repair('{"value":"１２",}', schema)
    assert not result.valid and result.repaired and result.parse_error is None
    batch = validate_batch(['{"value":"１２",}'], schema, repair=True)
    assert batch.summary.schema_failures == 1 and batch.summary.repaired == 1

    def generate(prompt, context):
        if context.attempt == 0:
            return '{"value":"１２",}'
        assert context.previous_result.repaired and context.previous_result.parse_error is None
        assert "$.value" in prompt
        return '{"value":"123"}'

    assert guarded_generate(prompt="Return digits", schema=schema, generate=generate).valid


def test_runtime_is_lazy_and_does_not_spawn_workers_or_require_node():
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import threading, sys
import outputguard
assert '_quickjs' not in sys.modules
assert len(threading.enumerate()) == 1
assert outputguard.validate('"a"', {'pattern': '(?<name>a)'}).valid
assert len(threading.enumerate()) == 1
""",
        ],
        env={**os.environ, "PATH": ""},
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_thread_local_caches_evict_patterns_and_recover_after_syntax_errors():
    barrier = threading.Barrier(8)

    def work(index):
        barrier.wait(timeout=10)
        for number in range(180):
            assert search(f"^item{number}$", f"item{number}")
        with pytest.raises(SchemaError):
            search("[", "text")
        assert search(r"(?<word>a)\k<word>", "aa")
        assert len(_runtime().patterns) <= 128
        return id(_runtime().context), index

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(work, range(8)))
    assert sorted(index for _, index in results) == list(range(8))
    assert len({context for context, _ in results}) == 8
    # Native contexts stay on their worker threads; only Python IDs are returned.


def test_user_strings_are_data_and_native_python_regexes_are_unchanged():
    expression = ";globalThis.outputguardInjected=true;//"
    assert search(expression, expression)
    assert _runtime().context.eval("typeof outputguardInjected") == "undefined"
    assert Draft7Validator({"pattern": r"^\d+$"}).is_valid("１２")
    assert not validate(json.dumps("１２"), {"pattern": r"^\d+$"}).valid


@pytest.mark.skipif(not hasattr(os, "fork"), reason="fork is unavailable")
def test_forked_child_creates_its_own_runtime():
    assert search("a", "a")
    read_fd, write_fd = os.pipe()
    child = os.fork()
    if child == 0:
        try:
            os.close(read_fd)
            assert search("a", "a")
            os.write(write_fd, str(_runtime().pid).encode())
        finally:
            os._exit(0)
    os.close(write_fd)
    received = os.read(read_fd, 100)
    os.close(read_fd)
    _, status = os.waitpid(child, 0)
    assert status == 0 and received == str(child).encode()
