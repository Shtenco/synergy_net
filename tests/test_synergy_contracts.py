from datetime import datetime,timezone
import importlib.util
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/"runtime"/"synergy_contracts.py"
spec=importlib.util.spec_from_file_location("synergy_contracts",PATH)
mod=importlib.util.module_from_spec(spec);assert spec and spec.loader;spec.loader.exec_module(mod)

def test_archive_evidence_becomes_content_addressed_transport_input():
    p=mod.consume_archive_evidence({"round_trip_verified":True,"source_sha256":"1"*64,"archive_sha256":"2"*64,"codec_id":"c","archive_bytes":10})
    assert p["content_id"]=="1"*64 and p["transport_authority"] is False

def test_transport_evidence_requires_authenticated_delivery():
    with pytest.raises(ValueError):
        mod.transport_evidence_payload(session_id="s",sender_peer="a",receiver_peer="b",content=b"x",
          delivered_at=datetime.now(timezone.utc),transport_profile="tcp",authenticated=False,route=["a","b"],bytes_on_wire=1,latency_ms=1)

def test_transport_evidence_hashes_delivered_content():
    p=mod.transport_evidence_payload(session_id="s",sender_peer="a",receiver_peer="b",content=b"x",
      delivered_at=datetime.now(timezone.utc),transport_profile="tcp",authenticated=True,route=["a","b"],bytes_on_wire=17,latency_ms=1)
    assert len(p["content_sha256"])==64
