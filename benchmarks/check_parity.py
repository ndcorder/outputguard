"""Compare the shared corpus against a built outputguard-js checkout."""

import argparse
import json
import subprocess
import warnings
from pathlib import Path

from benchmarks.compare import compare_reports
from benchmarks.comparison import assert_json_equal, json_difference
from benchmarks.configuration_cases import (
    FIXTURES_PATH,
    check_configuration_cases,
    configuration_cases,
)
from benchmarks.diff_cases import CASES_PATH as DIFF_CASES_PATH
from benchmarks.diff_cases import check_diff_cases, diff_cases
from benchmarks.evaluation_failures import CASES_PATH as EVALUATION_CASES_PATH
from benchmarks.evaluation_failures import METHODS as EVALUATION_METHODS
from benchmarks.evaluation_failures import check_failure_cases, failure_cases
from benchmarks.generation_cases import CASES_PATH as GENERATION_CASES_PATH
from benchmarks.generation_cases import check_generation_cases, generation_cases
from benchmarks.input_cases import CASES_PATH as INPUT_CASES_PATH
from benchmarks.input_cases import check_input_cases, input_cases
from benchmarks.python_number_cases import number_fixture_cases
from benchmarks.python_string_cases import string_fixture_cases
from benchmarks.repair_cases import CASES_PATH as REPAIR_CASES_PATH
from benchmarks.repair_cases import check_repair_cases, repair_cases
from benchmarks.run import CASES_PATH, check_cases
from benchmarks.schema_mutations import (
    CASES_PATH as MUTATION_CASES_PATH,
)
from benchmarks.schema_mutations import METHODS as MUTATION_METHODS
from benchmarks.schema_mutations import check_mutation_cases, mutation_cases
from benchmarks.string_repairs import CASES_PATH as STRING_CASES_PATH
from benchmarks.string_repairs import METHODS as STRING_METHODS
from benchmarks.string_repairs import check_string_repair_cases, string_repair_cases
from benchmarks.toml_cases import toml_fixture_cases
from benchmarks.toml_engine import verify_toml_engine
from benchmarks.truncation_cases import CASES_PATH as TRUNCATION_CASES_PATH
from benchmarks.truncation_cases import METHODS as TRUNCATION_METHODS
from benchmarks.truncation_cases import check_truncation_cases, truncation_cases
from benchmarks.unicode_repairs import CASES_PATH as UNICODE_CASES_PATH
from benchmarks.unicode_repairs import METHODS as UNICODE_METHODS
from benchmarks.unicode_repairs import check_unicode_cases, unicode_cases
from benchmarks.yaml_cases import yaml_fixture_cases
from benchmarks.yaml_engine import verify_yaml_engine
from outputguard import validate

