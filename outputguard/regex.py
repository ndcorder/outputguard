"""ECMAScript regex matching with bounded, thread-local compiled-pattern caches."""

from __future__ import annotations

import json
import os
import re
import threading
from collections import OrderedDict

from jsonschema.exceptions import SchemaError, ValidationError

_THREAD_STATE = threading.local()
_CACHE_LIMIT = 128
_Z_ANCHOR = re.compile(r"[^\\]\\Z")
_COMPILE = """
(source, flags) => {
  const pattern = new RegExp(JSON.parse(source), flags);
  return (text, many = false) => {
    const value = JSON.parse(text);
    if (!many) return pattern.test(value);
    const matches = [];
    for (let index = 0; index < value.length; index++) {
      if (pattern.test(value[index])) matches.push(index);
    }
    return JSON.stringify(matches);
  };
}
"""


class _Runtime:
    def __init__(self):
        # The thin public quickjs wrapper eagerly creates an executor. Use its
        # native binding directly: contexts stay on their creating thread and
        # importing OutputGuard never starts a background worker.
        import _quickjs  # type: ignore[import-not-found]

        self.binding = _quickjs
        self.pid = os.getpid()
        self.context = _quickjs.Context()
        self.compile = self.context.eval(_COMPILE)
        self.patterns = OrderedDict()

    def matcher(self, pattern: str, flags: str):
        key = (pattern, flags)
        cached = self.patterns.get(key)
        if cached is not None:
            self.patterns.move_to_end(key)
            return cached
        try:
            # JSON strings cross the native boundary as ASCII. Pattern and
            # instance text never become JavaScript source, including lone
            # surrogates, embedded NULs, and JavaScript-looking payloads.
            compiled = self.compile(json.dumps(pattern, ensure_ascii=True), flags)
        except self.binding.JSException as error:
            if str(error).startswith("SyntaxError:"):
                raise SchemaError(
                    f"Invalid ECMAScript regular expression {pattern!r}: {error}"
                ) from error
            raise
        self.patterns[key] = compiled
        if len(self.patterns) > _CACHE_LIMIT:
            self.patterns.popitem(last=False)
        return compiled


def _runtime():
    runtime = getattr(_THREAD_STATE, "runtime", None)
    if runtime is None or runtime.pid != os.getpid():
        # A forked child gets a fresh runtime rather than inherited native state.
        runtime = _THREAD_STATE.runtime = _Runtime()
    return runtime


def _matcher(pattern: str, flags: str):
    if not isinstance(pattern, str):
        raise SchemaError("Regular expression patterns must be strings")
    return _runtime().matcher(pattern, flags)


def search(pattern: str, text: str) -> bool:
    return bool(_matcher(pattern, "u")(json.dumps(text, ensure_ascii=True)))


def is_regex(pattern: str) -> bool:
    # Retain ajv-formats' rejection of the non-ECMAScript end-of-string anchor.
    if _Z_ANCHOR.search(pattern):
        return False
    try:
        _matcher(pattern, "")
    except SchemaError:
        return False
    return True


def pattern(validator, expression, instance, schema):
    matcher = _matcher(expression, "u")
    if validator.is_type(instance, "string") and not matcher(
        json.dumps(instance, ensure_ascii=True)
    ):
        yield ValidationError(f"{instance!r} does not match {expression!r}")


def _matching_keys(matcher, keys, encoded):
    if encoded is not None:
        for index in json.loads(matcher(encoded, True)):
            yield keys[index]
    else:
        for key in keys:
            if matcher(json.dumps(key, ensure_ascii=True)):
                yield key


def pattern_properties(validator, patterns, instance, schema):
    compiled = [
        (expression, subschema, _matcher(expression, "u"))
        for expression, subschema in patterns.items()
        if subschema is not True and subschema != {}
    ]
    if not validator.is_type(instance, "object"):
        return
    if len(instance) < 8:
        for expression, subschema, matcher in compiled:
            for key, value in instance.items():
                if isinstance(key, str) and matcher(json.dumps(key, ensure_ascii=True)):
                    yield from validator.descend(value, subschema, path=key, schema_path=expression)
        return
    keys = [key for key in instance if isinstance(key, str)]
    encoded = json.dumps(keys, ensure_ascii=True) if len(keys) >= 8 else None
    for expression, subschema, matcher in compiled:
        for key in _matching_keys(matcher, keys, encoded):
            yield from validator.descend(instance[key], subschema, path=key, schema_path=expression)


def additional_properties(validator, constraint, instance, schema):
    if constraint is True or constraint == {} or not validator.is_type(instance, "object"):
        return
    patterns = schema.get("patternProperties", {})
    compiled = [_matcher(expression, "u") for expression in patterns]
    properties = schema.get("properties", {})
    candidates = [key for key in instance if key not in properties]
    if len(candidates) < 8:
        extras = set()
        for key in candidates:
            encoded_key = json.dumps(key, ensure_ascii=True) if isinstance(key, str) else None
            if encoded_key is None or not any(matcher(encoded_key) for matcher in compiled):
                extras.add(key)
    else:
        keys = [key for key in candidates if isinstance(key, str)]
        encoded = json.dumps(keys, ensure_ascii=True) if len(keys) >= 8 else None
        extras = set(candidates)
        for matcher in compiled:
            extras.difference_update(_matching_keys(matcher, keys, encoded))
            if not extras:
                break
    if validator.is_type(constraint, "object"):
        for key in candidates:
            if key not in extras:
                continue
            yield from validator.descend(instance[key], constraint, path=key)
    elif not constraint and extras:
        # Preserve native grouping and wording while replacing only matching.
        joined = ", ".join(repr(key) for key in sorted(extras, key=str))
        if "patternProperties" in schema:
            verb = "does" if len(extras) == 1 else "do"
            expressions = ", ".join(repr(expression) for expression in sorted(patterns))
            yield ValidationError(f"{joined} {verb} not match any of the regexes: {expressions}")
        else:
            verb = "was" if len(extras) == 1 else "were"
            yield ValidationError(
                f"Additional properties are not allowed ({joined} {verb} unexpected)"
            )
