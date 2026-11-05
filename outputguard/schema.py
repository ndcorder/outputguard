"""Prepare schema views for resource discovery and boolean-error locations."""

import re
from urllib.parse import quote, unquote
from weakref import WeakValueDictionary

import jsonschema
from referencing.exceptions import Unresolvable
from referencing.jsonschema import DRAFT7

from outputguard.models import Schema


class _BooleanSchema(dict):
    """Validate a boolean target without exposing object keys to pointers."""

    def __init__(self, value):
        self._value = value
        super().__init__({} if value else {"not": {}})

    def __contains__(self, key):
        # Boolean resources have neither child schemas nor metadata. Keyword
        # iteration still evaluates the equivalent constraint for False.
        return False

    def __getitem__(self, key):
        raise KeyError(key)

    def __repr__(self):
        return repr(self._value)


# An equivalent object constraint preserves false-schema error paths and also
# prevents native pointer traversal from trying to index a Python bool.
_FALSE_SCHEMA: dict = _BooleanSchema(False)
_TRUE_SCHEMA: dict = _BooleanSchema(True)
_probe = next(
    jsonschema.Draft7Validator({}).descend(None, False, path="value", schema_path="value")
)
_NEEDS_FALSE_PATH_FIX = not _probe.path or not _probe.schema_path
_dependency_probe = {"dependencies": {"property": ["needed"], "schema": {}}}
_NEEDS_DEPENDENCY_RESOURCE_FIX = any(
    list(DRAFT7.subresources_of({"dependencies": dict(entries)})) != [{}]
    for entries in (
        list(_dependency_probe["dependencies"].items()),
        list(reversed(_dependency_probe["dependencies"].items())),
    )
)
_PLAIN_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]*\Z")
_ARRAY_INDEX = re.compile(r"(?:0|[1-9][0-9]*)\Z")
_DRAFT7_SCHEMA_MAPS = {"properties", "patternProperties", "definitions", "dependencies"}
_SCHEMA_MAPS = _DRAFT7_SCHEMA_MAPS | {"$defs"}
_SCHEMA_ARRAYS = {"allOf", "anyOf", "oneOf"}
_SINGLE_SCHEMAS = {
    "additionalProperties",
    "additionalItems",
    "contains",
    "propertyNames",
    "not",
    "if",
    "then",
    "else",
}
_LITERAL_KEYWORDS = {
    "default",
    "enum",
    "const",
    "required",
    "maximum",
    "minimum",
    "exclusiveMaximum",
    "exclusiveMinimum",
    "multipleOf",
    "maxLength",
    "minLength",
    "pattern",
    "format",
    "maxItems",
    "minItems",
    "uniqueItems",
    "maxProperties",
    "minProperties",
}


class _DependencyResources(dict):
    """Expose only resource-bearing schemas to the legacy dependency crawler.

    Draft 7 validation uses items(), and JSON Pointers use __getitem__(), so
    property lists and boolean dependencies retain their original behavior.
    """

    def values(self):
        return (value for value in super().values() if isinstance(value, dict))


def _normalize_reference(reference: str) -> str:
    if "%" not in reference:
        return reference
    document, separator, fragment = reference.partition("#")
    if not separator:
        return reference
    if fragment[:3].lower() == "%2f":
        # Decode only the leading slash here. Resource.pointer() decodes the
        # complete pointer once before splitting it into JSON Pointer tokens.
        return document + "#/" + fragment[3:]
    name = unquote(fragment)
    if name != fragment and _PLAIN_NAME.fullmatch(name):
        return document + "#" + name
    return reference


def _mixed_dependencies(value) -> bool:
    return (
        isinstance(value, dict)
        and any(isinstance(child, dict) for _, child in value.items())
        and any(not isinstance(child, dict) for _, child in value.items())
    )


