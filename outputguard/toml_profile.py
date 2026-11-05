"""Shared TOML 1.1 parsing with lossless date strings and exact Python integers."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from outputguard._parser_graph import decode_graph

_THREAD_STATE = threading.local()


class _Runtime:
    def __init__(self):
        import _quickjs  # type: ignore[import-not-found]

        self.pid = os.getpid()
        self.context = _quickjs.Context()
        self.context.eval(Path(__file__).with_name("_toml_engine.js").read_text())
        self.parse = self.context.eval("OutputguardToml.parse")


def _runtime():
    runtime = getattr(_THREAD_STATE, "runtime", None)
    if runtime is None or runtime.pid != os.getpid():
        runtime = _THREAD_STATE.runtime = _Runtime()
    return runtime


def load_toml(text: str) -> Any:
    # Untrusted source is an ASCII JSON argument, never evaluated as code.
    result = json.loads(_runtime().parse(json.dumps(text, ensure_ascii=True)))
    if not result["ok"]:
        raise ValueError(result["error"])
    return decode_graph(result["graph"])
