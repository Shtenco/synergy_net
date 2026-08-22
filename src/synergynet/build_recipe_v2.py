from __future__ import annotations

import hashlib
import json
import re
from typing import Any


class BuildRecipeV2Error(ValueError):
    pass


_SOURCE_COMMIT = "d2f5256825f4ee3e878476556a427b3172cf5d31"
_RECIPE_DIGEST = "9760d89fbc1de9553052db07feee7819bedee98aa0688efcabae7415aa143565"
_SERVICE_SPECS = {
    "content-cache": "5ace3018df97985f12d4c28da619b0598223eab34a710cac37d32edaf42ab1fd",
    "synergynet": "42c8b0df5e55345bd6b6636dfd4fd311035bd2bca91a9613814beeac08984fce",
}
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _canonical(value: Any) -> bytes:
    def check(item: Any) -> None:
        if item is None or isinstance(item, (str, bool)):
            return
        if isinstance(item, int) and not isinstance(item, bool):
            if abs(item) > 2**53 - 1:
                raise BuildRecipeV2Error("unsafe integer")
            return
        if isinstance(item, float):
            raise BuildRecipeV2Error("floating point values are forbidden")
        if isinstance(item, list):
            for child in item:
                check(child)
            return
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise BuildRecipeV2Error("object keys must be strings")
            for child in item.values():
                check(child)
            return
        raise BuildRecipeV2Error("unsupported build-recipe value")

    check(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def recipe_digest(payload: dict[str, Any]) -> str:
    body = dict(payload)
    body.pop("recipe_digest", None)
    return hashlib.sha256(_canonical(body)).hexdigest()


def verify_build_recipe_v2(payload: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "schema", "recipe_id", "repository", "source_commit", "source_role", "service_spec_digests",
        "artifact_kind", "package_name", "package_version", "python_requires", "build_backend",
        "build_system_requirements", "runtime_requirements", "build_toolchain", "reproducibility_status",
        "artifact_digest", "build_evidence_digest", "execution_authority", "recipe_digest",
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        raise BuildRecipeV2Error("unexpected build-recipe shape")
    if payload["schema"] != "synergy.build-recipe/v2":
        raise BuildRecipeV2Error("unexpected build recipe schema")
    if payload["recipe_id"] != "SYNERGYNET_RUNTIME_SERVICES_SOURCE_CANDIDATE_20260822":
        raise BuildRecipeV2Error("unexpected recipe id")
    if payload["repository"] != "Shtenco/synergynet":
        raise BuildRecipeV2Error("wrong repository")
    if payload["source_commit"] != _SOURCE_COMMIT or not _HEX40.fullmatch(payload["source_commit"]):
        raise BuildRecipeV2Error("source commit drifted")
    if payload["source_role"] != "SYNERGYNET_RUNTIME_SERVICES_V2":
        raise BuildRecipeV2Error("source role drifted")
    if payload["service_spec_digests"] != _SERVICE_SPECS:
        raise BuildRecipeV2Error("service spec bindings drifted")
    if payload["artifact_kind"] != "PYTHON_WHEEL":
        raise BuildRecipeV2Error("unexpected artifact kind")
    if payload["package_name"] != "synergynet" or payload["package_version"] != "0.1.0":
        raise BuildRecipeV2Error("package identity drifted")
    if payload["python_requires"] != ">=3.11":
        raise BuildRecipeV2Error("python requirement drifted")
    if payload["build_backend"] != "setuptools.build_meta":
        raise BuildRecipeV2Error("build backend drifted")
    if payload["build_system_requirements"] != ["setuptools>=68"]:
        raise BuildRecipeV2Error("build-system requirements drifted")
    if payload["runtime_requirements"] != []:
        raise BuildRecipeV2Error("unexpected runtime dependency disclosure")
    if payload["build_toolchain"] != {"status": "NOT_FROZEN", "lock_digest": None}:
        raise BuildRecipeV2Error("toolchain must remain explicitly unfrozen")
    if payload["reproducibility_status"] != "NOT_REPRODUCIBLE_TOOLCHAIN_NOT_FROZEN":
        raise BuildRecipeV2Error("recipe cannot claim reproducibility")
    if payload["artifact_digest"] is not None or payload["build_evidence_digest"] is not None:
        raise BuildRecipeV2Error("recipe cannot claim build output/evidence")
    if payload["execution_authority"] != "NONE":
        raise BuildRecipeV2Error("build recipe cannot grant execution authority")
    supplied = payload["recipe_digest"]
    if not isinstance(supplied, str) or not _HEX64.fullmatch(supplied):
        raise BuildRecipeV2Error("invalid recipe digest")
    recomputed = recipe_digest(payload)
    if supplied != recomputed or recomputed != _RECIPE_DIGEST:
        raise BuildRecipeV2Error("recipe digest mismatch")
    return payload
