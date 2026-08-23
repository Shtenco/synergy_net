from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

EXPECTED_DIGEST = "2529d725e426c5028daab7346d1c704d643ffd209d35ceace7f7330203a6353f"
EXPECTED_ARTIFACT = "7f22e68d80a7df879af71ebccdb45f8edb10cae3698bf07faa7076ce76fd0ef7"
EXPECTED_PREVIOUS_LOCATION = "c4102a8e668b79fc961a5f1767154154f4a600d320442770d74c7a006a5cee08"
EXPECTED_OLD_FILE_ID = "1zuB8rjKO0HHIZmvUEGZnAbnkKGNN59qp"


class LocationAvailabilityEvidenceError(ValueError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def verify(value: dict[str, Any]) -> str:
    if not isinstance(value, dict):
        raise LocationAvailabilityEvidenceError("evidence must be object")
    payload = dict(value)
    claimed = payload.pop("negative_evidence_digest", None)
    actual = hashlib.sha256(canonical(payload)).hexdigest()
    if claimed != EXPECTED_DIGEST or actual != EXPECTED_DIGEST:
        raise LocationAvailabilityEvidenceError("negative evidence digest mismatch")
    if payload.get("artifact_digest") != EXPECTED_ARTIFACT:
        raise LocationAvailabilityEvidenceError("artifact identity substitution")
    if payload.get("previous_location_evidence_digest") != EXPECTED_PREVIOUS_LOCATION:
        raise LocationAvailabilityEvidenceError("previous location evidence substitution")
    if payload.get("previous_provider_file_id") != EXPECTED_OLD_FILE_ID:
        raise LocationAvailabilityEvidenceError("old provider file id substitution")
    if payload.get("probe_result") != "NOT_FOUND_CURRENT_CONNECTED_DRIVE":
        raise LocationAvailabilityEvidenceError("probe result promotion")
    if payload.get("current_locator_status") != "UNRESOLVABLE_CURRENT_CONNECTION":
        raise LocationAvailabilityEvidenceError("locator status promotion")
    if payload.get("artifact_identity_status") != "UNCHANGED":
        raise LocationAvailabilityEvidenceError("artifact identity incorrectly changed")
    if payload.get("production_effect") != "NEW_DURABLE_LOCATOR_AND_FRESH_SHA_SIZE_VERIFICATION_REQUIRED":
        raise LocationAvailabilityEvidenceError("production effect weakened")
    if payload.get("execution_authority") != "NONE":
        raise LocationAvailabilityEvidenceError("execution authority escalation")
    return actual


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    path = root / "evidence" / "synergynet_artifact_location_availability_negative_evidence_v1.json"
    digest = verify(json.loads(path.read_text(encoding="utf-8")))
    print(json.dumps({"status": "PASS", "negative_evidence_digest": digest}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
