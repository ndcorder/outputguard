import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("results", [False, True])
@pytest.mark.parametrize(
    "clock_flags,clock",
    [
        ([], "wall"),
        (["--clock", "wall"], "wall"),
        (["--clock", "cpu"], "cpu"),
        (["--clock=cpu"], "cpu"),
    ],
)
def test_named_benchmark_selection_is_checked_unique_and_in_fixture_order(
    results, clock_flags, clock
):
    command = [
        sys.executable,
        "-m",
        "benchmarks.run",
        "--iterations",
        "1",
        "--samples",
        "1",
        "--case",
        "literal_ref_examples_pattern_valid",
        "--case",
        "clean_json",
        "--case",
        "clean_json",
    ]
    command.extend(clock_flags)
    if results:
        command.append("--results")
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
    report = json.loads(completed.stdout)
    entries = report if results else report["measurements"]
    assert [entry["name"] for entry in entries] == [
        "clean_json",
        "literal_ref_examples_pattern_valid",
    ]
    if results:
        assert all(entry["valid"] is True for entry in entries)
    else:
        assert report["iterations"] == report["samples"] == 1
        assert all(entry["schema_mode"] == "reused" for entry in entries)
        assert report["clock"] == clock
        for snapshot in report["environment"].values():
            assert snapshot["logical_cpus"] is None or snapshot["logical_cpus"] >= 1
            assert snapshot["load_average"] is None or len(snapshot["load_average"]) == 3


@pytest.mark.parametrize(
    "selection", [["--case"], ["--case", "clean_json", "--case", "missing_case"]]
)
def test_invalid_benchmark_selection_fails_without_partial_results(selection):
    completed = subprocess.run(
        [sys.executable, "-m", "benchmarks.run", *selection],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    assert completed.stdout == ""
    assert ("missing_case" if "missing_case" in selection else "--case") in completed.stderr


@pytest.mark.parametrize(
    "flags",
    [
        ["--clock"],
        ["--clock", "monotonic"],
        ["--clock", "CPU"],
        ["--clock="],
        ["--cl", "cpu"],
        ["--results=cpu"],
        ["--iterations", str(2**53)],
        ["--samples", str(2**53)],
        ["--iterations", "0x10"],
        ["--iterations", "1e3"],
        ["--iterations", "1.0"],
        ["--iterations", "１２"],
        ["--iterations", "\ufeff1"],
    ],
)
def test_invalid_timing_options_fail_before_producing_output(flags):
    completed = subprocess.run(
        [sys.executable, "-m", "benchmarks.run", "--case", "clean_json", *flags],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 2
    assert completed.stdout == "" and completed.stderr


@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_benchmark_help_describes_clock_selection(flag):
    completed = subprocess.run(
        [sys.executable, "-m", "benchmarks.run", flag],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0 and "--clock" in completed.stdout
    assert "cpu" in completed.stdout and not completed.stderr


@pytest.mark.parametrize(
    "modes",
    [
        ["--python-strings", "--python-numbers"],
        ["--yaml", "--python-strings"],
        ["--yaml", "--python-numbers"],
    ],
)
def test_generated_parsing_modes_are_mutually_exclusive(modes):
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "benchmarks.check_parsing_fuzz",
            *modes,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 2 and completed.stdout == ""
    assert "not allowed with argument" in completed.stderr