def prepare_reference_lookup(schema: Schema) -> Schema:
    """Repair native fragment or dependency lookup failures with document views."""
    fragments = dependencies = pointers = scopes = False
    pending = [schema]
    seen = set()
    while pending:
        value = pending.pop()
        if not isinstance(value, (dict, list)) or id(value) in seen:
            continue
        seen.add(id(value))
        if isinstance(value, dict):
            reference = value.get("$ref")
            if isinstance(reference, str):
                normalized = _normalize_reference(reference)
                fragments |= normalized != reference
                pointers |= normalized.partition("#")[2].startswith("/")
            dependencies |= _NEEDS_DEPENDENCY_RESOURCE_FIX and _mixed_dependencies(
                value.get("dependencies")
            )
            scopes |= isinstance(value.get("dependencies"), dict) or isinstance(
                value.get("items"), (dict, list)
            )
            pending.extend(child for _, child in value.items())
        else:
            pending.extend(value)
        if fragments and dependencies and pointers and scopes:
            break
    if not fragments and not dependencies and not (scopes and pointers):
        return schema
    # Named resources and anchors do not need the source-backed pointer views.
    return _SchemaPreparation(pointers=pointers, fragments=fragments, dependencies=dependencies)(
        schema
    )


def _rewrite_schema(schema: Schema, view, copy_schema=None) -> Schema:
    if schema is False:
        return _FALSE_SCHEMA if view.false_schemas else schema
    if schema is True:
        return schema
    result = schema

    def child(value):
        return view(value) if isinstance(value, (dict, bool)) else value

    def set_value(keyword, value):
        nonlocal result
        if value is schema[keyword]:
            return
        if result is schema:
            result = schema.copy() if copy_schema is None else copy_schema(schema)
        result[keyword] = value

    for keyword, value in schema.items():
        if keyword == "$ref" and view.fragments and isinstance(value, str):
            set_value(keyword, _normalize_reference(value))
        elif keyword in _SCHEMA_MAPS and isinstance(value, dict):
            updated = {name: child(subschema) for name, subschema in value.items()}
            if keyword == "dependencies" and view.dependencies and _mixed_dependencies(value):
                set_value(keyword, _DependencyResources(updated))
            elif any(updated[name] is not subschema for name, subschema in value.items()):
                set_value(keyword, updated)
        elif (keyword in _SCHEMA_ARRAYS or keyword == "items") and isinstance(value, list):
            updated_items = [child(subschema) for subschema in value]
            if any(updated is not old for updated, old in zip(updated_items, value, strict=True)):
                set_value(keyword, updated_items)
        elif keyword in _SINGLE_SCHEMAS or keyword == "items":
            # These two keywords handle False themselves and report the containing
            # object/array. Preserve that behavior instead of per-value failures.
            if keyword in {"additionalProperties", "additionalItems"} and value is False:
                continue
            set_value(keyword, child(value))
        elif keyword not in _LITERAL_KEYWORDS:
            # Object-valued annotations can become schemas through an explicit
            # JSON Pointer. Keep literal const/enum/default data unchanged.
            set_value(keyword, child(value))
    return result


class _PreparedSchema(dict):
    def __init__(self, source, prepared=None):
        self._source = source
        super().__init__(source if prepared is None else prepared)

    def __repr__(self):
        # Native keyword messages may quote a subschema. Show the caller's
        # schema rather than the internal equivalent false constraint.
        return repr(self._source)


class _SchemaView(_PreparedSchema):
    def __init__(self, source, view):
        self._view = view
        # Keyword iteration validates prepared constraints. Literal values such
        # as const/enum/default retain their original data representation.
        super().__init__(source, _rewrite_schema(source, view))

    def __getitem__(self, key):
        # JSON Pointer traversal can turn any document value into a schema.
        # Start from the source so preparation never changes a literal target.
        return _pointer_value(self._source, key, self._view)


def _pointer_value(source, key, view):
    value = source[key]
    if not isinstance(value, (dict, list, bool)):
        raise KeyError(key)
    if key in _DRAFT7_SCHEMA_MAPS and isinstance(value, dict):
        return view.mapping(value, dependencies=key == "dependencies")
    if key in _SINGLE_SCHEMAS or key == "items" or key in _SCHEMA_ARRAYS:
        return _pointer_schema(value, view)
    return view.data(value)


def _pointer_schema(value, view):
    if isinstance(value, bool):
        return _TRUE_SCHEMA if value else _FALSE_SCHEMA
    return _PointerArray(value, view) if isinstance(value, list) else view(value)


