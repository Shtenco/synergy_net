from __future__ import annotations
from datetime import datetime
from hashlib import sha256
from typing import Any


TRANSPORT_CONTRACT_ID="synergy.transport.evidence/v1"
ARCHIVE_CONTRACT_ID="synergy.archive.evidence/v1"
AUTHORITY="p2p_transport"


def consume_archive_evidence(payload: dict[str,Any]) -> dict[str,Any]:
    if payload.get("round_trip_verified") is not True:
        raise ValueError("archive must be exact-round-trip verified")
    source=str(payload.get("source_sha256","")).lower()
    archive=str(payload.get("archive_sha256","")).lower()
    for name,d in (("source_sha256",source),("archive_sha256",archive)):
        if len(d)!=64 or any(c not in "0123456789abcdef" for c in d):
            raise ValueError(f"invalid {name}")
    return {
        "content_id":source,
        "archive_id":archive,
        "codec_id":str(payload["codec_id"]),
        "archive_bytes":int(payload["archive_bytes"]),
        "transport_authority":False,
    }


def transport_evidence_payload(
    *,session_id:str,sender_peer:str,receiver_peer:str,content:bytes,
    delivered_at:datetime,transport_profile:str,authenticated:bool,
    route:list[str],bytes_on_wire:int,latency_ms:float,
) -> dict[str,Any]:
    if not session_id or not sender_peer or not receiver_peer or not content:
        raise ValueError("session/peers/content required")
    if not authenticated:
        raise ValueError("transport evidence requires authenticated delivery")
    if bytes_on_wire < len(content) or latency_ms < 0:
        raise ValueError("invalid transport measurements")
    if not route or route[0]!=sender_peer or route[-1]!=receiver_peer:
        raise ValueError("route endpoints do not match peers")
    return {
        "session_id":session_id,"sender_peer":sender_peer,"receiver_peer":receiver_peer,
        "content_sha256":sha256(content).hexdigest(),
        "delivered_at":delivered_at.isoformat(),
        "transport_profile":transport_profile,
        "authenticated":True,"route":list(route),
        "bytes_on_wire":int(bytes_on_wire),"latency_ms":float(latency_ms),
    }
