"""Compare real CLI processes, and optionally time fresh-process wall latency."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path

from benchmarks.cli_cases import CASES_PATH, cli_cases, run_cli_case
from benchmarks.comparison import assert_json_equal
from benchmarks.run import positive_int
from benchmarks.timing import environment_snapshot, round_microseconds

PYTHON_ENTRY = 'from outputguard.cli import cli\ncli(prog_name="outputguard")'
BENCHMARK_NAMES = {
    "validate-short-json",
    "validate-crlf",
    "validate-repaired-short-flags",
    "batch-empty",
    "batch-repaired",
    "large-pipe-output",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--js-repo", type=Path, default=Path("../outputguard-js"))
    parser.add_argument("--node", default="node")
    parser.add_argument("--workers", type=positive_int, default=4)
    parser.add_argument("--benchmark-dir", type=Path)
    parser.add_argument("--samples", type=positive_int, default=3)
    args = parser.parse_args()
    js_repo = args.js_repo.resolve()
    if CASES_PATH.read_bytes() != (js_repo / "benchmarks/cli_cases.json").read_bytes():
        raise SystemExit("CLI fixture copies differ between checkouts")
    cases = cli_cases()
    commands = {
        "python": [sys.executable, "-c", PYTHON_ENTRY],
        "js": [args.node, str(js_repo / "dist/cli.js")],
    }
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        expected = list(executor.map(partial(run_cli_case, command=commands["python"]), cases))
        actual = list(executor.map(partial(run_cli_case, command=commands["js"]), cases))
    assert_json_equal(actual, expected, "CLI process parity")
    print(f"CLI parity verified for {len(cases)} real-process contracts")
    if args.benchmark_dir is None:
        return
    # Fresh processes are measured serially; parent CPU time excludes the work.
    node = json.loads(
        subprocess.check_output(
            [
                args.node,
                "--input-type=module",
                "--eval",
                "process.stdout.write(JSON.stringify({version:process.version,platform:process.platform+'-'+process.arch}))",
            ],
            text=True,
        )
    )
    identities = {
        "python": (
            f"Python {platform.python_version()} CLI",
            sys.platform + "-" + platform.machine(),
        ),
        "js": (f"Node.js {node['version']} CLI", node["platform"]),
    }
    selected = [case for case in cases if case["name"] in BENCHMARK_NAMES]
    args.benchmark_dir.mkdir(parents=True, exist_ok=True)
    for language, command in commands.items():
        start = environment_snapshot()
        measurements = []
        for case in selected:
            durations: list[float] = []
            for _ in range(args.samples):
                run_cli_case(case, command, durations)
            measurements.append(
                {
                    "name": "cli_" + case["name"],
                    "schema_mode": "fresh",
                    "median_us": round_microseconds(statistics.median(durations)),
                    "min_us": round_microseconds(min(durations)),
                }
            )
        runtime, host = identities[language]
        report = {
            "runtime": runtime,
            "platform": host,
            "iterations": 1,
            "samples": args.samples,
            "warmup_iterations": 0,
            "clock": "wall",
            "environment": {"start": start, "end": environment_snapshot()},
            "measurements": measurements,
        }
        path = args.benchmark_dir / f"cli-{language}.json"
        path.write_text(json.dumps(report, indent=2) + "\n")
        print(path)


if __name__ == "__main__":
    main()