class _PointerDocument(_PreparedSchema):
    """Provide correct pointer roles from the first lookup without a tree walk."""

    def __init__(self, source, view=None):
        super().__init__(source)
        self._view = view

    def _scope(self):
        if self._view is None:
            self._view = _PointerPreparation(self._source)
        return self._view

    def get(self, key, default=None):
        value = dict.get(self, key, default)
        if key == "dependencies" and isinstance(value, dict):
            return self._scope().mapping(value, dependencies=True)
        if key == "items" and isinstance(value, (dict, list)):
            return self._scope()(value)
        return value

    def __getitem__(self, key):
        value = self._source[key]
        if not isinstance(value, (dict, list)):
            if isinstance(value, bool):
                return _TRUE_SCHEMA if value else _FALSE_SCHEMA
            raise KeyError(key)
        return _pointer_value(self._source, key, self._scope())


def prepare_pointer_document(schema: Schema) -> Schema:
    if not isinstance(schema, dict) or isinstance(
        schema, (_SchemaView, _DataView, _PointerDocument)
    ):
        return schema
    return _PointerDocument(schema)


class _DataView(_PreparedSchema):
    """Keep IDs out of pointer scope while retaining schema/literal contents."""

    def __init__(self, source, view):
        self._view = view
        self._schema_mode = False
        self._schema_view = None
        self._reference_rewrite = getattr(view, "fragments", False)
        super().__init__(source)

    def _schema(self):
        if self._schema_view is None:
            self._schema_view = self._view.project(self._source)
        return self._schema_view

    def get(self, key, default=None):
        if key == "$id":
            return default
        if key == "$schema" or key == "$ref" and not self._reference_rewrite:
            return dict.get(self, key, default)
        return self._schema().get(key, default)

    def items(self):
        # A pointer may select this entire value as a schema. Keyword iteration
        # then uses schema constraints while literal comparisons remain intact.
        self._schema_mode = True
        return self._schema().items()

    def __getitem__(self, key):
        if self._schema_mode:
            return self._schema()[key]
        value = self._source[key]
        if not isinstance(value, (dict, list, bool)):
            raise KeyError(key)
        return self._view.data(value)


class _SchemaMapView(_DataView):
    """Map keys name schemas; none of the keys is metadata for the map itself."""

    def __init__(self, source, view, dependencies):
        super().__init__(source, view)
        self._dependencies = dependencies

    def __getitem__(self, key):
        if self._schema_mode:
            return self._schema()[key]
        value = self._source[key]
        if not isinstance(value, (dict, list, bool)):
            raise KeyError(key)
        return _pointer_schema(value, self._view)

    def values(self):
        for value in dict.values(self):
            if not self._dependencies or isinstance(value, dict):
                yield self._view(value) if isinstance(value, (dict, bool)) else value


class _ArrayView(list):
    def __init__(self, source, view):
        self._source = source
        self._view = view
        super().__init__(source)

    def __getitem__(self, key):
        return self._view(self._source[key])

    def __iter__(self):
        return (self._view(value) for value in self._source)


class _PointerArray:
    """Keep pointer tokens intact until their RFC 6901 syntax is checked.

    This deliberately isn't a Sequence: the native resolver converts Sequence
    indexes with int(), losing leading zeros, signs, and non-ASCII digits.
    Keyword validation still receives ordinary lists through items()/get().
    """

    def __init__(self, source, view, data=False):
        self._source = source
        self._view = view
        self._data = data

    def _child(self, value):
        return self._view.data(value) if self._data else _pointer_schema(value, self._view)

    def __getitem__(self, key):
        if (
            not isinstance(key, str)
            or not _ARRAY_INDEX.fullmatch(key)
            or len(key) > len(str(len(self._source)))
        ):
            raise IndexError(key)
        value = self._source[int(key)]
        if not isinstance(value, (dict, list, bool)):
            raise IndexError(key)
        return self._child(value)

    def get(self, key, default=None):
        # Resource discovery reads metadata while traversing this array.
        # Asking for assertion keywords means it was selected as a schema.
        if key == "$ref":
            _invalid_pointer_target(self._view.root, self._source)
        return default

    def items(self):
        _invalid_pointer_target(self._view.root, self._source)

    def __iter__(self):
        return (self._child(value) for value in self._source)

    def __repr__(self):
        return repr(self._source)


def _invalid_pointer_target(root, target):
    """Locate a rejected array only on failure, keeping successful lookups lazy."""
    while isinstance(target, (_PreparedSchema, _ArrayView, _PointerArray)):
        target = target._source
    pending = [(root, [])]
    seen = set()
    while pending:
        value, parts = pending.pop()
        while isinstance(value, (_PreparedSchema, _ArrayView, _PointerArray)):
            value = value._source
        if value is target:
            pointer = ("/" if parts else "") + "/".join(
                str(part).replace("~", "~0").replace("/", "~1") for part in parts
            )
            raise Unresolvable(ref="#" + quote(pointer, safe="/~"))
        if not isinstance(value, (dict, list)) or id(value) in seen:
            continue
        seen.add(id(value))
        children = value.items() if isinstance(value, dict) else enumerate(value)
        pending.extend((child, [*parts, key]) for key, child in children)
    raise Unresolvable(ref="#")


