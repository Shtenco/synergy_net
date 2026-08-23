from __future__ import annotations
import base64, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence' / 'synergynet_artifact_location_evidence_v3.json'
CARRIER = ROOT / 'artifacts' / 'durable' / 'synergynet_runtime_v3_git_carrier'
EXPECTED = 'b1ca1c1f5849deac30a0aac14748c21b8a74a26776ba2134a448c9427a839220'


def canonical(v):
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def verify(value=None):
    v = json.loads(EVIDENCE.read_text()) if value is None else value
    claimed = v.get('location_evidence_digest')
    payload = dict(v); payload.pop('location_evidence_digest', None)
    actual = hashlib.sha256(canonical(payload)).hexdigest()
    if claimed != EXPECTED or actual != EXPECTED: raise ValueError('location evidence digest mismatch')
    if v['artifact_digest'] != '7f22e68d80a7df879af71ebccdb45f8edb10cae3698bf07faa7076ce76fd0ef7': raise ValueError('artifact substitution')
    if v['artifact_size'] != 12837: raise ValueError('size substitution')
    if v['provider'] != 'GITHUB_GIT_OBJECT_DATABASE': raise ValueError('provider substitution')
    if v['location_status'] != 'DURABLE_GITHUB_GIT_CARRIER_CURRENTLY_RESOLVABLE': raise ValueError('status substitution')
    if v['execution_authority'] != 'NONE': raise ValueError('authority escalation')
    if v['current_unavailability_negative_evidence_digest'] != '2529d725e426c5028daab7346d1c704d643ffd209d35ceace7f7330203a6353f': raise ValueError('negative evidence erasure')
    encoded = bytearray()
    for c in sorted(v['chunks'], key=lambda x: x['ordinal']):
        p = CARRIER / f"{c['ordinal']:03d}.b64part"
        raw = p.read_bytes()
        if len(raw) != c['encoded_length']: raise ValueError('chunk length mismatch')
        if hashlib.sha256(raw).hexdigest() != c['sha256']: raise ValueError('chunk sha mismatch')
        encoded.extend(raw)
    if len(encoded) != v['encoded_length']: raise ValueError('encoded length mismatch')
    artifact = base64.b64decode(bytes(encoded), validate=True)
    if len(artifact) != v['artifact_size']: raise ValueError('decoded size mismatch')
    if hashlib.sha256(artifact).hexdigest() != v['artifact_digest']: raise ValueError('decoded artifact sha mismatch')
    return {'status':'PASS','location_evidence_digest':actual,'artifact_digest':v['artifact_digest'],'artifact_size':len(artifact),'execution_authority':'NONE'}

if __name__ == '__main__':
    print(json.dumps(verify(), sort_keys=True))