REPORT_CASES_PATH = Path(__file__).with_name("report_comparisons.json")
NUMERIC_CASES_PATH = Path(__file__).with_name("numeric_cases.json")
FORMAT_CASES_PATH = Path(__file__).with_name("schema_formats.json")
REGEX_CASES_PATH = Path(__file__).with_name("regex_cases.json")
PYTHON_STRINGS_PATH = Path(__file__).with_name("python_strings.json")
PYTHON_NUMBERS_PATH = Path(__file__).with_name("python_numbers.json")
YAML_CASES_PATH = Path(__file__).with_name("yaml_cases.json")
TOML_CASES_PATH = Path(__file__).with_name("toml_cases.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--js-repo", type=Path, default=Path("../outputguard-js"))
    args = parser.parse_args()
    js_repo = args.js_repo.resolve()
    if CASES_PATH.read_bytes() != (js_repo / "benchmarks/cases.json").read_bytes():
        raise SystemExit("Parity fixtures differ between checkouts")
    expected = check_cases(json.loads(CASES_PATH.read_text()))
    completed = subprocess.run(
        ["node", "benchmarks/run.mjs", "--results"],
        cwd=js_repo,
        check=False,
        text=True,
        capture_output=True,
    )
    if completed.returncode:
        raise SystemExit(f"JavaScript parity runner failed:\n{completed.stderr}")
    actual = json.loads(completed.stdout)
    difference = json_difference(expected, actual)
    if difference is not None:
        raise SystemExit(f"Python and JavaScript normalized results differ: {difference}")
    if (
        REPORT_CASES_PATH.read_bytes()
        != (js_repo / "benchmarks/report_comparisons.json").read_bytes()
    ):
        raise SystemExit("Report comparison fixtures differ between checkouts")
    report_cases = json.loads(REPORT_CASES_PATH.read_text())
    expected_reports = []
    for case in report_cases:
        report = compare_reports(case["before"], case["after"], case["threshold"])
        assert_json_equal(report, case["expected"], case["name"])
        expected_reports.append(report)
    completed = subprocess.run(
        [
            "node",
            "--input-type=module",
            "--eval",
            """
import { compareReports } from './benchmarks/compare.mjs';
process.stdin.setEncoding('utf8');
let input = '';
for await (const chunk of process.stdin) input += chunk;
const cases = JSON.parse(input);
const results = cases.map(c => compareReports(c.before, c.after, c.threshold));
process.stdout.write(JSON.stringify(results));
""",
        ],
        cwd=js_repo,
        input=json.dumps(report_cases),
        check=False,
        text=True,
        capture_output=True,
    )
    if completed.returncode:
        raise SystemExit(f"JavaScript report comparison failed:\n{completed.stderr}")
    difference = json_difference(expected_reports, json.loads(completed.stdout))
    if difference is not None:
        raise SystemExit(f"Python and JavaScript report comparisons differ: {difference}")
    if NUMERIC_CASES_PATH.read_bytes() != (js_repo / "benchmarks/numeric_cases.json").read_bytes():
        raise SystemExit("Numeric fixtures differ between checkouts")
    numeric_cases = json.loads(NUMERIC_CASES_PATH.read_text())
    expected_numeric = []
    for case in numeric_cases:
        valid = validate(case["text"], {"multipleOf": case["divisor"]}).valid
        assert_json_equal(valid, case["valid"], case["name"])
        expected_numeric.append(valid)
    completed = subprocess.run(
        [
            "node",
            "--input-type=module",
            "--eval",
            """
import { validate } from './dist/index.js';
process.stdin.setEncoding('utf8');
let input = '';
for await (const chunk of process.stdin) input += chunk;
const cases = JSON.parse(input);
const results = cases.map(c => validate(c.text, {multipleOf: c.divisor}).valid);
process.stdout.write(JSON.stringify(results));
""",
        ],
        cwd=js_repo,
        input=json.dumps(numeric_cases),
        check=False,
        text=True,
        capture_output=True,
    )
    if completed.returncode:
        raise SystemExit(f"JavaScript numeric validation failed:\n{completed.stderr}")
    difference = json_difference(expected_numeric, json.loads(completed.stdout))
    if difference is not None:
        raise SystemExit(f"Python and JavaScript numeric validity differs: {difference}")
    if FORMAT_CASES_PATH.read_bytes() != (js_repo / "benchmarks/schema_formats.json").read_bytes():
        raise SystemExit("Schema-format fixtures differ between checkouts")
    patterns = CASES_PATH.parent.parent / "outputguard/_schema_format_patterns.json"
    if patterns.read_bytes() != (js_repo / "src/schemaFormatPatterns.json").read_bytes():
        raise SystemExit("Schema-format patterns differ between checkouts")
    format_cases = json.loads(FORMAT_CASES_PATH.read_text())
    expected_formats = []
    for case in format_cases:
        valid = validate(json.dumps(case["value"]), {"format": case["format"]}).valid
        assert_json_equal(valid, case["valid"], case["name"])
        expected_formats.append(valid)
    completed = subprocess.run(
        [
            "node",
            "--input-type=module",
            "--eval",
            """
import { validate } from './dist/index.js';
process.stdin.setEncoding('utf8');
let input = '';
for await (const chunk of process.stdin) input += chunk;
const cases = JSON.parse(input);
const results = cases.map(c => validate(JSON.stringify(c.value), {format: c.format}).valid);
process.stdout.write(JSON.stringify(results));
""",
        ],
        cwd=js_repo,
        input=json.dumps(format_cases),
        check=False,
        text=True,
        capture_output=True,
    )
    if completed.returncode:
        raise SystemExit(f"JavaScript schema-format validation failed:\n{completed.stderr}")
    difference = json_difference(expected_formats, json.loads(completed.stdout))
    if difference is not None:
        raise SystemExit(f"Python and JavaScript schema-format validity differs: {difference}")
    if REGEX_CASES_PATH.read_bytes() != (js_repo / "benchmarks/regex_cases.json").read_bytes():
        raise SystemExit("Regex fixtures differ between checkouts")
    regex_cases = json.loads(REGEX_CASES_PATH.read_text())
    expected_regex = []
    for case in regex_cases:
        valid = validate(json.dumps(case["text"]), {"pattern": case["pattern"]}).valid
        assert_json_equal(valid, case["valid"], case["name"])
        expected_regex.append(valid)
    completed = subprocess.run(
        [
            "node",
            "--input-type=module",
            "--eval",
            """
import { validate } from './dist/index.js';
process.stdin.setEncoding('utf8');
let input = '';
for await (const chunk of process.stdin) input += chunk;
const cases = JSON.parse(input);
const results = cases.map(c => validate(JSON.stringify(c.text), {pattern: c.pattern}).valid);
process.stdout.write(JSON.stringify(results));
""",
        ],
        cwd=js_repo,
        input=json.dumps(regex_cases),
        check=False,
        text=True,
        capture_output=True,
    )
    if completed.returncode:
        raise SystemExit(f"JavaScript regex validation failed:\n{completed.stderr}")
    difference = json_difference(expected_regex, json.loads(completed.stdout))
    if difference is not None:
        raise SystemExit(f"Python and JavaScript regex validity differs: {difference}")
    if (
        PYTHON_STRINGS_PATH.read_bytes()
        != (js_repo / "benchmarks/python_strings.json").read_bytes()
    ):
        raise SystemExit("Python-string fixtures differ between checkouts")
    python_string_cases = string_fixture_cases()
    if (
        PYTHON_NUMBERS_PATH.read_bytes()
        != (js_repo / "benchmarks/python_numbers.json").read_bytes()
    ):
        raise SystemExit("Python-number fixtures differ between checkouts")
    python_number_cases = number_fixture_cases()
    if YAML_CASES_PATH.read_bytes() != (js_repo / "benchmarks/yaml_cases.json").read_bytes():
        raise SystemExit("YAML core fixtures differ between checkouts")
    verify_yaml_engine(js_repo, Path(__file__).parents[1] / "outputguard")
    yaml_cases = yaml_fixture_cases()
    if TOML_CASES_PATH.read_bytes() != (js_repo / "benchmarks/toml_cases.json").read_bytes():
        raise SystemExit("TOML profile fixtures differ between checkouts")
    verify_toml_engine(js_repo, Path(__file__).parents[1] / "outputguard")
    toml_cases = toml_fixture_cases()
    parser_cases = python_string_cases + python_number_cases + yaml_cases + toml_cases
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        warnings.simplefilter("ignore", DeprecationWarning)
        expected_parsers = check_cases(parser_cases)
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
  const result = normalized(runCase(c));
  assertJsonEqual(result, c.expected, c.name);
  return {name: c.name, ...result};
});
process.stdout.write(JSON.stringify(results));
""",
        ],
        cwd=js_repo,
        input=json.dumps(parser_cases),
        check=False,
        text=True,
        capture_output=True,
    )
    if completed.returncode:
        raise SystemExit(f"JavaScript format parsing failed:\n{completed.stderr}")
    difference = json_difference(expected_parsers, json.loads(completed.stdout))
    if difference is not None:
        raise SystemExit(f"Python and JavaScript parser results differ: {difference}")
    if FIXTURES_PATH.read_bytes() != (js_repo / "benchmarks/configuration_cases.json").read_bytes():
        raise SystemExit("Configuration fixtures differ between checkouts")
    config_cases = configuration_cases()
    expected_configuration = check_configuration_cases(config_cases, asynchronous=False)
    assert_json_equal(
        check_configuration_cases(config_cases, asynchronous=True),
        expected_configuration,
        "Python sync and async configuration contracts",
    )
    completed = subprocess.run(
        [
            "node",
            "--input-type=module",
            "--eval",
            """
