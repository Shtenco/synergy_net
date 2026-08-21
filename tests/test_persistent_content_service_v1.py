from __future__ import annotations

import hashlib
import json
import socket

import pytest

from synergynet.persistent_service_v1 import (
    PersistentContentClient,
    PersistentContentServer,
    PersistentServiceError,
)


def _line(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def test_status_and_round_trip_raw(tmp_path) -> None:
    with PersistentContentServer(store_root=tmp_path / "store") as server:
        client = PersistentContentClient(server.address)
        status = client.status()
        assert status == {
            "ok": True,
            "schema": "synergynet.content-service/v1",
            "protocol": "synergynet.content-wire/v1",
            "store_kind": "DIRECTORY_SHA256_RAW_BYTES",
            "execution_authority": "NONE",
        }
        raw = b"synergy-net-persistent-content" * 100
        digest = client.put(raw, codec_id="raw")
        assert digest == hashlib.sha256(raw).hexdigest()
        assert client.has(digest) is True
        assert client.get_raw(digest) == raw


def test_zlib_wire_representation_preserves_raw_content_identity(tmp_path) -> None:
    raw = (b"compressible-synergy-payload-" * 1000)
    expected = hashlib.sha256(raw).hexdigest()
    with PersistentContentServer(store_root=tmp_path / "store") as server:
        client = PersistentContentClient(server.address)
        assert client.put(raw, codec_id="zlib-9") == expected
        assert client.get_raw(expected) == raw
        assert server.store.get(expected) == raw


def test_store_survives_service_restart(tmp_path) -> None:
    root = tmp_path / "store"
    raw = b"restart-persistent"
    with PersistentContentServer(store_root=root) as server:
        digest = PersistentContentClient(server.address).put(raw)
    with PersistentContentServer(store_root=root) as server:
        client = PersistentContentClient(server.address)
        assert client.has(digest) is True
        assert client.get_raw(digest) == raw


def test_network_request_cannot_supply_filesystem_path(tmp_path) -> None:
    with PersistentContentServer(store_root=tmp_path / "store") as server:
        with socket.create_connection(server.address, timeout=2) as sock:
            reader = sock.makefile("rb")
            sock.sendall(_line({"op": "HAS", "digest": "0" * 64, "path": "/tmp/escape"}))
            response = json.loads(reader.readline().decode())
        assert response["ok"] is False
        assert response["error"] == "INVALID_REQUEST"
        assert response["execution_authority"] == "NONE"


def test_digest_mismatch_is_rejected_before_store_commit(tmp_path) -> None:
    root = tmp_path / "store"
    raw = b"actual-bytes"
    false_digest = hashlib.sha256(b"different").hexdigest()
    with PersistentContentServer(store_root=root) as server:
        with socket.create_connection(server.address, timeout=2) as sock:
            reader = sock.makefile("rb")
            sock.sendall(_line({
                "op": "PUT",
                "digest": false_digest,
                "raw_size": len(raw),
                "payload_size": len(raw),
                "codec": "raw",
            }))
            sock.sendall(raw)
            response = json.loads(reader.readline().decode())
        assert response["ok"] is False
        assert server.store.has(false_digest) is False


def test_unknown_operation_is_fail_closed(tmp_path) -> None:
    with PersistentContentServer(store_root=tmp_path / "store") as server:
        with socket.create_connection(server.address, timeout=2) as sock:
            reader = sock.makefile("rb")
            sock.sendall(_line({"op": "RUN_COMMAND", "command": "anything"}))
            response = json.loads(reader.readline().decode())
        assert response["ok"] is False
        assert response["error"] == "UNKNOWN_OP"
        assert response["execution_authority"] == "NONE"


def test_missing_chunk_is_not_synthesized(tmp_path) -> None:
    with PersistentContentServer(store_root=tmp_path / "store") as server:
        client = PersistentContentClient(server.address)
        with pytest.raises(PersistentServiceError):
            client.get_raw("1" * 64)
