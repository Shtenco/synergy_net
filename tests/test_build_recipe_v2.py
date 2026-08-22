from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest

from synergynet.build_recipe_v2 import BuildRecipeV2Error, recipe_digest, verify_build_recipe_v2


ROOT = Path(__file__).resolve().parents[1]


def _recipe() -> dict:
    return json.loads((ROOT / "config/build_recipe_v2.json").read_text(encoding="utf-8"))


def test_build_recipe_v2_binds_service_source_without_reproducibility_overclaim() -> None:
    recipe = _recipe()
    schema = json.loads((ROOT / "schemas/synergy_build_recipe_v2.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(recipe, schema)
    assert verify_build_recipe_v2(recipe) == recipe
    assert recipe["service_spec_digests"] == {
        "content-cache": "5ace3018df97985f12d4c28da619b0598223eab34a710cac37d32edaf42ab1fd",
        "synergynet": "42c8b0df5e55345bd6b6636dfd4fd311035bd2bca91a9613814beeac08984fce",
    }
    assert recipe["build_toolchain"] == {"status": "NOT_FROZEN", "lock_digest": None}
    assert recipe["artifact_digest"] is None
    assert recipe["build_evidence_digest"] is None
    assert recipe["execution_authority"] == "NONE"


def test_fresh_hash_cannot_invent_frozen_toolchain() -> None:
    recipe = copy.deepcopy(_recipe())
    recipe["build_toolchain"] = {"status": "FROZEN", "lock_digest": "1" * 64}
    recipe["reproducibility_status"] = "REPRODUCIBLE"
    recipe["recipe_digest"] = recipe_digest(recipe)
    with pytest.raises(BuildRecipeV2Error):
        verify_build_recipe_v2(recipe)


def test_fresh_hash_cannot_invent_artifact_evidence() -> None:
    recipe = copy.deepcopy(_recipe())
    recipe["artifact_digest"] = "2" * 64
    recipe["build_evidence_digest"] = "3" * 64
    recipe["recipe_digest"] = recipe_digest(recipe)
    with pytest.raises(BuildRecipeV2Error):
        verify_build_recipe_v2(recipe)


def test_fresh_hash_cannot_change_service_spec_binding() -> None:
    recipe = copy.deepcopy(_recipe())
    recipe["service_spec_digests"]["synergynet"] = "4" * 64
    recipe["recipe_digest"] = recipe_digest(recipe)
    with pytest.raises(BuildRecipeV2Error):
        verify_build_recipe_v2(recipe)
