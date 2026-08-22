from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest

from synergynet.service_spec_v1 import ServiceSpecError, spec_digest, verify_service_set_v1, verify_service_spec_v1


ROOT = Path(__file__).resolve().parents[1]


def _spec(name: str) -> dict:
    return json.loads((ROOT / f"config/service_specs_v1/{name}.json").read_text())


def test_current_synergynet_specs_are_valid_but_not_runnable() -> None:
    content = _spec("content-cache")
    transport = _spec("synergynet")
    assert verify_service_spec_v1(content) == content
    assert verify_service_spec_v1(transport) == transport
    assert verify_service_set_v1([content, transport]) == (content, transport)
    schema = json.loads((ROOT / "schemas/synergy_service_spec_v1.schema.json").read_text())
    jsonschema.validate(content, schema)
    jsonschema.validate(transport, schema)
    assert all(item["readiness_status"] == "SERVICE_INTERFACE_NOT_IMPLEMENTED" for item in (content, transport))


def test_fresh_hash_cannot_invent_transport_entrypoint() -> None:
    spec = copy.deepcopy(_spec("synergynet"))
    spec["runtime_form"] = "PYTHON_SERVICE"
    spec["entrypoint"] = "synergynet.server:main"
    spec["health_probe"] = "HEALTH_V1"
    spec["lifecycle_protocol"] = "META_OS_SERVICE_V1"
    spec["wire_protocol"] = "SYNERGYNET_TCP_V1"
    spec["readiness_status"] = "RUNNABLE"
    spec["spec_digest"] = spec_digest(spec)
    with pytest.raises(ServiceSpecError):
        verify_service_spec_v1(spec)


def test_fresh_hash_cannot_invent_content_cache_entrypoint() -> None:
    spec = copy.deepcopy(_spec("content-cache"))
    spec["runtime_form"] = "PYTHON_SERVICE"
    spec["entrypoint"] = "synergynet.cache:main"
    spec["health_probe"] = "CACHE_HEALTH_V1"
    spec["lifecycle_protocol"] = "META_OS_SERVICE_V1"
    spec["wire_protocol"] = "CONTENT_CACHE_RPC_V1"
    spec["readiness_status"] = "RUNNABLE"
    spec["spec_digest"] = spec_digest(spec)
    with pytest.raises(ServiceSpecError):
        verify_service_spec_v1(spec)


def test_service_set_must_be_complete_and_sorted() -> None:
    content = _spec("content-cache")
    transport = _spec("synergynet")
    with pytest.raises(ServiceSpecError):
        verify_service_set_v1([transport, content])
    with pytest.raises(ServiceSpecError):
        verify_service_set_v1([transport])
