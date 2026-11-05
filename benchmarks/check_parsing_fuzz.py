"""Check generated parsing and repairs against known data in both ports."""

import argparse
import json
import subprocess
import warnings
from pathlib import Path

from benchmarks.comparison import assert_json_equal
from benchmarks.parsing_cases import generate_parsing_cases
from benchmarks.python_number_cases import generate_python_number_cases
from benchmarks.python_string_cases import generate_python_string_cases
from benchmarks.run import check_cases, positive_int
from benchmarks.toml_cases import generate_toml_cases
from benchmarks.yaml_cases import generate_yaml_cases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--js-repo", type=Path, default=Path("../outputguard-js"))
    parser.add_argument("--cases", type=positive_int, default=1200)
    parser.add_argument("--seed", type=int, default=2107)
    mode_flags = parser.add_mutually_exclusive_group()
    mode_flags.add_argument(
        "--python-strings", action="store_true", help="Generate Python string literals"
    )
    mode_flags.add_argument(
        "--python-numbers", action="store_true", help="Generate Python real-number literals"
    )
    mode_flags.add_argument(
        "--yaml", action="store_true", help="Generate shared YAML profile documents"
    )
    mode_flags.add_argument(
        "--toml", action="store_true", help="Generate shared TOML profile documents"
    )
    args = parser.parse_args()
    if args.toml:
        generate, mode = generate_toml_cases, "TOML profile"
    elif args.yaml:
        generate, mode = generate_yaml_cases, "YAML core"
    elif args.python_numbers:
        generate, mode = generate_python_number_cases, "Python number"
    elif args.python_strings:
        generate, mode = generate_python_string_cases, "Python string"
    else:
        generate, mode = generate_parsing_cases, "JSON parsing and repair"
    cases = generate(args.cases, args.seed)
    expected = []
    for case in cases:
        try:
            with warnings.catch_warnings():
                # Expected unknown/octal escapes can warn on newer CPython.
                warnings.simplefilter("ignore", SyntaxWarning)
                warnings.simplefilter("ignore", DeprecationWarning)
                expected.extend(check_cases([case]))
        except Exception as error:
            raise SystemExit(
                f"Python parsing runner failed for {json.dumps(case, indent=2)}\n{error}"
            ) from error
    completed = subprocess.run(
        [
            "node",
            "--input-type=module",
            "--eval",
            """
import { runCase, normalized } from './benchmarks/run.mjs';
import { assertJsonEqual } from './benchmarks/comparison.mjs';
process.stdin.setEncoding('utf8');
let input = '';
for await (const chunk of process.stdin) input += chunk;
const cases = JSON.parse(input);
const results = cases.map(c => {
  try {
    const result = normalized(runCase(c));
    assertJsonEqual(result, c.expected, c.name);
    return {name: c.name, ...result};
  } catch (error) {
    throw new Error(JSON.stringify(c, null, 2), {cause: error});
  }
});
process.stdout.write(JSON.stringify(results));
""",
        ],
        cwd=args.js_repo.resolve(),
        input=json.dumps(cases),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise SystemExit(f"JavaScript parsing runner failed:\n{completed.stderr}")
    assert_json_equal(json.loads(completed.stdout), expected, "Cross-port parsing results")
    print(f"{mode} results match for {len(cases)} generated cases (seed {args.seed})")


if __name__ == "__main__":
    main()
