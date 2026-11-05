import copy
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from benchmarks import check_parity
from benchmarks.compare import compare_reports
from benchmarks.comparison import assert_json_equal

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "benchmarks/report_comparisons.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_report_comparisons_match_explicit_expectations_without_mutating_inputs(case):
    before = copy.deepcopy(case)
    assert_json_equal(
        compare_reports(case["before"], case["after"], case["threshold"]),
        case["expected"],
        case["name"],
    )
    assert case == before


INVALID_FIELDS = [
    ("runtime", 1),
    ("runtime", ""),
    ("platform", None),
    ("iterations", 0),
    ("iterations", True),
    ("iterations", 1.5),
    ("iterations", 2**53),
    ("samples", "5"),
    ("samples", 0),
    ("warmup_iterations", -1),
    ("clock", None),
    ("clock", "monotonic"),
    ("clock", True),
    ("clock", {}),
    ("clock", []),
    ("measurements", None),
    ("measurements.0", None),
    ("measurements.0.name", ""),
    ("measurements.0.name", 1),
    ("measurements.0.schema_mode", "cached"),
    ("measurements.0.schema_mode", {}),
    ("measurements.0.median_us", False),
    ("measurements.0.median_us", -1),
    ("measurements.0.median_us", "10"),
    ("measurements.0.median_us", float("nan")),
    ("measurements.0.median_us", float("inf")),
    ("measurements.0.min_us", 1000),
    ("measurements.0.min_us", True),
]


@pytest.mark.parametrize(("path", "value"), INVALID_FIELDS)
@pytest.mark.parametrize("side", ["before", "after"])
def test_malformed_reports_are_rejected_before_comparison(side, path, value):
    case = copy.deepcopy(CASES[0])
    target = case[side]
    steps = path.split(".")
    for step in steps[:-1]:
        target = target[int(step) if isinstance(target, list) else step]
    target[int(steps[-1]) if isinstance(target, list) else steps[-1]] = value
    with pytest.raises(ValueError, match=side):
        compare_reports(case["before"], case["after"])


@pytest.mark.parametrize("value", [None, [], True])
def test_report_root_must_be_an_object(value):
    with pytest.raises(ValueError, match="before must be an object"):
        compare_reports(value, CASES[0]["after"])


@pytest.mark.parametrize("threshold", [True, -1, "5", float("nan"), float("inf")])
def test_invalid_thresholds_are_rejected(threshold):
    with pytest.raises(ValueError, match="threshold"):
        compare_reports(CASES[0]["before"], CASES[0]["after"], threshold)


def test_duplicate_case_names_are_rejected_even_when_schema_modes_differ():
    before = copy.deepcopy(CASES[0]["before"])
    before["measurements"].append({**before["measurements"][0], "schema_mode": "fresh"})
    with pytest.raises(ValueError, match="duplicate measurement: reused"):
        compare_reports(before, CASES[0]["after"])


@pytest.mark.parametrize(
    "path,value",
    [
        ("environment", []),
        ("environment", True),
        ("environment.start", []),
        ("environment.start.logical_cpus", 0),
        ("environment.start.logical_cpus", True),
        ("environment.start.logical_cpus", 1.5),
        ("environment.start.logical_cpus", 2**53),
        ("environment.start.load_average", []),
        ("environment.start.load_average", [1, 2]),
        ("environment.start.load_average", [1, 2, 3, 4]),
        ("environment.start.load_average", [True, 0, 0]),
        ("environment.start.load_average", [1, -1, 0]),
        ("environment.start.load_average", [1, float("nan"), 0]),
        ("environment.start.load_average", [1, float("inf"), 0]),
    ],
)
@pytest.mark.parametrize("side", ["before", "after"])
def test_malformed_host_observations_are_rejected(side, path, value):
    case = copy.deepcopy(CASES[0])
    case[side]["environment"] = {"start": {"logical_cpus": 8, "load_average": [1, 2, 3]}}
    target = case[side]
    steps = path.split(".")
    for key in steps[:-1]:
        target = target[key]
    target[steps[-1]] = value
    with pytest.raises(ValueError, match=side + ".environment"):
        compare_reports(case["before"], case["after"])


def test_comparison_observations_do_not_alias_caller_owned_reports():
    before, after = copy.deepcopy(CASES[0]["before"]), copy.deepcopy(CASES[0]["after"])
    before["environment"] = {"start": {"logical_cpus": 8, "load_average": [1, 2, 3]}}
    original = copy.deepcopy(before)
    result = compare_reports(before, after)
    result["environment"]["before"]["start"]["load_average"][0] = 99
    assert before == original


def test_nonrepresentable_ratios_fail_instead_of_emitting_infinite_json():
    before, after = copy.deepcopy(CASES[0]["before"]), copy.deepcopy(CASES[0]["before"])
    before["measurements"][0].update(median_us=1e-300, min_us=0)
    after["measurements"][0].update(median_us=1e300, min_us=0)
    with pytest.raises(ValueError, match="overflows for measurement: reused"):
        compare_reports(before, after)


