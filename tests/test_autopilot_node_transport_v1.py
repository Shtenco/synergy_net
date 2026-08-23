from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from synergynet.autopilot_node_transport_v1 import TransportBindingError, verify_transport_binding

ROOT = Path(__file__).resolve().parents[1]
BINDING = ROOT / "bindings" / "synergy_autopilot_v5_ai_node_transport_v1.json"


def load():
    return json.loads(BINDING.read_text())


def fresh_hash(obj: dict):
    body = dict(obj)
    body.pop("transport_binding_digest", None)
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    obj["transport_binding_digest"] = hashlib.sha256(raw).hexdigest()
    return obj


def test_canonical_transport_binding_passes():
    assert verify_transport_binding(load())["nexus_network_access"] == "NONE"


@pytest.mark.parametrize(
    "field,value",
    [
        ("node_source_commit", "0" * 40),
        ("node_integration_manifest_digest", "0" * 64),
        ("transport_artifact_digest", "0" * 64),
        ("transport_location_evidence_digest", "0" * 64),
        ("transport_runtime_spec_digest", "0" * 64),
        ("wire_protocol", "arbitrary-wire/v9"),
        ("binding_scope", "NEXUS_DIRECT_NETWORK"),
        ("materialization_status", "RUNNING"),
        ("network_address_authority", "ARBITRARY_REMOTE_DESTINATION"),
        ("nexus_network_access", "FULL_EGRESS"),
        ("remote_filesystem_path_authority", "REMOTE_RW"),
        ("auto_start", True),
        ("financial_authority", "TREASURY"),
        ("payment_authority", "METAPAY"),
        ("blockchain_submission_authority", "SIGN_AND_SUBMIT"),
        ("execution_authority", "ROOT"),
    ],
)
def test_fresh_hash_cannot_escalate_transport(field, value):
    binding = copy.deepcopy(load())
    binding[field] = value
    fresh_hash(binding)
    with pytest.raises(TransportBindingError):
        verify_transport_binding(binding)
