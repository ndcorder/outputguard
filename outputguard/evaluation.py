"""Extend Draft 7 evaluation without changing global native validators."""

from contextvars import ContextVar
from typing import Literal

import jsonschema
from jsonschema.validators import extend, validator_for

from outputguard.numeric import multiple_of
from outputguard.regex import additional_properties, pattern, pattern_properties
from outputguard.schema import _PreparedSchema, prepare_pointer_document

_active_references: ContextVar[set[tuple[int, int, str]] | Literal[False] | None] = ContextVar(
    "outputguard_active_references", default=None
)
_native_ref = jsonschema.Draft7Validator.VALIDATORS["$ref"]


def begin_evaluation():
    # False enables tracking without allocating a set for reference-free calls.
    return _active_references.set(False)


def end_evaluation(token):
    _active_references.reset(token)


def _guarded_ref(validator, ref, instance, schema):
    active = _active_references.get()
    if active is None:
        yield from _native_ref(validator, ref, instance, schema)
        return
    if active is False:
        active = set()
        _active_references.set(active)
    original = schema
    while isinstance(original, _PreparedSchema):
        original = original._source
    resolver = getattr(validator, "_resolver", None)
    key = (id(original), id(instance), getattr(resolver, "_base_uri", ""))
    if key in active:
        raise RecursionError("Schema reference revisits an active schema and instance")
    active.add(key)
    try:
        yield from _native_ref(validator, ref, instance, schema)
    finally:
        active.remove(key)


class _ScopedEvaluation(_PreparedSchema):
    def __init__(self, source):
        # Native descend() enters the child's resource. The native keyword can
        # still perform its boolean test and construct its usual diagnostics.
        super().__init__(source, {"allOf": [source]})


def _with_scope(schema):
    if isinstance(schema, dict) and "$ref" not in schema:
        identifier = schema.get("$id")
        if isinstance(identifier, str) and identifier and not identifier.startswith("#"):
            return _ScopedEvaluation(schema)
    return schema


def _scoped_keyword(keyword):
    native = jsonschema.Draft7Validator.VALIDATORS[keyword]

    def validate(validator, value, instance, schema):
        if keyword == "oneOf":
            prepared = None
            for index, child in enumerate(value):
                scoped = _with_scope(child)
                if scoped is not child:
                    if prepared is None:
                        prepared = list(value)
                    prepared[index] = scoped
            if prepared is not None:
                value = prepared
        else:
            value = _with_scope(value)
        return native(validator, value, instance, schema)

    return validate


Draft7Validator = extend(
    jsonschema.Draft7Validator,
    {
        **{keyword: _scoped_keyword(keyword) for keyword in ("if", "contains", "not", "oneOf")},
        "multipleOf": multiple_of,
        "pattern": pattern,
        "patternProperties": pattern_properties,
        "additionalProperties": additional_properties,
        "$ref": _guarded_ref,
    },
)


class _SameDraftSchema(_PreparedSchema):
    def __init__(self, source):
        super().__init__(prepare_pointer_document(source))

    def get(self, key, default=None):
        if key == "$schema":
            return default
        return self._source.get(key, default)

    def __contains__(self, key):
        return key != "$schema" and key in self._source

    def __getitem__(self, key):
        return self._source[key]

    def items(self):
        return self._source.items()


def _evolve(self, **changes):
    schema = changes.get("schema", self.schema)
    dialect = schema.get("$schema") if isinstance(schema, dict) else None
    if (
        dialect
        and validator_for({"$schema": dialect}, default=self.__class__)
        is jsonschema.Draft7Validator
    ):
        # evolve() would otherwise select the globally registered native class
        # and lose this extension. Only its dialect selection sees this view;
        # keyword iteration, pointers, metadata, and source repr stay intact.
        changes["schema"] = _SameDraftSchema(schema)
    return jsonschema.Draft7Validator.evolve(self, **changes)


def _descend(self, *args, **kwargs):
    # Retain the dependency's current descent implementation, including native
    # boolean-path fixes, while evolve() keeps these local keyword handlers.
    return jsonschema.Draft7Validator.descend(self, *args, **kwargs)


# This class is local and unregistered. Native classes and global dialect
# selection remain unchanged, including when other libraries use jsonschema.
Draft7Validator.evolve = _evolve
Draft7Validator.descend = _descend
