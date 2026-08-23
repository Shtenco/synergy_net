from __future__ import annotations

import hashlib
import json
from typing import Any

BINDING_DIGEST = "3c8198e10863c52c0492ca422c404a1e05e6fd2f48f4c393587d9d87eee3855f"
NODE_COMMIT = "c39f6f0ee0e37c08366a63ec160c580b9ae954ba"
NODE_ROOT = "a793250aaa2299fdaf1661e985423c2b62687a19395ceabcc7bb63c005defe54"
ARTIFACT = "7f22e68d80a7df879af71ebccdb45f8edb10cae3698bf07faa7076ce76fd0ef7"
LOCATION = "c4102a8e668b79fc961a5f1767154154f4a600d320442770d74c7a006a5cee08"
RUNTIME = "8c38cd130e3dd73723e3a3241d2df61bef218abdab2d16785ccec5b172fac4df"

class TransportBindingError(ValueError):
    pass


def canonical_digest(value: dict[str, Any], field: str = "transport_binding_digest") -> str:
    body = dict(value)
    body.pop(field, None)
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def verify_transport_binding(binding: dict[str, Any]) -> dict[str, Any]:
    if binding.get("schema") != "synergynet.node-transport-binding/v1":
        raise TransportBindingError("schema")
    if canonical_digest(binding) != binding.get("transport_binding_digest"):
        raise TransportBindingError("self digest")
    if binding.get("transport_binding_digest") != BINDING_DIGEST:
        raise TransportBindingError("unexpected generation")
    if binding.get("node_source_commit") != NODE_COMMIT or binding.get("node_integration_manifest_digest") != NODE_ROOT:
        raise TransportBindingError("node substitution")
    if binding.get("transport_artifact_digest") != ARTIFACT:
        raise TransportBindingError("transport artifact substitution")
    if binding.get("transport_location_evidence_digest") != LOCATION:
        raise TransportBindingError("locator substitution")
    if binding.get("transport_runtime_spec_digest") != RUNTIME:
        raise TransportBindingError("runtime substitution")
    if binding.get("wire_protocol") != "synergynet.relay-wire/v3":
        raise TransportBindingError("wire protocol drift")
    if binding.get("binding_scope") != "OUTER_AUTOPILOT_NODE_ONLY":
        raise TransportBindingError("scope drift")
    if binding.get("materialization_status") != "PROTOCOL_BOUND_HOST_ADDRESS_NOT_MATERIALIZED":
        raise TransportBindingError("materialization overclaim")
    if binding.get("network_address_authority") != "STATIC_OPERATOR_LOCAL_ALLOWLIST_ONLY":
        raise TransportBindingError("network authority drift")
    if binding.get("nexus_network_access") != "NONE":
        raise TransportBindingError("NEXUS network escalation")
    if binding.get("remote_filesystem_path_authority") != "NONE":
        raise TransportBindingError("remote path authority escalation")
    if binding.get("auto_start") is not False:
        raise TransportBindingError("auto start")
    for field in ("financial_authority", "payment_authority", "accounting_authority", "blockchain_submission_authority", "execution_authority"):
        if binding.get(field) != "NONE":
            raise TransportBindingError(f"authority escalation: {field}")
    return binding
