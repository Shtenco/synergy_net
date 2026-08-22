from __future__ import annotations

import hashlib
import json
import re
from typing import Any


class ServiceSpecV2Error(ValueError):
    pass


_SOURCE_COMMIT = "aa93e18bdeb84a8475419cde83f149c8381428cd"
_RUNTIME_MANIFEST_DIGEST = "d8be0a9023111df54c49704e9a0fea07d0fc5cac5a1a333d1c7bfac7a3708930"
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_EXPECTED = {
    "content-cache": {
        "kind": "CONTENT_CACHE",
        "required_capabilities": ["CONTENT_CACHE"],
        "entrypoint": "python -m synergynet.content_service_v2",
        "wire_protocol": "synergynet.content-wire/v2",
        "resource_limits": ["MAX_PAYLOAD_BYTES", "MAX_CONNECTIONS"],
        "spec_digest": "5ace3018df97985f12d4c28da619b0598223eab34a710cac37d32edaf42ab1fd",
    },
    "synergynet": {
        "kind": "SYNERGYNET",
        "required_capabilities": ["P2P_RELAY"],
        "entrypoint": "python -m synergynet.relay_service_v2",
        "wire_protocol": "synergynet.relay-wire/v2",
        "resource_limits": ["STATIC_PEER_DIRECTORY_MAX_256", "MAX_CONNECTIONS", "OUTBOUND_TIMEOUT"],
        "spec_digest": "42c8b0df5e55345bd6b6636dfd4fd311035bd2bca91a9613814beeac08984fce",
    },
}


def _canonical(value: Any) -> bytes:
    def check(item: Any) -> None:
        if item is None or isinstance(item, (str, bool)):
            return
        if isinstance(item, int) and not isinstance(item, bool):
            if abs(item) > 2**53 - 1:
                raise ServiceSpecV2Error("unsafe integer")
            return
        if isinstance(item, float):
            raise ServiceSpecV2Error("floating point values are forbidden")
        if isinstance(item, list):
            for child in item:
                check(child)
            return
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise ServiceSpecV2Error("object keys must be strings")
            for child in item.values():
                check(child)
            return
        raise ServiceSpecV2Error("unsupported value")

    check(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_digest(payload: dict[str, Any], self_field: str | None = None) -> str:
    body = dict(payload)
    if self_field is not None:
        body.pop(self_field, None)
    return hashlib.sha256(_canonical(body)).hexdigest()


def verify_runtime_source_manifest_v2(payload: dict[str, Any]) -> dict[str, Any]:
    required = {"schema", "generation", "source_status", "services", "build_artifact_digest", "build_evidence_digest", "execution_authority"}
    if not isinstance(payload, dict) or set(payload) != required:
        raise ServiceSpecV2Error("unexpected runtime-source shape")
    if payload["schema"] != "synergynet.runtime-source/v2":
        raise ServiceSpecV2Error("wrong runtime-source schema")
    if payload["generation"] != "BOUNDED_RUNTIME_SERVICES_V2_20260822":
        raise ServiceSpecV2Error("runtime generation drifted")
    if payload["source_status"] != "IMPLEMENTED_NOT_FROZEN":
        raise ServiceSpecV2Error("runtime source status drifted")
    if payload["build_artifact_digest"] is not None or payload["build_evidence_digest"] is not None:
        raise ServiceSpecV2Error("runtime source cannot claim build evidence")
    if payload["execution_authority"] != "NONE":
        raise ServiceSpecV2Error("runtime source cannot grant execution authority")
    services = payload["services"]
    if not isinstance(services, list) or [item.get("service_id") for item in services] != ["content-cache", "synergynet"]:
        raise ServiceSpecV2Error("runtime service set drifted")
    if canonical_digest(payload) != _RUNTIME_MANIFEST_DIGEST:
        raise ServiceSpecV2Error("runtime-source manifest digest mismatch")
    return payload


def spec_digest(payload: dict[str, Any]) -> str:
    return canonical_digest(payload, "spec_digest")


def verify_service_spec_v2(payload: dict[str, Any], runtime_manifest: dict[str, Any]) -> dict[str, Any]:
    verify_runtime_source_manifest_v2(runtime_manifest)
    required = {
        "schema", "service_id", "kind", "repository", "source_commit", "runtime_source_manifest_digest",
        "required_capabilities", "runtime_form", "entrypoint", "health_probe", "lifecycle_protocol",
        "wire_protocol", "resource_limits", "interface_status", "build_artifact_digest",
        "build_evidence_digest", "execution_authority", "spec_digest",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise ServiceSpecV2Error("unexpected service-spec shape")
    if payload["schema"] != "synergy.service-spec/v2":
        raise ServiceSpecV2Error("unexpected service-spec schema")
    service_id = payload["service_id"]
    if service_id not in _EXPECTED:
        raise ServiceSpecV2Error("unknown service id")
    expected = _EXPECTED[service_id]
    if payload["repository"] != "Shtenco/synergynet":
        raise ServiceSpecV2Error("wrong repository")
    if payload["source_commit"] != _SOURCE_COMMIT or not _HEX40.fullmatch(payload["source_commit"]):
        raise ServiceSpecV2Error("runtime source commit drifted")
    if payload["runtime_source_manifest_digest"] != _RUNTIME_MANIFEST_DIGEST:
        raise ServiceSpecV2Error("runtime manifest binding drifted")
    for field in ("kind", "required_capabilities", "entrypoint", "wire_protocol", "resource_limits"):
        if payload[field] != expected[field]:
            raise ServiceSpecV2Error(f"{field} drifted")
    if payload["runtime_form"] != "PYTHON_SERVICE":
        raise ServiceSpecV2Error("runtime form drifted")
    if payload["health_probe"] != "STATUS_EXPECT_READY":
        raise ServiceSpecV2Error("health probe drifted")
    if payload["lifecycle_protocol"] != "SIGINT_SIGTERM_GRACEFUL_SHUTDOWN":
        raise ServiceSpecV2Error("lifecycle protocol drifted")
    if payload["interface_status"] != "SERVICE_INTERFACE_IMPLEMENTED_SOURCE_ONLY":
        raise ServiceSpecV2Error("service interface status overclaims readiness")
    if payload["build_artifact_digest"] is not None or payload["build_evidence_digest"] is not None:
        raise ServiceSpecV2Error("ServiceSpec v2 cannot claim verified build artifacts")
    if payload["execution_authority"] != "NONE":
        raise ServiceSpecV2Error("ServiceSpec cannot grant execution authority")
    supplied = payload["spec_digest"]
    if not isinstance(supplied, str) or not _HEX64.fullmatch(supplied):
        raise ServiceSpecV2Error("invalid spec digest")
    recomputed = spec_digest(payload)
    if supplied != recomputed or recomputed != expected["spec_digest"]:
        raise ServiceSpecV2Error("service-spec digest mismatch")
    return payload


def verify_service_set_v2(specs: list[dict[str, Any]], runtime_manifest: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    if not isinstance(specs, list) or len(specs) != 2:
        raise ServiceSpecV2Error("service-spec set must contain exactly two services")
    verified = [verify_service_spec_v2(item, runtime_manifest) for item in specs]
    if [item["service_id"] for item in verified] != ["content-cache", "synergynet"]:
        raise ServiceSpecV2Error("service-spec set must be canonical and complete")
    return tuple(verified)
