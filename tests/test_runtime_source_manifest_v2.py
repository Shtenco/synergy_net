from __future__ import annotations

import json
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_source_manifest_v2_is_non_authorizing_and_complete() -> None:
    payload = json.loads((ROOT / "config/runtime_services_v2.json").read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "schemas/synergynet_runtime_source_v2.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(payload, schema)
    assert payload["source_status"] == "IMPLEMENTED_NOT_FROZEN"
    assert payload["build_artifact_digest"] is None
    assert payload["build_evidence_digest"] is None
    assert payload["execution_authority"] == "NONE"
    services = {service["service_id"]: service for service in payload["services"]}
    assert set(services) == {"content-cache", "synergynet"}
    assert services["content-cache"]["required_capabilities"] == ["CONTENT_CACHE"]
    assert services["synergynet"]["required_capabilities"] == ["P2P_RELAY"]
    assert all(service["health_operation"] == "STATUS" for service in services.values())
    assert all(service["ready_value"] == "READY" for service in services.values())
    assert all(service["execution_authority"] == "NONE" for service in services.values())
