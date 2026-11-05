"""Compare checked benchmark timing reports, grouped by schema lifetime."""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from pathlib import Path

_CONDITIONS = ("runtime", "platform", "iterations", "samples", "warmup_iterations", "clock")
_MODES = ("reused", "fresh", "none")
_STATUSES = ("regressed", "improved", "unchanged", "unmeasurable", "incomparable")
_DECIMAL = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")


def _number(value, label, *, minimum=0):
    try:
        valid = (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and value >= minimum
        )
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f"{label} must be a finite number >= {minimum}")
    return float(value)


def _report(report, label):
    if not isinstance(report, dict):
        raise ValueError(f"{label} must be an object")
    for key in _CONDITIONS[:2]:
        if not isinstance(report.get(key), str) or not report[key]:
            raise ValueError(f"{label}.{key} must be a nonempty string")
    for key in _CONDITIONS[2:5]:
        value = _number(
            report.get(key), f"{label}.{key}", minimum=0 if key == "warmup_iterations" else 1
        )
        if value != math.floor(value) or value > 2**53 - 1:
            raise ValueError(f"{label}.{key} must be a safe integer")
    if report.get("clock", "wall") not in ("wall", "cpu"):
        raise ValueError(f"{label}.clock must be wall or cpu")
    if not isinstance(report.get("measurements"), list):
        raise ValueError(f"{label}.measurements must be an array")
    indexed = {}
    for index, entry in enumerate(report["measurements"]):
        path = f"{label}.measurements[{index}]"
        if not isinstance(entry, dict):
            raise ValueError(f"{path} must be an object")
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"{path}.name must be a nonempty string")
        if name in indexed:
            raise ValueError(f"{label} has duplicate measurement: {name}")
        if entry.get("schema_mode") not in _MODES:
            raise ValueError(f"{path}.schema_mode must be reused, fresh, or none")
        median = _number(entry.get("median_us"), f"{path}.median_us")
        minimum = _number(entry.get("min_us"), f"{path}.min_us")
        if minimum > median:
            raise ValueError(f"{path}.min_us exceeds median_us")
        indexed[name] = {**entry, "median_us": median}
    return indexed


def _environment(value, label):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object or null")
    result = {}
    for bound in ("start", "end"):
        snapshot = value.get(bound)
        if snapshot is None:
            result[bound] = None
            continue
        path = f"{label}.{bound}"
        if not isinstance(snapshot, dict):
            raise ValueError(f"{path} must be an object or null")
        cpus = snapshot.get("logical_cpus")
        if cpus is not None:
            cpus = _number(cpus, path + ".logical_cpus", minimum=1)
            if not cpus.is_integer() or cpus > 2**53 - 1:
                raise ValueError(f"{path}.logical_cpus must be a positive safe integer or null")
            cpus = int(cpus)
        load = snapshot.get("load_average")
        if load is not None:
            if not isinstance(load, list) or len(load) != 3:
                raise ValueError(f"{path}.load_average must be an array of three numbers or null")
            load = [
                _number(item, f"{path}.load_average[{index}]") for index, item in enumerate(load)
            ]
        result[bound] = {"logical_cpus": cpus, "load_average": load}
    return result


def _conditions(report):
    return {key: report.get(key, "wall") if key == "clock" else report[key] for key in _CONDITIONS}


def _rounded(value, digits):
    scale = 10**digits
    # Reports use the same positive-half rounding rule in both runtimes.
    return math.floor(value * scale + 0.5) / scale


def _summary(rows):
    ratios = [row["_ratio"] for row in rows if row["_ratio"] is not None]
    median = statistics.median(ratios) if ratios else None
    return {
        "count": len(rows),
        "compared": len(ratios),
        **{status: sum(row["status"] == status for row in rows) for status in _STATUSES},
        "median_ratio": _rounded(median, 6) if median is not None else None,
        "median_change_percent": _rounded((median - 1) * 100, 3) if median is not None else None,
    }


def compare_reports(before, after, threshold=5):
    """Compare case medians; positive change means slower in the after report."""
    threshold = _number(threshold, "threshold")
    old, new = _report(before, "before"), _report(after, "after")
    before_conditions, after_conditions = _conditions(before), _conditions(after)
    same_clock = before_conditions["clock"] == after_conditions["clock"]
    environments = {
        "before": _environment(before.get("environment"), "before.environment"),
        "after": _environment(after.get("environment"), "after.environment"),
    }
    rows = []
    for name, current in new.items():
        if name not in old:
            continue
        previous = old[name]
        same_mode = previous["schema_mode"] == current["schema_mode"]
        ratio = None
        if not same_mode or not same_clock:
            status = "incomparable"
        elif not previous["median_us"] or not current["median_us"]:
            status = "unmeasurable"
        else:
            ratio = current["median_us"] / previous["median_us"]
            if not math.isfinite(ratio * 10**6) or not math.isfinite((ratio - 1) * 100 * 10**3):
                raise ValueError(f"comparison overflows for measurement: {name}")
            status = (
                "regressed"
                if ratio > 1 + threshold / 100
                else "improved"
                if ratio < 1 - threshold / 100
                else "unchanged"
            )
        row = {
            "name": name,
            "schema_mode": current["schema_mode"] if same_mode else None,
            "before_us": previous["median_us"],
            "after_us": current["median_us"],
            "ratio": _rounded(ratio, 6) if ratio is not None else None,
            "change_percent": _rounded((ratio - 1) * 100, 3) if ratio is not None else None,
            "status": status,
            "_ratio": ratio,
        }
        if not same_mode:
            row.update(
                before_schema_mode=previous["schema_mode"], after_schema_mode=current["schema_mode"]
            )
        if not same_clock:
            row.update(
                before_clock=before_conditions["clock"], after_clock=after_conditions["clock"]
            )
        rows.append(row)
    result = {
        "threshold_percent": threshold,
        "conditions": {
            "before": before_conditions,
            "after": after_conditions,
            "changed": [
                key for key in _CONDITIONS if before_conditions[key] != after_conditions[key]
            ],
        },
        "environment": environments,
        "before_count": len(old),
        "after_count": len(new),
        "added": [name for name in new if name not in old],
        "removed": [name for name in old if name not in new],
        "summary": _summary(rows),
        "by_schema_mode": {
            mode: _summary([row for row in rows if row["schema_mode"] == mode]) for mode in _MODES
        },
        "measurements": [
            {key: value for key, value in row.items() if key != "_ratio"} for row in rows
        ],
    }
    return result


def _percentage(value):
    if not _DECIMAL.fullmatch(value):
        raise argparse.ArgumentTypeError("must be a finite number >= 0")
    try:
        return _number(float(value), "threshold")
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def _invalid_constant(value):
    raise ValueError(f"invalid JSON constant: {value}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--threshold", type=_percentage, default=5)
    parser.add_argument("--fail-on-regression", action="store_true")
    parser.add_argument("--fail-on-incomparable", action="store_true")
    args = parser.parse_args()
    try:
        result = compare_reports(
            json.loads(args.before.read_text(), parse_constant=_invalid_constant),
            json.loads(args.after.read_text(), parse_constant=_invalid_constant),
            args.threshold,
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, allow_nan=False))
    if (
        args.fail_on_regression
        and result["summary"]["regressed"]
        or args.fail_on_incomparable
        and result["summary"]["incomparable"]
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