import { checkConfigurationCases } from './benchmarks/configuration.mjs';
process.stdin.setEncoding('utf8');
let input = '';
for await (const chunk of process.stdin) input += chunk;
process.stdout.write(JSON.stringify(await checkConfigurationCases(JSON.parse(input))));
""",
        ],
        cwd=js_repo,
        input=json.dumps(config_cases),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise SystemExit(f"JavaScript configuration checks failed:\n{completed.stderr}")
    assert_json_equal(
        json.loads(completed.stdout), expected_configuration, "Configuration contracts"
    )
    if REPAIR_CASES_PATH.read_bytes() != (js_repo / "benchmarks/repair_cases.json").read_bytes():
        raise SystemExit("Repair fixtures differ between checkouts")
    repair_contracts = repair_cases()
    expected_repairs = {
        f"{entrypoint}:{str(report).lower()}": check_repair_cases(
            repair_contracts, report=report, entrypoint=entrypoint
        )
        for entrypoint in ("guard", "module")
        for report in (False, True)
    }
    completed = subprocess.run(
        [
            "node",
            "--input-type=module",
            "--eval",
            """
import { checkRepairCases } from './benchmarks/repairCases.mjs';
let input = '';
process.stdin.setEncoding('utf8');
for await (const chunk of process.stdin) input += chunk;
const cases = JSON.parse(input);
const results = {};
for (const entrypoint of ["guard", "module"]) for (const report of [false, true]) {
  results[`${entrypoint}:${report}`] = checkRepairCases(cases, { report, entrypoint });
}
process.stdout.write(JSON.stringify(results));
""",
        ],
        cwd=js_repo,
        input=json.dumps(repair_contracts),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise SystemExit(f"JavaScript repair contracts failed:\n{completed.stderr}")
    assert_json_equal(json.loads(completed.stdout), expected_repairs, "Repair contracts")
    if DIFF_CASES_PATH.read_bytes() != (js_repo / "benchmarks/diff_cases.json").read_bytes():
        raise SystemExit("Diff fixtures differ between checkouts")
    diff_contracts = diff_cases()
    expected_diffs = check_diff_cases(diff_contracts)
    completed = subprocess.run(
        [
            "node",
            "--input-type=module",
            "--eval",
            """
