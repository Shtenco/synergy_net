from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from synergynet.service_build_recipe_v1 import (
    EXPECTED_RECIPE_DIGEST,
    TransportBuildError,
    build_transport_archive,
    verify_recipe,
    verify_source_tree,
)


ROOT = Path(__file__).resolve().parents[1]
RECIPE_PATH = ROOT / "config" / "research_transport_build_recipe_v1.json"


def _recipe() -> dict:
    return json.loads(RECIPE_PATH.read_text(encoding="utf-8"))


def test_recipe_is_exact_and_stdlib_only() -> None:
    recipe = verify_recipe(_recipe())
    assert recipe["recipe_digest"] == EXPECTED_RECIPE_DIGEST
    assert recipe["dependency_contract"] == "PYTHON_STDLIB_ONLY"
    assert recipe["dependency_lock_status"] == "STDLIB_ONLY_NO_THIRD_PARTY_RUNTIME_DEPENDENCIES"
    assert recipe["service_roles"] == ["CONTENT_CACHE", "SYNERGYNET"]
    assert recipe["execution_authority"] == "NONE"


def test_current_transport_source_matches_frozen_blobs() -> None:
    files = verify_source_tree(ROOT, _recipe())
    assert [f.path for f in files] == [item["path"] for item in _recipe()["include_files"]]


def test_repeated_builds_are_byte_identical(tmp_path: Path) -> None:
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    e1 = build_transport_archive(ROOT, _recipe(), first)
    e2 = build_transport_archive(ROOT, _recipe(), second)
    assert first.read_bytes() == second.read_bytes()
    assert e1 == e2
    assert e1["build_status"] == "ARTIFACT_BUILT_TEST_EVIDENCE_PENDING"
    assert e1["test_evidence_status"] == "NOT_ATTESTED"
    assert e1["execution_authority"] == "NONE"


def test_runtime_tamper_is_rejected(tmp_path: Path) -> None:
    shadow = tmp_path / "repo"
    for item in _recipe()["include_files"]:
        src = ROOT / item["path"]
        dst = shadow / item["path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    target = shadow / "src" / "synergynet" / "static_relay_v1.py"
    target.write_bytes(target.read_bytes() + b"\n# tamper\n")
    with pytest.raises(TransportBuildError, match="source blob drift"):
        verify_source_tree(shadow, _recipe())


def test_fresh_hash_cannot_add_payment_or_execution_authority() -> None:
    recipe = _recipe()
    recipe["execution_authority"] = "NETWORK_EXECUTOR"
    recipe["recipe_digest"] = "0" * 64
    with pytest.raises(TransportBuildError):
        verify_recipe(recipe)
