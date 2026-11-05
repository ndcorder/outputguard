"""Private schema-format assertions, independent of optional jsonschema extras."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from jsonschema import FormatChecker

from outputguard.regex import is_regex

# The shared patterns are adapted from ajv-formats. Its license is distributed
# beside the data, which is also bundled in the JavaScript implementation.
_PATTERNS = json.loads(Path(__file__).with_name("_schema_format_patterns.json").read_text())
_DATE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")
_TIME = re.compile(
    r"([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.[0-9]+)?"
    r"(z|([+-])([0-9]{2})(?::?([0-9]{2}))?)?",
    re.IGNORECASE | re.ASCII,
)
_URL_SCHEME = re.compile(r"(?:https?|ftp)://", re.IGNORECASE | re.ASCII)
_JS_WHITESPACE = re.compile(
    r"[\x09-\x0d \xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]"
)


def _date(value: str) -> bool:
    match = _DATE.fullmatch(value)
    if match is None:
        return False
    year, month, day = map(int, match.groups())
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    days = (0, 31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    return 1 <= month <= 12 and 1 <= day <= days[month]


def _time(value: str, *, timezone: bool) -> bool:
    match = _TIME.fullmatch(value)
    if match is None:
        return False
    hour, minute, second = map(int, match.groups()[:3])
    zone, sign, zone_hour, zone_minute = match.groups()[3:]
    offset_hour, offset_minute = int(zone_hour or 0), int(zone_minute or 0)
    if (
        hour > 23
        or minute > 59
        or second > 60
        or offset_hour > 23
        or offset_minute > 59
        or (timezone and zone is None)
    ):
        return False
    if second < 60:
        return True
    offset = (offset_hour * 60 + offset_minute) * (-1 if sign == "-" else 1)
    return (hour * 60 + minute - offset) % 1440 == 1439


def _date_time(value: str, *, timezone: bool) -> bool:
    parts = re.split("[Tt ]", value)
    return len(parts) == 2 and _date(parts[0]) and _time(parts[1], timezone=timezone)


def _integer(value: int | float) -> bool:
    return isinstance(value, int) or value.is_integer()


def _pattern_checker(source: str, ignore_case: bool) -> Callable[[str], bool]:
    source = re.sub(r"\\u\{([0-9a-f]+)\}", lambda match: chr(int(match[1], 16)), source)
    pattern = re.compile(source, re.ASCII | (re.IGNORECASE if ignore_case else 0))
    return lambda value: pattern.fullmatch(value) is not None


_STRING_CHECKS: dict[str, Callable[[str], bool]] = {
    name: _pattern_checker(**definition) for name, definition in _PATTERNS.items()
}
_url_pattern = _STRING_CHECKS["url"]
_STRING_CHECKS["url"] = lambda value: (
    _URL_SCHEME.match(value) is not None
    and _JS_WHITESPACE.search(value) is None
    and _url_pattern(value)
)
_STRING_CHECKS.update(
    {
        "date": _date,
        "time": lambda value: _time(value, timezone=True),
        "iso-time": lambda value: _time(value, timezone=False),
        "date-time": lambda value: _date_time(value, timezone=True),
        "iso-date-time": lambda value: _date_time(value, timezone=False),
        "regex": is_regex,
    }
)
_NUMBER_CHECKS: dict[str, Callable[[Any], bool]] = {
    "int32": lambda value: _integer(value) and -(2**31) <= value < 2**31,
    "int64": lambda value: _integer(value) and -(2**63) <= value < 2**63,
    "float": lambda value: True,
    "double": lambda value: True,
}


def _strings(check):
    return lambda value: not isinstance(value, str) or check(value)


def _numbers(check):
    return lambda value: (
        isinstance(value, bool) or not isinstance(value, (int, float)) or check(value)
    )


# Start empty so installing jsonschema extras or registering a native checker
# elsewhere cannot silently change OutputGuard's supported assertion profile.
SCHEMA_FORMAT_CHECKER = FormatChecker(formats=[])
for _name, _check in _STRING_CHECKS.items():
    SCHEMA_FORMAT_CHECKER.checks(_name)(_strings(_check))
for _name, _check in _NUMBER_CHECKS.items():
    SCHEMA_FORMAT_CHECKER.checks(_name)(_numbers(_check))
