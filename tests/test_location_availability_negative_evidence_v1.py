import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from verify_location_availability_negative_evidence_v1 import LocationAvailabilityEvidenceError, verify  # noqa: E402


class LocationAvailabilityNegativeEvidenceV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = json.loads((ROOT / "evidence" / "synergynet_artifact_location_availability_negative_evidence_v1.json").read_text(encoding="utf-8"))

    def test_canonical_negative_evidence(self):
        self.assertEqual(
            verify(self.evidence),
            "2529d725e426c5028daab7346d1c704d643ffd209d35ceace7f7330203a6353f",
        )

    def reject(self, field, value):
        candidate = copy.deepcopy(self.evidence)
        candidate[field] = value
        candidate["negative_evidence_digest"] = "0" * 64
        with self.assertRaises(LocationAvailabilityEvidenceError):
            verify(candidate)

    def test_reject_artifact_substitution(self):
        self.reject("artifact_digest", "f" * 64)

    def test_reject_old_locator_substitution(self):
        self.reject("previous_provider_file_id", "different")

    def test_reject_false_resolved_status(self):
        self.reject("current_locator_status", "RESOLVED")

    def test_reject_probe_promotion(self):
        self.reject("probe_result", "FOUND")

    def test_reject_weakened_production_effect(self):
        self.reject("production_effect", "NONE")

    def test_reject_execution_authority(self):
        self.reject("execution_authority", "ROOT")


if __name__ == "__main__":
    unittest.main()
