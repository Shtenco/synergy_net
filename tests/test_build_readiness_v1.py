import json
from pathlib import Path

import pytest

from synergynet.build_readiness_v1 import BuildReadinessError, readiness_digest, verify_research_transport_build_readiness

ROOT = Path(__file__).resolve().parents[1]


def load_payload():
    return json.loads((ROOT / "config/research_transport_build_readiness_v1.json").read_text(encoding="utf-8"))


def test_canonical_readiness_freezes_transport_cache_sources_without_daemon_claim():
    payload = load_payload()
    verify_research_transport_build_readiness(payload)
    assert payload["readiness_digest"] == "a41c5bf58ff85ee1b4efafc3975ca975f2ca1c59a020aca056e7351e71659a0e"
    assert payload["dependency_lock_status"] == "STDLIB_ONLY"
    assert payload["service_entrypoint"] is None
    assert payload["service_readiness"] == "IN_PROCESS_SERVER_NOT_DAEMON_ENTRYPOINT"


def test_fresh_hash_cannot_invent_daemon_entrypoint():
    payload = load_payload()
    payload["service_entrypoint"] = "synergynet.daemon:main"
    payload["readiness_digest"] = readiness_digest(payload)
    with pytest.raises(BuildReadinessError, match="non-daemon"):
        verify_research_transport_build_readiness(payload)


def test_fresh_hash_cannot_claim_built_artifact():
    payload = load_payload()
    payload["build_artifact_digest"] = "f" * 64
    payload["readiness_digest"] = readiness_digest(payload)
    with pytest.raises(BuildReadinessError, match="cannot claim artifact"):
        verify_research_transport_build_readiness(payload)


def test_source_blob_tamper_is_rejected_even_with_new_outer_digest():
    payload = load_payload()
    payload["source_artifacts"][2]["git_blob_sha"] = "0" * 40
    payload["readiness_digest"] = readiness_digest(payload)
    with pytest.raises(BuildReadinessError, match="source artifact identity drifted"):
        verify_research_transport_build_readiness(payload)
