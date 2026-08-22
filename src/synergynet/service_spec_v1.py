from __future__ import annotations

import hashlib
import json
import re
from typing import Any


class ServiceSpecError(ValueError):
    pass


_SOURCE_COMMIT = "a8fde01c19420dbe63ca30e1da3b009c0c10064d"
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_EXPECTED = {
    "content-cache": {
        "kind": "CONTENT_CACHE",
        "required_capabilities": ["CONTENT_CACHE"],
        "spec_digest": "9ce8c608edd65f7c888809c49109fa3a4cecffe58d9434d6c9bf317150e7ee96",
    },
    "synergynet": {
        "kind": "SYNERGYNET",
        "required_capabilities": ["P2P_RELAY"],
        "spec_digest": "e74ae38f45d313b301b4f7b4c408485780d1c1f6ebdb68cbd7c0bd3ed13b391c",
    },
}


def _canonical(value: Any) -> bytes:
    def check(item: Any) -> None:
        if item is None or isinstance(item, (str, bool)):
            return
        if isinstance(item, int) and not isinstance(item, bool):
            if abs(item) > 2**53 - 1:
                raise ServiceSpecError("unsafe integer")
            return
        if isinstance(item, float):
            raise ServiceSpecError("floating point values are forbidden")
        if isinstance(item, list):
            for child in item:
                check(child)
            return
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise ServiceSpecError("object keys must be strings")
            for child in item.values():
                check(child)
            return
        raise ServiceSpecError("unsupported service-spec value")

    check(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def spec_digest(payload: dict[str, Any]) -> str:
    body = dict(payload)
    body.pop("spec_digest", None)
    return hashlib.sha256(_canonical(body)).hexdigest()


def verify_service_spec_v1(payload: dict[str, Any]) -> dict[str, Any]:
    required = {
        "schema", "service_id", "kind", "repository", "source_commit",
        "required_capabilities", "runtime_form", "entrypoint", "health_probe",
        "lifecycle_protocol", "wire_protocol", "readiness_status",
        "execution_authority", "spec_digest",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise ServiceSpecError("unexpected service-spec shape")
    if payload["schema"] != "synergy.service-spec/v1":
        raise ServiceSpecError("unexpected service-spec schema")
    service_id = payload["service_id"]
    if service_id not in _EXPECTED:
        raise ServiceSpecError("unknown SynergyNet service id")
    expected = _EXPECTED[service_id]
    if payload["kind"] != expected["kind"]:
        raise ServiceSpecError("service kind drifted")
    if payload["repository"] != "Shtenco/synergynet":
        raise ServiceSpecError("wrong repository")
    if payload["source_commit"] != _SOURCE_COMMIT or not _HEX40.fullmatch(payload["source_commit"]):
        raise ServiceSpecError("source commit drifted")
    if payload["required_capabilities"] != expected["required_capabilities"]:
        raise ServiceSpecError("required capabilities drifted")
    if payload["runtime_form"] != "PYTHON_LIBRARY_ONLY":
        raise ServiceSpecError("current generation is library-only")
    for field in ("entrypoint", "health_probe", "lifecycle_protocol", "wire_protocol"):
        if payload[field] is not None:
            raise ServiceSpecError(f"v1 cannot claim implemented {field}")
    if payload["readiness_status"] != "SERVICE_INTERFACE_NOT_IMPLEMENTED":
        raise ServiceSpecError("v1 cannot claim service readiness")
    if payload["execution_authority"] != "NONE":
        raise ServiceSpecError("service specification cannot grant execution authority")
    supplied = payload["spec_digest"]
    if not isinstance(supplied, str) or not _HEX64.fullmatch(supplied):
        raise ServiceSpecError("invalid spec digest")
    recomputed = spec_digest(payload)
    if supplied != recomputed or recomputed != expected["spec_digest"]:
        raise ServiceSpecError("SynergyNet service-spec digest mismatch")
    return payload


def verify_service_set_v1(specs: list[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    if not isinstance(specs, list) or len(specs) != len(_EXPECTED):
        raise ServiceSpecError("service-spec set must contain exactly two services")
    verified = [verify_service_spec_v1(item) for item in specs]
    if [item["service_id"] for item in verified] != sorted(_EXPECTED):
        raise ServiceSpecError("service-spec set must be sorted and complete")
    return tuple(verified)
