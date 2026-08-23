from __future__ import annotations
import hashlib,json
from pathlib import Path
EXPECTED='0c58185ea0af4a8abc7ce215c0b7ff077cea9357e831b9d197ec730a34ed6c7e'

def canonical(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def verify(v):
 p=dict(v); claimed=p.pop('transport_binding_digest',None); actual=hashlib.sha256(canonical(p)).hexdigest()
 if claimed!=EXPECTED or actual!=EXPECTED: raise ValueError('transport binding digest mismatch')
 checks={
  'previous_transport_binding_digest':'3c8198e10863c52c0492ca422c404a1e05e6fd2f48f4c393587d9d87eee3855f',
  'transport_artifact_digest':'7f22e68d80a7df879af71ebccdb45f8edb10cae3698bf07faa7076ce76fd0ef7',
  'transport_location_evidence_v3_digest':'b1ca1c1f5849deac30a0aac14748c21b8a74a26776ba2134a448c9427a839220',
  'transport_runtime_spec_digest':'8c38cd130e3dd73723e3a3241d2df61bef218abdab2d16785ccec5b172fac4df',
  'wire_protocol':'synergynet.relay-wire/v3',
  'binding_scope':'OUTER_AUTOPILOT_NODE_ONLY',
  'nexus_network_access':'NONE',
 }
 for k,x in checks.items():
  if p.get(k)!=x: raise ValueError(f'{k} substitution')
 if p.get('auto_start') is not False: raise ValueError('auto-start escalation')
 for k in ('financial_authority','payment_authority','accounting_authority','blockchain_submission_authority','execution_authority'):
  if p.get(k)!='NONE': raise ValueError(f'authority escalation {k}')
 return actual
def load_default(root=None):
 root=root or Path(__file__).resolve().parents[2]; return json.loads((root/'bindings'/'synergy_autopilot_v5_ai_node_transport_v2.json').read_text())
