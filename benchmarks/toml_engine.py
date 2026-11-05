"""Verify both generated TOML parsers against their sources and dependency."""

import hashlib
import json
from pathlib import Path

SOURCE_PATHS = (
    "src/tomlDate.ts",
    "src/tomlParserEntry.ts",
    "src/tomlProfile.ts",
    "src/tomlBridge.ts",
    "src/vendor/tomlParser.d.ts",
    "benchmarks/build_toml_engine.mjs",
)


def verify_toml_engine(js_repo: Path, package: Path) -> None:
    metadata = json.loads((package / "_toml_engine.json").read_text())
    rebuild = "Run node benchmarks/build_toml_engine.mjs from the JavaScript checkout"
    if (
        not isinstance(metadata, dict)
        or not isinstance(metadata.get("source_hashes"), dict)
        or set(metadata["source_hashes"]) != set(SOURCE_PATHS)
    ):
        raise SystemExit(f"TOML engine source manifest is incomplete. {rebuild}")
    for name in SOURCE_PATHS:
        actual = hashlib.sha256((js_repo / name).read_bytes()).hexdigest()
        if actual != metadata["source_hashes"][name]:
            raise SystemExit(f"TOML engine source is stale: {name}. {rebuild}")
    for path, key in (
        (package / "_toml_engine.js", "bundle_sha256"),
        (js_repo / "src/vendor/tomlParser.js", "parser_sha256"),
    ):
        if hashlib.sha256(path.read_bytes()).hexdigest() != metadata.get(key):
            raise SystemExit(f"TOML engine bundle does not match its manifest. {rebuild}")
    dependency = js_repo / "node_modules/smol-toml"
    if json.loads((dependency / "package.json").read_text())["version"] != metadata.get(
        "smol_toml_version"
    ):
        raise SystemExit(f"TOML engine dependency version is stale. {rebuild}")
    if (package / "_toml_engine.LICENSE").read_bytes() != (dependency / "LICENSE").read_bytes():
        raise SystemExit(f"TOML engine license differs from its dependency. {rebuild}")