import { checkDiffCases } from './benchmarks/diffCases.mjs';
process.stdin.setEncoding('utf8');
let input = '';
for await (const chunk of process.stdin) input += chunk;
process.stdout.write(JSON.stringify(checkDiffCases(JSON.parse(input))));
""",
        ],
        cwd=js_repo,
        input=json.dumps(diff_contracts),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise SystemExit(f"JavaScript diff contracts failed:\n{completed.stderr}")
    assert_json_equal(json.loads(completed.stdout), expected_diffs, "Diff contracts")
    if INPUT_CASES_PATH.read_bytes() != (js_repo / "benchmarks/input_cases.json").read_bytes():
        raise SystemExit("Input fixtures differ between checkouts")
    input_contracts = input_cases()
    expected_inputs = check_input_cases(input_contracts, asynchronous=False)
    assert_json_equal(
        check_input_cases(input_contracts, asynchronous=True),
        expected_inputs,
        "Python sync and async input contracts",
    )
    completed = subprocess.run(
        [
            "node",
            "--input-type=module",
            "--eval",
            """
import { checkInputCases, inputCases } from './benchmarks/inputCases.mjs';
import { assertJsonEqual } from './benchmarks/comparison.mjs';
process.stdin.setEncoding('utf8');
let input = '';
for await (const chunk of process.stdin) input += chunk;
const cases = JSON.parse(input);
assertJsonEqual(inputCases(), cases, 'Input fixture expansion');
process.stdout.write(JSON.stringify(await checkInputCases(cases)));
""",
        ],
        cwd=js_repo,
        input=json.dumps(input_contracts),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise SystemExit(f"JavaScript input contracts failed:\n{completed.stderr}")
    assert_json_equal(json.loads(completed.stdout), expected_inputs, "Input contracts")
    if (
        MUTATION_CASES_PATH.read_bytes()
        != (js_repo / "benchmarks/schema_mutations.json").read_bytes()
    ):
        raise SystemExit("Schema mutation fixtures differ between checkouts")
    mutations = mutation_cases()
    expected_mutations = [check_mutation_cases(mutations, method) for method in MUTATION_METHODS]
    completed = subprocess.run(
        [
            "node",
            "--input-type=module",
            "--eval",
            """
