"""Verify that the shipped YAML engine matches its JavaScript source and dependency."""

import hashlib
import json
from pathlib import Path

SOURCE_PATHS = (
    "src/yamlProfile.ts",
    "src/yamlBridge.ts",
    "src/yamlPatterns.json",
    "benchmarks/build_yaml_engine.mjs",
)


def verify_yaml_engine(js_repo: Path, package: Path) -> None:
    metadata = json.loads((package / "_yaml_engine.json").read_text())
    rebuild = "Run node benchmarks/build_yaml_engine.mjs from the JavaScript checkout"
    if (
        not isinstance(metadata, dict)
        or not isinstance(metadata.get("source_hashes"), dict)
        or set(metadata["source_hashes"]) != set(SOURCE_PATHS)
    ):
        raise SystemExit(f"YAML engine source manifest is incomplete. {rebuild}")
    for path in SOURCE_PATHS:
        actual = hashlib.sha256((js_repo / path).read_bytes()).hexdigest()
        if actual != metadata["source_hashes"][path]:
            raise SystemExit(f"YAML engine source is stale: {path}. {rebuild}")
    actual = hashlib.sha256((package / "_yaml_engine.js").read_bytes()).hexdigest()
    if actual != metadata.get("bundle_sha256"):
        raise SystemExit(f"YAML engine bundle does not match its manifest. {rebuild}")
    version = json.loads((js_repo / "node_modules/yaml/package.json").read_text())["version"]
    if version != metadata.get("yaml_version"):
        raise SystemExit(f"YAML engine dependency version is stale. {rebuild}")
    if (package / "_yaml_patterns.json").read_bytes() != (
        js_repo / "src/yamlPatterns.json"
    ).read_bytes():
        raise SystemExit(f"YAML core patterns differ between checkouts. {rebuild}")
    if (package / "_yaml_engine.LICENSE").read_bytes() != (
        js_repo / "node_modules/yaml/LICENSE"
    ).read_bytes():
        raise SystemExit(f"YAML engine license differs from its dependency. {rebuild}")
