import copy, json, unittest
from pathlib import Path
from scripts.verify_location_evidence_v3 import verify

ROOT = Path(__file__).resolve().parents[1]

class LocationEvidenceV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.value = json.loads((ROOT/'evidence'/'synergynet_artifact_location_evidence_v3.json').read_text())

    def test_canonical(self):
        out = verify(copy.deepcopy(self.value))
        self.assertEqual(out['status'], 'PASS')
        self.assertEqual(out['artifact_size'], 12837)

    def test_reject_artifact_substitution(self):
        x = copy.deepcopy(self.value); x['artifact_digest'] = '0'*64
        with self.assertRaises(ValueError): verify(x)

    def test_reject_negative_evidence_erasure(self):
        x = copy.deepcopy(self.value); x['current_unavailability_negative_evidence_digest'] = '0'*64
        with self.assertRaises(ValueError): verify(x)

    def test_reject_authority_escalation(self):
        x = copy.deepcopy(self.value); x['execution_authority'] = 'ROOT'
        with self.assertRaises(ValueError): verify(x)

    def test_reject_locator_status_substitution(self):
        x = copy.deepcopy(self.value); x['location_status'] = 'TRUST_ME'
        with self.assertRaises(ValueError): verify(x)

if __name__ == '__main__': unittest.main()
