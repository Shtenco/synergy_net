from __future__ import annotations

import hashlib
import socket

from synergynet.content_service_v2 import ContentLimits, PersistentContentClient, PersistentContentServer, _json_line, _read_json_line
from synergynet.relay_service_v2 import RelayClient, RelayServer, StaticPeerDirectory


def test_content_roundtrip_status_and_restart(tmp_path) -> None:
    root = tmp_path / "store"
    raw = b"abc" * 10000
    with PersistentContentServer(
        store_root=root,
        limits=ContentLimits(max_payload_bytes=1024 * 1024, max_connections=8),
    ) as server:
        client = PersistentContentClient(server.address)
        status = client.status()
        assert status["status"] == "READY"
        assert status["service_id"] == "content-cache"
        assert status["execution_authority"] == "NONE"
        digest = client.put(raw, codec_id="zlib-9")
        assert digest == hashlib.sha256(raw).hexdigest()
        assert client.has(digest)
        assert client.get_raw(digest) == raw
    with PersistentContentServer(store_root=root) as server:
        assert PersistentContentClient(server.address).get_raw(digest) == raw


def test_content_rejects_shape_and_path_injection(tmp_path) -> None:
    with PersistentContentServer(store_root=tmp_path / "store") as server:
        with socket.create_connection(server.address, timeout=2) as sock:
            reader = sock.makefile("rb")
            sock.sendall(_json_line({"op": "STATUS", "path": "/tmp/evil"}))
            response = _read_json_line(reader)
        assert response == {"ok": False, "error": "INVALID_REQUEST", "execution_authority": "NONE"}


def test_relay_moves_exact_hash_between_allowlisted_peers(tmp_path) -> None:
    raw = b"relay-me" * 4096
    with PersistentContentServer(store_root=tmp_path / "a") as source, PersistentContentServer(store_root=tmp_path / "b") as destination:
        digest = PersistentContentClient(source.address).put(raw)
        directory = StaticPeerDirectory.from_payload({
            "schema": "synergynet.static-peer-directory/v2",
            "peers": [
                {"peer_id": "A", "host": source.address[0], "port": source.address[1]},
                {"peer_id": "B", "host": destination.address[0], "port": destination.address[1]},
            ],
        })
        with RelayServer(directory=directory) as relay:
            client = RelayClient(relay.address)
            status = client.status()
            assert status["status"] == "READY"
            assert status["execution_authority"] == "NONE"
            response = client.request({
                "op": "RELAY_CHUNK",
                "request_id": "r1",
                "source_peer_id": "A",
                "destination_peer_id": "B",
                "chunk_digest": digest,
            })
            assert response["ok"] is True
            assert response["chunk_digest"] == digest
            assert response["relay_scope"] == "STATIC_LOCAL_ALLOWLIST"
            assert response["execution_authority"] == "NONE"
            assert PersistentContentClient(destination.address).get_raw(digest) == raw


def test_relay_rejects_remote_address_injection(tmp_path) -> None:
    with PersistentContentServer(store_root=tmp_path / "a") as source, PersistentContentServer(store_root=tmp_path / "b") as destination:
        directory = StaticPeerDirectory.from_payload({
            "schema": "synergynet.static-peer-directory/v2",
            "peers": [
                {"peer_id": "A", "host": source.address[0], "port": source.address[1]},
                {"peer_id": "B", "host": destination.address[0], "port": destination.address[1]},
            ],
        })
        with RelayServer(directory=directory) as relay:
            response = RelayClient(relay.address).request({
                "op": "RELAY_CHUNK",
                "request_id": "r1",
                "source_peer_id": "A",
                "destination_peer_id": "B",
                "chunk_digest": "0" * 64,
                "host": "evil.example",
            })
            assert response["ok"] is False
            assert response["error"] == "INVALID_REQUEST"
            assert response["execution_authority"] == "NONE"