import { checkMutationCases, mutationMethods } from './benchmarks/schemaMutations.mjs';
process.stdin.setEncoding('utf8');
let input = '';
for await (const chunk of process.stdin) input += chunk;
const cases = JSON.parse(input);
const results = mutationMethods.map(method => checkMutationCases(cases, method));
process.stdout.write(JSON.stringify(results));
""",
        ],
        cwd=js_repo,
        input=json.dumps(mutations),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise SystemExit(f"JavaScript schema mutation workflows failed:\n{completed.stderr}")
    assert_json_equal(json.loads(completed.stdout), expected_mutations, "Schema mutations")
    if (
        EVALUATION_CASES_PATH.read_bytes()
        != (js_repo / "benchmarks/evaluation_failures.json").read_bytes()
    ):
        raise SystemExit("Evaluation failure fixtures differ between checkouts")
    failures = failure_cases()
    expected_failures = [check_failure_cases(failures, method) for method in EVALUATION_METHODS]
    for method in ("generate", "generate_no_repair"):
        assert_json_equal(
            check_failure_cases(failures, method, True),
            expected_failures[EVALUATION_METHODS.index(method)],
            "Async evaluation failures",
        )
    completed = subprocess.run(
        [
            "node",
            "--input-type=module",
            "--eval",
            """
import { checkFailureCases, failureMethods } from './benchmarks/evaluationFailures.mjs';
process.stdin.setEncoding('utf8');
let input = '';
for await (const chunk of process.stdin) input += chunk;
const cases = JSON.parse(input), results = [];
for (const method of failureMethods) results.push(await checkFailureCases(cases, method));
process.stdout.write(JSON.stringify(results));
""",
        ],
        cwd=js_repo,
        input=json.dumps(failures),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise SystemExit(f"JavaScript evaluation failure contracts failed:\n{completed.stderr}")
    assert_json_equal(json.loads(completed.stdout), expected_failures, "Evaluation failures")
    if (
        GENERATION_CASES_PATH.read_bytes()
        != (js_repo / "benchmarks/generation_cases.json").read_bytes()
    ):
        raise SystemExit("Generation fixtures differ between checkouts")
    generations = generation_cases()
    expected_generations = [
        check_generation_cases(generations, throwing=throwing, asynchronous=asynchronous)
        for throwing in (False, True)
        for asynchronous in (False, True)
    ]
    completed = subprocess.run(
        [
            "node",
            "--input-type=module",
            "--eval",
            """
import { checkGenerationCases } from './benchmarks/generationCases.mjs';
process.stdin.setEncoding('utf8');
let input = '';
for await (const chunk of process.stdin) input += chunk;
const cases = JSON.parse(input), results = [];
for (const throwing of [false, true]) for (const asynchronous of [false, true]) {
  results.push(await checkGenerationCases(cases, { throwing, asynchronous }));
}
process.stdout.write(JSON.stringify(results));
""",
        ],
        cwd=js_repo,
        input=json.dumps(generations),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise SystemExit(f"JavaScript generation contracts failed:\n{completed.stderr}")
    assert_json_equal(json.loads(completed.stdout), expected_generations, "Generation contracts")
    if (
        UNICODE_CASES_PATH.read_bytes()
        != (js_repo / "benchmarks/unicode_repairs.json").read_bytes()
    ):
        raise SystemExit("Unicode repair fixtures differ between checkouts")
    unicode_contracts = unicode_cases()
    expected_unicode = [
        check_unicode_cases(unicode_contracts, method) for method in UNICODE_METHODS
    ]
    completed = subprocess.run(
        [
            "node",
            "--input-type=module",
            "--eval",
            """
