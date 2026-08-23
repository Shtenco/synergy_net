import copy,unittest
from synergynet.autopilot_node_transport_v2 import load_default,verify
class TransportV2Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.v=load_default()
 def test_canonical(self): self.assertEqual(verify(copy.deepcopy(self.v)),'0c58185ea0af4a8abc7ce215c0b7ff077cea9357e831b9d197ec730a34ed6c7e')
 def test_reject_old_location(self):
  x=copy.deepcopy(self.v); x['transport_location_evidence_v3_digest']='c4102a8e668b79fc961a5f1767154154f4a600d320442770d74c7a006a5cee08'
  with self.assertRaises(ValueError): verify(x)
 def test_reject_nexus_egress(self):
  x=copy.deepcopy(self.v); x['nexus_network_access']='FULL'
  with self.assertRaises(ValueError): verify(x)
 def test_reject_authority(self):
  x=copy.deepcopy(self.v); x['execution_authority']='ROOT'
  with self.assertRaises(ValueError): verify(x)
if __name__=='__main__':unittest.main()
