from __future__ import annotations

import hashlib

import pytest

from synergynet.persistent_service_v1 import PersistentContentClient, PersistentContentServer
from synergynet.static_relay_v1 import (
    PeerEndpoint,
    RelayInvariantError,
    StaticChunkRelay,
    StaticPeerDirectory,
    verify_response,
)


def _request(digest: str, *, source: str = "peer-a", destination: str = "peer-b") -> dict:
    return {
        "schema": "synergynet.relay-request/v1",
        "request_id": "relay-001",
        "operation": "RELAY_CHUNK",
        "source_peer_id": source,
        "destination_peer_id": destination,
        "chunk_digest": digest,
    }


def test_relay_moves_exact_chunk_between_allowlisted_peers(tmp_path) -> None:
    raw = b"synergy-relay-content" * 100
    with PersistentContentServer(store_root=tmp_path / "a") as source, PersistentContentServer(store_root=tmp_path / "b") as destination:
        source_client = PersistentContentClient(source.address)
        destination_client = PersistentContentClient(destination.address)
        digest = source_client.put(raw, codec_id="zlib-9")
        directory = StaticPeerDirectory((
            PeerEndpoint("peer-a", *source.address),
            PeerEndpoint("peer-b", *destination.address),
        ))
        relay = StaticChunkRelay(directory)
        request = _request(digest)
        response = relay.relay_chunk(request)
        assert response["status"] == "RELAYED"
        assert response["relay_scope"] == "STATIC_ALLOWLISTED_PEERS_ONLY"
        assert response["raw_bytes"] == len(raw)
        assert response["execution_authority"] == "NONE"
        assert destination_client.get_raw(digest) == raw
        assert verify_response(response, request, directory) == response


def test_unknown_peer_is_blocked_before_network_resolution(tmp_path) -> None:
    digest = hashlib.sha256(b"x").hexdigest()
    with PersistentContentServer(store_root=tmp_path / "a") as source:
        directory = StaticPeerDirectory((PeerEndpoint("peer-a", *source.address),))
        relay = StaticChunkRelay(directory)
        with pytest.raises(RelayInvariantError, match="allowlisted"):
            relay.relay_chunk(_request(digest, destination="untrusted-peer"))


def test_request_cannot_inject_host_port_or_url(tmp_path) -> None:
    digest = hashlib.sha256(b"x").hexdigest()
    with PersistentContentServer(store_root=tmp_path / "a") as source, PersistentContentServer(store_root=tmp_path / "b") as destination:
        directory = StaticPeerDirectory((PeerEndpoint("peer-a", *source.address), PeerEndpoint("peer-b", *destination.address)))
        relay = StaticChunkRelay(directory)
        request = _request(digest)
        request["host"] = "169.254.169.254"
        with pytest.raises(RelayInvariantError, match="shape"):
            relay.relay_chunk(request)


def test_source_and_destination_must_differ(tmp_path) -> None:
    digest = hashlib.sha256(b"x").hexdigest()
    with PersistentContentServer(store_root=tmp_path / "a") as source:
        directory = StaticPeerDirectory((PeerEndpoint("peer-a", *source.address),))
        relay = StaticChunkRelay(directory)
        with pytest.raises(RelayInvariantError, match="must differ"):
            relay.relay_chunk(_request(digest, source="peer-a", destination="peer-a"))


def test_missing_source_chunk_does_not_create_destination_data(tmp_path) -> None:
    digest = hashlib.sha256(b"missing").hexdigest()
    with PersistentContentServer(store_root=tmp_path / "a") as source, PersistentContentServer(store_root=tmp_path / "b") as destination:
        directory = StaticPeerDirectory((PeerEndpoint("peer-a", *source.address), PeerEndpoint("peer-b", *destination.address)))
        relay = StaticChunkRelay(directory)
        with pytest.raises(Exception):
            relay.relay_chunk(_request(digest))
        assert destination.store.has(digest) is False


def test_response_authority_tamper_fails_even_with_other_fields_intact(tmp_path) -> None:
    raw = b"authority-test"
    with PersistentContentServer(store_root=tmp_path / "a") as source, PersistentContentServer(store_root=tmp_path / "b") as destination:
        digest = PersistentContentClient(source.address).put(raw)
        directory = StaticPeerDirectory((PeerEndpoint("peer-a", *source.address), PeerEndpoint("peer-b", *destination.address)))
        request = _request(digest)
        response = StaticChunkRelay(directory).relay_chunk(request)
        response["execution_authority"] = "PROCESS"
        with pytest.raises(RelayInvariantError, match="execution_authority"):
            verify_response(response, request, directory)
