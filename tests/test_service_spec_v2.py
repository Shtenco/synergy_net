from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest

from synergynet.service_spec_v2 import (
    ServiceSpecV2Error,
    spec_digest,
    verify_service_set_v2,
    verify_service_spec_v2,
)


ROOT = Path(__file__).resolve().parents[1]


def _runtime() -> dict:
    return json.loads((ROOT / "config/runtime_services_v2.json").read_text(encoding="utf-8"))


def _spec(name: str) -> dict:
    return json.loads((ROOT / f"config/service_specs_v2/{name}.json").read_text(encoding="utf-8"))


def test_service_specs_v2_bind_real_runtime_without_build_overclaim() -> None:
    runtime = _runtime()
    content = _spec("content-cache")
    relay = _spec("synergynet")
    schema = json.loads((ROOT / "schemas/synergy_service_spec_v2.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(content, schema)
    jsonschema.validate(relay, schema)
    assert verify_service_spec_v2(content, runtime) == content
    assert verify_service_spec_v2(relay, runtime) == relay
    assert verify_service_set_v2([content, relay], runtime) == (content, relay)
    for item in (content, relay):
        assert item["runtime_form"] == "PYTHON_SERVICE"
        assert item["interface_status"] == "SERVICE_INTERFACE_IMPLEMENTED_SOURCE_ONLY"
        assert item["build_artifact_digest"] is None
        assert item["build_evidence_digest"] is None
        assert item["execution_authority"] == "NONE"


def test_fresh_hash_cannot_promote_source_interface_to_build_verified() -> None:
    runtime = _runtime()
    spec = copy.deepcopy(_spec("content-cache"))
    spec["interface_status"] = "RUNNABLE"
    spec["build_artifact_digest"] = "1" * 64
    spec["build_evidence_digest"] = "2" * 64
    spec["spec_digest"] = spec_digest(spec)
    with pytest.raises(ServiceSpecV2Error):
        verify_service_spec_v2(spec, runtime)


def test_fresh_hash_cannot_move_spec_to_different_source_commit() -> None:
    runtime = _runtime()
    spec = copy.deepcopy(_spec("synergynet"))
    spec["source_commit"] = "0" * 40
    spec["spec_digest"] = spec_digest(spec)
    with pytest.raises(ServiceSpecV2Error):
        verify_service_spec_v2(spec, runtime)


def test_runtime_manifest_tamper_is_rejected_even_if_service_spec_is_unchanged() -> None:
    runtime = copy.deepcopy(_runtime())
    runtime["services"][0]["entrypoint"] = "python -m synergynet.fake"
    with pytest.raises(ServiceSpecV2Error):
        verify_service_spec_v2(_spec("content-cache"), runtime)


def test_service_spec_cannot_grant_execution_authority() -> None:
    runtime = _runtime()
    spec = copy.deepcopy(_spec("synergynet"))
    spec["execution_authority"] = "PROCESS_EXECUTION"
    spec["spec_digest"] = spec_digest(spec)
    with pytest.raises(ServiceSpecV2Error):
        verify_service_spec_v2(spec, runtime)
