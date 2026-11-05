"""Decode shared parser graphs without losing native Python numeric types."""

from __future__ import annotations

import math
from typing import Any


def decode_graph(graph: dict) -> Any:
    values: list[Any] = []
    # Records are in postorder; aliases reference an already completed value.
    # Reusing those values preserves shared-container identity without cycles.
    for node in graph["nodes"]:
        kind = node["kind"]
        if kind == "str" or kind == "bool":
            value = node["value"]
        elif kind == "null":
            value = None
        elif kind == "seq":
            value = [values[index] for index in node["items"]]
        elif kind == "map":
            value = {values[key]: values[item] for key, item in node["entries"]}
        elif kind == "int":
            source = node["source"]
            if source.startswith("0o"):
                value = int(source[2:], 8)
            elif source.startswith("0x"):
                value = int(source[2:], 16)
            else:
                value = int(source, 10)
        elif kind == "float":
            source = node["source"]
            if source[-3:].lower() == "inf":
                value = -math.inf if source.startswith("-") else math.inf
            elif source[-3:].lower() == "nan":
                value = math.nan
            else:
                value = float(source)
        else:  # pragma: no cover - bundled bridge protocol invariant
            raise ValueError(f"Unknown parser graph node kind: {kind}")
        values.append(value)
    return values[graph["root"]]
