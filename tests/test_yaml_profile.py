import hashlib
import json
import math
import multiprocessing
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import yaml

from benchmarks.comparison import assert_json_equal
from outputguard import OutputGuard, guarded_generate, validate, validate_and_repair, validate_batch
from outputguard.exceptions import ParseError, SchemaValidationError
from outputguard.formats import FormatParseError, parse_document
from outputguard.yaml_profile import _runtime

ROOT = Path(__file__).parents[1]
CASES = json.loads((ROOT / "benchmarks/yaml_cases.json").read_text())
LOCATIONS = [
    pytest.param(case, location, id=f"{case['name']}-{location}")
    for case in CASES
    for location in (["root"] if case.get("root_only") else ["root", "property", "list"])
]


def document(text, location):
    if location == "root":
        return text
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return ("holder:" if location == "property" else "-") + "\n  " + text.replace("\n", "\n  ")


def assert_value(value, case):
    if case.get("value_kind") == "nan":
        assert type(value) is float and math.isnan(value)
    elif "value_kind" in case:
        assert value == (-math.inf if case["value_kind"] == "negative_infinity" else math.inf)
    else:
        assert_json_equal(value, case["value"], case["name"])
    if "number_type" in case:
        assert type(value) is (int if case["number_type"] == "integer" else float)
        if value == 0:
            assert math.copysign(1, value) == math.copysign(1, case["value"])


@pytest.mark.parametrize(("case", "location"), LOCATIONS)
def test_yaml_core_data_and_parse_failure_categories(case, location):
    text = document(case["text"], location)
    for schema in (True, False):
        result = validate(text, schema, format="yaml")
        assert (
            result.original_text == text and not result.repaired and not result.strategies_applied
        )
        if not case["valid"]:
            assert not result.valid and result.data is None and result.parse_error
            assert [(error.path, error.schema_path) for error in result.errors] == [("$", "")]
        else:
            assert result.valid is schema and result.parse_error is None
            value = (
                result.data
                if location == "root"
                else result.data["holder"]
                if location == "property"
                else result.data[0]
            )
            assert_value(value, case)
            assert [error.path for error in result.errors] == ([] if schema else ["$"])


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_yaml_parser_contract_and_repair_short_circuit(case):
    if not case["valid"]:
        with pytest.raises(FormatParseError):
            parse_document(case["text"], "yaml")
        return
    assert_value(parse_document(case["text"], "yaml"), case)
    result = validate_and_repair(case["text"], True, format="yaml")
    assert result.valid and not result.repaired and result.parse_error is None
    assert result.repaired_text == "" and not result.strategies_applied
    assert_value(result.data, case)


@pytest.mark.parametrize("format", ["yaml", "yml", "auto", "forced-json-off"])
def test_yaml_keys_scalars_and_aliases_through_format_selection(format):
    text = "__proto__: &data {yes: on, number: 0123}\ncopy: *data"
    result = validate(text, {"properties": {"__proto__": {"type": "object"}}}, format=format)
    assert result.valid and result.parse_error is None
    assert result.format == format
    assert result.data == {
        "__proto__": {"yes": "on", "number": 123},
        "copy": {"yes": "on", "number": 123},
    }
    assert result.data["__proto__"] is result.data["copy"]
    result.data["copy"]["number"] = 42
    assert parse_document(text, format)["copy"]["number"] == 123


def test_aliases_preserve_container_identity_and_schema_diagnostics():
    result = validate("[&item {age: 42}, *item]", {"uniqueItems": True}, format="yaml")
    assert not result.valid and result.parse_error is None
    assert result.data[0] is result.data[1]
    assert [(error.path, error.value) for error in result.errors] == [("$", result.data)]


@pytest.mark.parametrize(("text", "kind"), [("yes", "type"), ("a: 1\na: 2", "parse")])
def test_yaml_guard_exception_categories(text, kind):
    guard = OutputGuard(format="yaml", strategies=[])
    with pytest.raises(ParseError if kind == "parse" else SchemaValidationError):
        guard.parse(text, {"type": "boolean"})


