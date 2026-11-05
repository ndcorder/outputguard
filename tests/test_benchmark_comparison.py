import copy
import json
import subprocess
import sys

import pytest

from benchmarks import check_parity
from benchmarks.comparison import assert_json_equal, json_difference, same_json
from benchmarks.run import check_cases


@pytest.mark.parametrize(
    ("left", "right", "equal"),
    [
        (False, 0, False),
        (True, 1, False),
        ([False], [0], False),
        ({"value": False}, {"value": 0}, False),
        ({"value": [True]}, {"value": [1]}, False),
        ([], {}, False),
        (None, False, False),
        ("1", 1, False),
        ([0, 1], [1, 0], False),
        ({"missing": None}, {}, False),
        ({"__proto__": False}, {}, False),
        (1, 1.0, True),
        (0, -0.0, True),
        ({"value": [0, 1.0]}, {"value": [-0.0, 1]}, True),
        ({"a": 0, "b": False}, {"b": False, "a": 0.0}, True),
        (None, None, True),
        ([False, True, 0, 1], [False, True, 0.0, 1.0], True),
    ],
)
def test_json_equality_contract(left, right, equal):
    assert same_json(left, right) is equal
    assert same_json(right, left) is equal


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), (), {0: "x"}])
def test_non_json_values_cannot_pass_a_json_comparison(value):
    assert not same_json(value, value)


def test_first_difference_identifies_nested_escaped_and_prototype_keys():
    expected = {"a/b": [{"__proto__": False}]}
    actual = {"a/b": [{"__proto__": 0}]}
    assert json_difference(expected, actual) == (
        '$["a/b"][0]["__proto__"]: expected boolean, got number'
    )
    with pytest.raises(ValueError, match="comparison_probe"):
        assert_json_equal(actual, expected, "comparison_probe")


def _case():
    return {
        "name": "typed_value_probe",
        "text": '{"value":false}',
        "schema": {"properties": {"value": False}},
        "format": "json",
        "expected": {
            "valid": False,
            "data": {"value": False},
            "repaired": False,
            "repaired_text": "",
            "strategies": [],
            "parse_failure": False,
            "error_paths": ["$.value"],
            "error_values": [False],
        },
    }


@pytest.mark.parametrize(
    "path", [("valid",), ("data", "value"), ("repaired",), ("parse_failure",), ("error_values", 0)]
)
def test_benchmark_correctness_gate_rejects_boolean_number_mismatches(path):
    case = _case()
    check_cases([case])
    expected = case["expected"]
    for step in path[:-1]:
        expected = expected[step]
    expected[path[-1]] = 0
    with pytest.raises(ValueError, match="typed_value_probe.*expected number, got boolean"):
        check_cases([case])


@pytest.mark.parametrize("path", [("valid",), ("data", "value"), ("error_values", 0)])
def test_cross_runtime_gate_rejects_typed_mismatch_from_node(monkeypatch, tmp_path, path):
    case = _case()
    encoded = json.dumps([case])
    fixtures = tmp_path / "cases.json"
    fixtures.write_text(encoded)
    js_repo = tmp_path / "js"
    (js_repo / "benchmarks").mkdir(parents=True)
    (js_repo / "benchmarks/cases.json").write_text(encoded)
    actual = {"name": case["name"], **copy.deepcopy(case["expected"])}
    target = actual
    for step in path[:-1]:
        target = target[step]
    target[path[-1]] = 0

    def run_node(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, json.dumps([actual]), "")

    monkeypatch.setattr(check_parity, "CASES_PATH", fixtures)
    monkeypatch.setattr(check_parity.subprocess, "run", run_node)
    monkeypatch.setattr(sys, "argv", ["check_parity", "--js-repo", str(js_repo)])
    with pytest.raises(SystemExit, match="expected boolean, got number"):
        check_parity.main()
