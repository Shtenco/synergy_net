from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest

from synergynet.build_recipe_v1 import BuildRecipeError, recipe_digest, verify_build_recipe_v1


ROOT = Path(__file__).resolve().parents[1]


def _recipe() -> dict:
    return json.loads((ROOT / "config/build_recipe_v1.json").read_text())


def test_canonical_recipe_verifies_and_schema_accepts() -> None:
    recipe = _recipe()
    assert verify_build_recipe_v1(recipe) == recipe
    schema = json.loads((ROOT / "schemas/synergy_build_recipe_v1.schema.json").read_text())
    jsonschema.validate(recipe, schema)


def test_fresh_hash_cannot_claim_reproducible_build() -> None:
    recipe = copy.deepcopy(_recipe())
    recipe["build_toolchain"] = {"status": "FROZEN", "lock_digest": "aa" * 32}
    recipe["reproducibility_status"] = "REPRODUCIBLE"
    recipe["artifact_digest"] = "bb" * 32
    recipe["recipe_digest"] = recipe_digest(recipe)
    with pytest.raises(BuildRecipeError):
        verify_build_recipe_v1(recipe)


def test_runtime_dependency_disclosure_is_empty_but_build_toolchain_is_not_frozen() -> None:
    recipe = _recipe()
    assert recipe["runtime_requirements"] == []
    assert recipe["build_toolchain"] == {"status": "NOT_FROZEN", "lock_digest": None}
    assert recipe["artifact_digest"] is None


def test_execution_authority_is_never_granted() -> None:
    recipe = copy.deepcopy(_recipe())
    recipe["execution_authority"] = "PROCESS_EXECUTION"
    recipe["recipe_digest"] = recipe_digest(recipe)
    with pytest.raises(BuildRecipeError):
        verify_build_recipe_v1(recipe)