def test_large_representable_changes_remain_valid_json():
    before, after = copy.deepcopy(CASES[0]["before"]), copy.deepcopy(CASES[0]["before"])
    before["measurements"][0].update(median_us=1, min_us=0)
    after["measurements"][0].update(median_us=1e301, min_us=0)
    result = compare_reports(before, after)
    assert result["measurements"][0]["status"] == "regressed"
    assert math.isfinite(result["measurements"][0]["ratio"])
    assert math.isfinite(result["measurements"][0]["change_percent"])
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize(
    ("flags", "status"),
    [
        ([], 0),
        (["--fail-on-regression"], 1),
        (["--threshold", "50", "--fail-on-regression"], 0),
        (["--threshold=50", "--fail-on-regression"], 0),
        (["--threshold", "50", "--fail-on-incomparable"], 1),
    ],
)
def test_comparison_cli_keeps_json_output_when_ci_gate_fails(tmp_path, flags, status):
    paths = [tmp_path / "before report.json", tmp_path / "after report.json"]
    for path, report in zip(paths, [CASES[0]["before"], CASES[0]["after"]], strict=True):
        path.write_text(json.dumps(report))
    completed = subprocess.run(
        [sys.executable, "-m", "benchmarks.compare", *map(str, paths), *flags],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == status, completed.stderr
    report = json.loads(completed.stdout)
    assert report["summary"]["count"] == 5
    assert report["added"] == ["added"]
    assert report["summary"]["regressed"] == (
        0 if "--threshold" in flags or "--threshold=50" in flags else 1
    )


@pytest.mark.parametrize(
    "flags",
    [
        ["--threshold"],
        ["--threshold", "0x10"],
        ["--threshold", ""],
        ["--threshold", "-1"],
        ["--threshold", "NaN"],
        ["--threshold", "Infinity"],
        ["--threshold", "5\n"],
        ["--thres", "5"],
        ["--fail"],
    ],
)
def test_invalid_cli_arguments_produce_no_partial_report(flags):
    completed = subprocess.run(
        [sys.executable, "-m", "benchmarks.compare", "missing-before", "missing-after", *flags],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert completed.stdout == ""
    assert completed.stderr


def test_cli_rejects_non_json_constants_even_in_unused_fields(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text('{"unused":NaN}')
    completed = subprocess.run(
        [sys.executable, "-m", "benchmarks.compare", str(path), str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert completed.stdout == ""


@pytest.mark.parametrize(
    "flags,status",
    [
        ([], 0),
        (["--fail-on-regression"], 0),
        (["--fail-on-incomparable"], 1),
        (["--fail-on-regression", "--fail-on-incomparable"], 1),
    ],
)
def test_clock_mismatch_is_excluded_from_ratios_and_has_an_opt_in_gate(tmp_path, flags, status):
    case = next(case for case in CASES if case["name"] == "wall_and_cpu_are_incomparable")
    paths = [tmp_path / "before.json", tmp_path / "after.json"]
    for path, side in zip(paths, ["before", "after"], strict=True):
        path.write_text(json.dumps(case[side]))
    completed = subprocess.run(
        [sys.executable, "-m", "benchmarks.compare", *map(str, paths), *flags],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == status, completed.stderr
    result = json.loads(completed.stdout)
    assert result["summary"]["compared"] == result["summary"]["regressed"] == 0
    assert result["measurements"][0]["ratio"] is None
    assert result["measurements"][0]["status"] == "incomparable"


@pytest.mark.parametrize("mismatch", ["number", "type"])
def test_cross_runtime_gate_checks_report_comparison_results(monkeypatch, tmp_path, mismatch):
    js_repo = tmp_path / "js"
    (js_repo / "benchmarks").mkdir(parents=True)
    cases_path = tmp_path / "cases.json"
    cases_path.write_text("[]")
    reports_path = tmp_path / "reports.json"
    reports_path.write_text(json.dumps(CASES))
    (js_repo / "benchmarks/cases.json").write_text("[]")
    (js_repo / "benchmarks/report_comparisons.json").write_text(json.dumps(CASES))
    actual = [copy.deepcopy(case["expected"]) for case in CASES]
    actual[0]["summary"]["regressed"] = False if mismatch == "type" else 0

    def run_node(command, **kwargs):
        output = [] if "--results" in command else actual
        return subprocess.CompletedProcess(command, 0, json.dumps(output), "")

    monkeypatch.setattr(check_parity, "CASES_PATH", cases_path)
    monkeypatch.setattr(check_parity, "REPORT_CASES_PATH", reports_path)
    monkeypatch.setattr(check_parity.subprocess, "run", run_node)
    monkeypatch.setattr(sys, "argv", ["check_parity", "--js-repo", str(js_repo)])
    with pytest.raises(SystemExit, match="report comparisons differ.*regressed"):
        check_parity.main()
