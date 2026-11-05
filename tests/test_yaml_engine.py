import hashlib
import json

import pytest

from benchmarks.yaml_engine import SOURCE_PATHS, verify_yaml_engine


@pytest.mark.parametrize(
    "change", [None, "source", "bundle", "version", "patterns", "manifest", "license"]
)
def test_yaml_engine_gate_detects_stale_sources_dependencies_and_artifacts(tmp_path, change):
    js_repo, package = tmp_path / "js", tmp_path / "outputguard"
    package.mkdir()
    hashes = {}
    for index, name in enumerate(SOURCE_PATHS):
        path = js_repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"source {index}")
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    dependency = js_repo / "node_modules/yaml/package.json"
    dependency.parent.mkdir(parents=True)
    dependency.write_text('{"version":"2.9.0"}')
    (dependency.parent / "LICENSE").write_text("ISC license")
    (package / "_yaml_engine.LICENSE").write_text("ISC license")
    bundle = package / "_yaml_engine.js"
    bundle.write_text("bundle")
    patterns = package / "_yaml_patterns.json"
    patterns.write_bytes((js_repo / "src/yamlPatterns.json").read_bytes())
    metadata = {
        "yaml_version": "2.9.0",
        "source_hashes": hashes,
        "bundle_sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
    }
    if change == "source":
        (js_repo / SOURCE_PATHS[0]).write_text("changed source")
    elif change == "bundle":
        bundle.write_text("changed bundle")
    elif change == "version":
        dependency.write_text('{"version":"2.9.1"}')
    elif change == "patterns":
        patterns.write_text("changed patterns")
    elif change == "manifest":
        metadata["source_hashes"] = {}
    elif change == "license":
        (package / "_yaml_engine.LICENSE").write_text("changed license")
    (package / "_yaml_engine.json").write_text(json.dumps(metadata))
    if change is None:
        verify_yaml_engine(js_repo, package)
    else:
        with pytest.raises(SystemExit, match="YAML.*(stale|manifest|differ)"):
            verify_yaml_engine(js_repo, package)
