from __future__ import annotations

import hashlib
import json
import re
from typing import Any


class BuildReadinessError(ValueError):
    pass


_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_EXPECTED_DIGEST = "a41c5bf58ff85ee1b4efafc3975ca975f2ca1c59a020aca056e7351e71659a0e"
_EXPECTED_ARTIFACTS = [
    {"path":"src/synergynet/lab.py","git_blob_sha":"ca1aec269e0e9772f4cd05d354b560dab346a333","role":"CHUNKING_AND_CONTENT_IDENTITY"},
    {"path":"src/synergynet/persistent_lab_v3.py","git_blob_sha":"e204e066adbdf08306301ea9c4a86ea35ad07995","role":"PERSISTENT_TRANSFER_COMPONENT"},
    {"path":"src/synergynet/storage_v3.py","git_blob_sha":"067a5cbd963a491bc430f0805a510905a9143138","role":"DURABLE_CONTENT_STORE_AND_CODEC_ABI"},
    {"path":"src/synergynet/tcp_transport.py","git_blob_sha":"c3097a94bcc7e979584124bfe6bb1d2adf79fb98","role":"IN_PROCESS_TCP_TRANSPORT"},
]


def _canonical(value: Any) -> bytes:
    if isinstance(value, float):
        raise BuildReadinessError("floats forbidden")
    if isinstance(value, int) and not isinstance(value, bool) and abs(value) > 2**53 - 1:
        raise BuildReadinessError("unsafe integer")
    if isinstance(value, list):
        for item in value:
            _canonical(item)
    elif isinstance(value, dict):
        if any(not isinstance(k, str) for k in value):
            raise BuildReadinessError("keys must be strings")
        for item in value.values():
            _canonical(item)
    elif value is not None and not isinstance(value, (str, bool, int)):
        raise BuildReadinessError("unsupported value")
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def readiness_digest(payload: dict[str, Any]) -> str:
    body = dict(payload)
    body.pop("readiness_digest", None)
    return hashlib.sha256(_canonical(body)).hexdigest()


def verify_research_transport_build_readiness(payload: dict[str, Any]) -> dict[str, Any]:
    expected = {"schema","component_id","source_repository","source_commit","source_ref","source_artifacts","artifact_kind","service_entrypoint","python_versions","dependency_lock_status","service_readiness","build_artifact_digest","execution_authority","readiness_digest"}
    if not isinstance(payload, dict) or set(payload) != expected:
        raise BuildReadinessError("unexpected build-readiness shape")
    if payload["schema"] != "synergynet.build-readiness/v1" or payload["component_id"] != "SYNERGYNET_RESEARCH_TRANSPORT_CACHE_V1":
        raise BuildReadinessError("unexpected build-readiness identity")
    if payload["source_repository"] != "Shtenco/synergynet" or payload["source_commit"] != "a8fde01c19420dbe63ca30e1da3b009c0c10064d":
        raise BuildReadinessError("source identity drifted")
    if not _HEX40.fullmatch(payload["source_commit"]):
        raise BuildReadinessError("source commit must be lowercase git sha")
    if payload["source_ref"] != "feat/persistent-store-codec-v3-20260821":
        raise BuildReadinessError("source ref drifted")
    if payload["source_artifacts"] != _EXPECTED_ARTIFACTS:
        raise BuildReadinessError("source artifact identity drifted")
    for item in payload["source_artifacts"]:
        if not _HEX40.fullmatch(item["git_blob_sha"]):
            raise BuildReadinessError("git blob sha invalid")
    if payload["artifact_kind"] != "PYTHON_LIBRARY_WITH_IN_PROCESS_SERVER" or payload["service_entrypoint"] is not None:
        raise BuildReadinessError("v1 must remain non-daemon library/server components")
    if payload["python_versions"] != ["3.11", "3.12"]:
        raise BuildReadinessError("python version contract drifted")
    if payload["dependency_lock_status"] != "STDLIB_ONLY":
        raise BuildReadinessError("unexpected dependency lock status")
    if payload["service_readiness"] != "IN_PROCESS_SERVER_NOT_DAEMON_ENTRYPOINT":
        raise BuildReadinessError("service readiness overclaims deployability")
    if payload["build_artifact_digest"] is not None:
        raise BuildReadinessError("unbuilt component cannot claim artifact digest")
    if payload["execution_authority"] != "NONE":
        raise BuildReadinessError("build-readiness artifact cannot execute")
    digest = payload["readiness_digest"]
    if not isinstance(digest, str) or not _HEX64.fullmatch(digest):
        raise BuildReadinessError("readiness digest invalid")
    if readiness_digest(payload) != digest or digest != _EXPECTED_DIGEST:
        raise BuildReadinessError("build-readiness digest mismatch")
    return payload
