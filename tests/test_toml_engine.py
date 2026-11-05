import hashlib
import json

import pytest

from benchmarks.toml_engine import SOURCE_PATHS, verify_toml_engine


@pytest.mark.parametrize(
    "change", [None, "source", "bundle", "parser", "version", "manifest", "license"]
)
def test_toml_engine_gate_detects_stale_sources_dependencies_and_artifacts(tmp_path, change):
    js_repo, package = tmp_path / "js", tmp_path / "outputguard"
    package.mkdir()
    hashes = {}
    for index, name in enumerate(SOURCE_PATHS):
        path = js_repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"source {index}")
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    dependency = js_repo / "node_modules/smol-toml"
    dependency.mkdir(parents=True)
    (dependency / "package.json").write_text('{"version":"1.9.1"}')
    (dependency / "LICENSE").write_text("BSD license")
    (package / "_toml_engine.LICENSE").write_text("BSD license")
    bundle = package / "_toml_engine.js"
    bundle.write_text("bundle")
    parser = js_repo / "src/vendor/tomlParser.js"
    parser.write_text("parser")
    metadata = {
        "smol_toml_version": "1.9.1",
        "source_hashes": hashes,
        "bundle_sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
        "parser_sha256": hashlib.sha256(parser.read_bytes()).hexdigest(),
    }
    if change == "source":
        (js_repo / SOURCE_PATHS[0]).write_text("changed source")
    elif change == "bundle":
        bundle.write_text("changed bundle")
    elif change == "parser":
        parser.write_text("changed parser")
    elif change == "version":
        (dependency / "package.json").write_text('{"version":"1.9.2"}')
    elif change == "manifest":
        metadata["source_hashes"] = {}
    elif change == "license":
        (package / "_toml_engine.LICENSE").write_text("changed license")
    (package / "_toml_engine.json").write_text(json.dumps(metadata))
    if change is None:
        verify_toml_engine(js_repo, package)
    else:
        with pytest.raises(SystemExit, match="TOML.*(stale|manifest|differ)"):
            verify_toml_engine(js_repo, package)