import { checkUnicodeCases, unicodeMethods } from './benchmarks/unicodeRepairs.mjs';
process.stdin.setEncoding('utf8');
let input = '';
for await (const chunk of process.stdin) input += chunk;
const cases = JSON.parse(input);
const results = unicodeMethods.map(method => checkUnicodeCases(cases, method));
process.stdout.write(JSON.stringify(results));
""",
        ],
        cwd=js_repo,
        input=json.dumps(unicode_contracts),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise SystemExit(f"JavaScript Unicode repair contracts failed:\n{completed.stderr}")
    assert_json_equal(json.loads(completed.stdout), expected_unicode, "Unicode repairs")
    if (
        TRUNCATION_CASES_PATH.read_bytes()
        != (js_repo / "benchmarks/truncation_cases.json").read_bytes()
    ):
        raise SystemExit("Truncation fixtures differ between checkouts")
    truncations = truncation_cases()
    expected_truncations = [
        check_truncation_cases(truncations, method) for method in TRUNCATION_METHODS
    ]
    completed = subprocess.run(
        [
            "node",
            "--input-type=module",
            "--eval",
            """
import { checkTruncationCases, truncationMethods } from './benchmarks/truncationCases.mjs';
process.stdin.setEncoding('utf8');
let input = '';
for await (const chunk of process.stdin) input += chunk;
const cases = JSON.parse(input);
const results = truncationMethods.map(method => checkTruncationCases(cases, method));
process.stdout.write(JSON.stringify(results));
""",
        ],
        cwd=js_repo,
        input=json.dumps(truncations),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise SystemExit(f"JavaScript truncation contracts failed:\n{completed.stderr}")
    assert_json_equal(json.loads(completed.stdout), expected_truncations, "Truncation repairs")
    if STRING_CASES_PATH.read_bytes() != (js_repo / "benchmarks/string_repairs.json").read_bytes():
        raise SystemExit("String repair fixtures differ between checkouts")
    string_cases = string_repair_cases()
    expected_strings = [
        check_string_repair_cases(string_cases, method) for method in STRING_METHODS
    ]
    completed = subprocess.run(
        [
            "node",
            "--input-type=module",
            "--eval",
            """
import { checkStringRepairCases, stringRepairMethods } from './benchmarks/stringRepairs.mjs';
process.stdin.setEncoding('utf8');
let input = '';
for await (const chunk of process.stdin) input += chunk;
const cases = JSON.parse(input);
const results = stringRepairMethods.map(method => checkStringRepairCases(cases, method));
process.stdout.write(JSON.stringify(results));
""",
        ],
        cwd=js_repo,
        input=json.dumps(string_cases),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise SystemExit(f"JavaScript string repair contracts failed:\n{completed.stderr}")
    assert_json_equal(json.loads(completed.stdout), expected_strings, "String repairs")
    print(
        f"Parity verified for {len(expected)} shared cases, "
        f"{len(report_cases)} report comparisons, {len(numeric_cases)} numeric cases, "
        f"{len(format_cases)} schema-format cases, {len(regex_cases)} regex cases, "
        f"{len(python_string_cases)} Python-string cases, "
        f"{len(python_number_cases)} Python-number cases, {len(yaml_cases)} YAML core cases, "
        f"{len(toml_cases)} TOML profile cases, {len(config_cases)} configuration cases, "
        f"{len(repair_contracts) * len(expected_repairs)} repair contracts, "
        f"{len(diff_contracts)} diff contracts, "
        f"{len(input_contracts)} input contracts, "
        f"{len(mutations) * len(MUTATION_METHODS)} schema mutation workflows, "
        f"{len(failures) * len(EVALUATION_METHODS)} evaluation failure contracts, "
        f"{len(generations) * len(expected_generations)} generation outcome contracts, "
        f"{sum(len(cases) for cases in expected_unicode)} Unicode repair contracts, "
        f"{sum(len(cases) for cases in expected_truncations)} truncation repair contracts, and "
        f"{sum(len(cases) for cases in expected_strings)} string repair contracts"
    )


if __name__ == "__main__":
    main()