class _PointerPreparation:
    """Prepare visited pointer nodes lazily while leaving validation native."""

    def __init__(self, root) -> None:
        self.root = root
        self.cache: WeakValueDictionary | None = None

    def __call__(self, value):
        if value is _FALSE_SCHEMA or value is _TRUE_SCHEMA or not isinstance(value, dict):
            return _ArrayView(value, self) if isinstance(value, list) else value
        if self.cache is None:
            self.cache = WeakValueDictionary()
        cached = self.cache.get(id(value))
        if cached is None:
            cached = _PointerDocument(value, self)
            self.cache[id(value)] = cached
        return cached

    def project(self, value):
        # A data/map frame retains its projection for this lookup. It does not
        # need an entry in the separate cache for declared schema nodes.
        return _PointerDocument(value, self)

    def mapping(self, value, dependencies=False):
        return _SchemaMapView(value, self, dependencies)

    def data(self, value):
        if isinstance(value, bool):
            return _TRUE_SCHEMA if value else _FALSE_SCHEMA
        if not isinstance(value, (dict, list)) or value is _FALSE_SCHEMA:
            return value
        return (
            _DataView(value, self)
            if isinstance(value, dict)
            else _PointerArray(value, self, data=True)
        )


class _SchemaPreparation:
    def __init__(
        self, pointers: bool = False, fragments: bool = False, dependencies: bool = False
    ) -> None:
        self.has_references = False
        self.root = None
        self.false_schemas = _NEEDS_FALSE_PATH_FIX
        self.fragments = fragments
        self.dependencies = dependencies or (pointers and _NEEDS_DEPENDENCY_RESOURCE_FIX)
        # Views retain this callable. Weak entries prevent a cache cycle while
        # reusing views held by validators and resources during this call.
        self.cache: WeakValueDictionary | None = WeakValueDictionary() if pointers else None

    def mapping(self, value, dependencies=False):
        # Pointer frames are fresh: a leaf may become a schema during keyword
        # iteration without changing the role of a later traversal of the map.
        return _SchemaMapView(value, self, dependencies)

    def project(self, value):
        return self(value)

    def data(self, value):
        if value is _FALSE_SCHEMA:
            return value
        if isinstance(value, bool):
            return _TRUE_SCHEMA if value else _FALSE_SCHEMA
        if not isinstance(value, (dict, list)):
            return value
        return (
            _DataView(value, self)
            if isinstance(value, dict)
            else _PointerArray(value, self, data=True)
        )

    def __call__(self, value):
        if self.root is None:
            self.root = value
        if value is _FALSE_SCHEMA or value is _TRUE_SCHEMA:
            return value
        if self.cache is None:
            if isinstance(value, dict) and isinstance(value.get("$ref"), str):
                self.has_references = True
            return _rewrite_schema(value, self, _PreparedSchema)
        if value is False:
            return _FALSE_SCHEMA if self.false_schemas else value
        while isinstance(value, (_PreparedSchema, _ArrayView)):
            if isinstance(value, (_SchemaView, _ArrayView)) and value._view is self:
                return value
            value = value._source
        if not isinstance(value, (dict, list)):
            return value
        cached = self.cache.get(id(value))
        if cached is None:
            cached = (
                _SchemaView(value, self) if isinstance(value, dict) else _ArrayView(value, self)
            )
            self.cache[id(value)] = cached
        return cached


def prepare_schema(schema: Schema) -> Schema:
    # Newer jsonschema versions preserve these paths natively.
    if not _NEEDS_FALSE_PATH_FIX:
        return schema
    # Reference-free schemas need no pointer views. Discover nested references
    # during the existing preparation walk, skipping literal data throughout.
    if not (isinstance(schema, dict) and isinstance(schema.get("$ref"), str)):
        preparation = _SchemaPreparation()
        prepared = preparation(schema)
        if not preparation.has_references:
            return prepared
    return _SchemaPreparation(pointers=True)(schema)
