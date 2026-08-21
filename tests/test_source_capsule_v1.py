import importlib.util
import io
import json
from pathlib import Path
import shutil
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "build_source_capsule_v1.py"
spec = importlib.util.spec_from_file_location("synergynet_source_capsule_v1", TOOL)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def test_recipe_is_non_executable_and_discloses_unpinned_interpreter():
    recipe = module.load_and_verify_recipe(ROOT)
    assert recipe["recipe_digest"] == "5202b60cd607a8c88f97aa4cd5b9ba9ed6c304715f445f32cc610fcd61ee2bd3"
    assert recipe["dependency_manifest"] is None
    assert recipe["dependency_lock_status"] == "STDLIB_ONLY_DEPENDENCIES_INTERPRETER_NOT_PINNED"
    assert recipe["artifact_kind"] == "NON_EXECUTABLE_DETERMINISTIC_SOURCE_CAPSULE"
    assert recipe["build_evidence_status"] == "NOT_EXECUTED"
    assert recipe["execution_authority"] == "NONE"


def test_two_source_capsule_builds_are_byte_identical():
    first, manifest_a = module.build_capsule_bytes(ROOT)
    second, manifest_b = module.build_capsule_bytes(ROOT)
    assert first == second
    assert manifest_a == manifest_b
    assert module.verify_capsule_bytes(first) == manifest_a


def test_capsule_contains_transport_persistent_store_and_codec_sources():
    capsule, manifest = module.build_capsule_bytes(ROOT)
    paths = {record["path"] for record in manifest["files"]}
    assert {
        "src/synergynet/lab.py",
        "src/synergynet/tcp_baseline.py",
        "src/synergynet/tcp_transport.py",
        "src/synergynet/storage_v3.py",
        "src/synergynet/persistent_lab_v3.py",
    }.issubset(paths)
    with zipfile.ZipFile(io.BytesIO(capsule), "r") as archive:
        infos = archive.infolist()
        assert [info.filename for info in infos] == sorted(info.filename for info in infos)
        assert all(info.date_time == module.FIXED_ZIP_DATETIME for info in infos)
        assert all(info.compress_type == zipfile.ZIP_STORED for info in infos)


def test_manifest_hashes_exact_repository_source_bytes():
    capsule, manifest = module.build_capsule_bytes(ROOT)
    with zipfile.ZipFile(io.BytesIO(capsule), "r") as archive:
        for record in manifest["files"]:
            data = archive.read(record["path"])
            assert data == (ROOT / record["path"]).read_bytes()
            assert record["bytes"] == len(data)
            assert record["sha256"] == module._sha256(data)


def test_path_traversal_is_rejected():
    for raw in ("../x", "/tmp/x", "a/../../x", "a\\b"):
        with pytest.raises(module.CapsuleBuildError):
            module._validate_relative_path(raw)


def test_symlink_source_is_rejected(tmp_path):
    recipe = module.load_and_verify_recipe(ROOT)
    for relative in recipe["source_paths"]:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    outside = tmp_path / "outside.py"
    outside.write_text("print('outside')", encoding="utf-8")
    victim = tmp_path / "src/synergynet/lab.py"
    victim.unlink()
    try:
        victim.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    with pytest.raises(module.CapsuleBuildError, match="symlink source forbidden"):
        module.build_capsule_bytes(tmp_path)


def test_fresh_recipe_digest_cannot_claim_executable_environment(tmp_path):
    recipe = json.loads((ROOT / "config/synergynet_source_capsule_recipe_v1.json").read_text(encoding="utf-8"))
    recipe["artifact_kind"] = "EXECUTABLE"
    recipe["dependency_lock_status"] = "PRODUCTION_RUNTIME_LOCKED"
    recipe["execution_authority"] = "RUN"
    recipe["recipe_digest"] = module._recipe_digest(recipe)
    path = tmp_path / "config/synergynet_source_capsule_recipe_v1.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(recipe), encoding="utf-8")
    with pytest.raises(module.CapsuleBuildError):
        module.load_and_verify_recipe(tmp_path)