def test_batch_and_generation_keep_yaml_parse_and_schema_failures_separate():
    guard = OutputGuard(format="yaml", strategies=[])
    batch = validate_batch(["true", "yes", "a: 1\na: 2"], {"type": "boolean"}, guard=guard)
    assert (batch.summary.valid, batch.summary.parse_failures, batch.summary.schema_failures) == (
        1,
        1,
        1,
    )

    def generate(prompt, context):
        if context.attempt == 0:
            return "a: 1\na: 2"
        if context.attempt == 1:
            assert context.previous_result.parse_error
            return "yes"
        assert context.previous_result.parse_error is None
        assert context.previous_result.data == "yes"
        return "true"

    result = guarded_generate(
        generate=generate,
        prompt="Return YAML",
        schema={"type": "boolean"},
        format="yaml",
        guard=guard,
    )
    assert result.valid and result.data is True and len(result.attempts) == 3


@pytest.mark.parametrize("value", ["x" * 1000, "😀" * 500])
@pytest.mark.parametrize(("aliases", "valid"), [(110, True), (111, False)])
def test_exact_alias_amplification_boundary_uses_decoded_utf16_weight(value, aliases, valid):
    text = "[&a " + json.dumps(value, ensure_ascii=True) + ", *a" * aliases + "]"
    result = validate(text, True, format="yaml")
    assert result.valid is valid
    if valid:
        assert result.data == [value] * (aliases + 1)
    else:
        assert "alias expansion" in result.parse_error


def test_large_harmless_alias_lists_and_nested_amplification():
    text = "[&a x" + ", *a" * 3000 + "]"
    assert parse_document(text, "yaml") == ["x"] * 3001
    text = "a: &a [x, x, x, x, x]\n"
    for name, previous in zip("bcdefgh", "abcdefg", strict=True):
        text += name + ": &" + name + " [" + ", ".join(["*" + previous] * 5) + "]\n"
    result = validate(text, True, format="yaml")
    assert not result.valid and "alias expansion" in result.parse_error


def test_native_pyyaml_defaults_remain_unchanged_and_integer_precision_is_native():
    assert yaml.safe_load("yes") is True and yaml.safe_load("0123") == 83
    assert parse_document("yes", "yaml") == "yes"
    assert parse_document("0x20000000000001", "yaml") == 9007199254740993
    assert yaml.safe_load("yes") is True and yaml.safe_load("0123") == 83


def test_source_is_data_and_engine_artifact_matches_its_manifest():
    payload = '"; globalThis.__yaml_injected = true; //'
    assert parse_document(json.dumps(payload), "yaml") == payload
    assert _runtime().context.eval("typeof globalThis.__yaml_injected") == "undefined"
    metadata = json.loads((ROOT / "outputguard/_yaml_engine.json").read_text())
    assert (
        hashlib.sha256((ROOT / "outputguard/_yaml_engine.js").read_bytes()).hexdigest()
        == metadata["bundle_sha256"]
    )


def test_yaml_runtime_needs_no_node_or_background_worker():
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import threading; before=threading.active_count(); from outputguard import validate; r=validate('yes', {'const':'yes'}, format='yaml'); assert r.valid; assert threading.active_count()==before",
        ],
        cwd=ROOT,
        env={**os.environ, "PATH": ""},
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_yaml_contexts_are_isolated_by_thread():
    barrier = threading.Barrier(8)

    def worker(index):
        data = parse_document(f"value: &a [{index}, yes]\ncopy: *a", "yaml")
        runtime = _runtime()
        barrier.wait(timeout=10)
        assert data["value"] is data["copy"]
        return id(runtime.context), data["copy"]

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(worker, range(8)))
    assert len({context for context, data in results}) == 8
    assert [data for context, data in results] == [[index, "yes"] for index in range(8)]


def _forked_yaml(connection):
    try:
        connection.send((_runtime().pid, parse_document("yes", "yaml")))
    finally:
        connection.close()


@pytest.mark.skipif("fork" not in multiprocessing.get_all_start_methods(), reason="requires fork")
def test_yaml_runtime_is_reset_after_a_fork():
    assert _runtime().pid == os.getpid()
    context = multiprocessing.get_context("fork")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=_forked_yaml, args=(child,))
    process.start()
    child.close()
    try:
        assert parent.poll(10)
        pid, data = parent.recv()
        assert pid == process.pid and pid != os.getpid() and data == "yes"
    finally:
        parent.close()
        process.join(10)
        if process.is_alive():
            process.kill()
            process.join()
    assert process.exitcode == 0
