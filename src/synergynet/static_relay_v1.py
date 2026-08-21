from __future__ import annotations

from dataclasses import dataclass
import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, BinaryIO

from .persistent_service_v1 import PersistentContentClient, PersistentServiceError


class RelayInvariantError(ValueError):
    pass


_MAX_REQUEST_BYTES = 16 * 1024
_MAX_PEERS = 256
_MAX_PEER_ID_BYTES = 128
_SCHEMA_REQUEST = "synergynet.relay-request/v1"
_SCHEMA_RESPONSE = "synergynet.relay-response/v1"
_OPERATION = "RELAY_CHUNK"


def _canonical(value: Any) -> bytes:
    def check(item: Any) -> None:
        if item is None or isinstance(item, (str, bool)):
            return
        if isinstance(item, int) and not isinstance(item, bool):
            if abs(item) > 2**53 - 1:
                raise RelayInvariantError("unsafe integer")
            return
        if isinstance(item, float):
            raise RelayInvariantError("floats forbidden in relay protocol")
        if isinstance(item, list):
            for child in item:
                check(child)
            return
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise RelayInvariantError("object keys must be strings")
            for child in item.values():
                check(child)
            return
        raise RelayInvariantError("unsupported relay-protocol value")

    check(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest_payload(payload: dict[str, Any], digest_field: str | None = None) -> str:
    body = dict(payload)
    if digest_field is not None:
        body.pop(digest_field, None)
    return hashlib.sha256(_canonical(body)).hexdigest()


def _sha256(value: object) -> str:
    if not isinstance(value, str) or len(value) != 64 or value.lower() != value:
        raise RelayInvariantError("digest must be lowercase sha256 hex")
    if any(ch not in "0123456789abcdef" for ch in value):
        raise RelayInvariantError("digest must be lowercase sha256 hex")
    return value


def _peer_id(value: object) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > _MAX_PEER_ID_BYTES:
        raise RelayInvariantError("invalid peer_id")
    return value


def _request_id(value: object) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 128:
        raise RelayInvariantError("invalid request_id")
    return value


@dataclass(frozen=True)
class PeerEndpoint:
    peer_id: str
    host: str
    port: int

    def __post_init__(self) -> None:
        _peer_id(self.peer_id)
        if not isinstance(self.host, str) or not self.host or len(self.host.encode("utf-8")) > 255:
            raise RelayInvariantError("invalid peer host")
        if isinstance(self.port, bool) or not isinstance(self.port, int) or not (1 <= self.port <= 65535):
            raise RelayInvariantError("invalid peer port")

    @property
    def address(self) -> tuple[str, int]:
        return self.host, self.port


class StaticPeerDirectory:
    def __init__(self, endpoints: tuple[PeerEndpoint, ...]):
        if not endpoints or len(endpoints) > _MAX_PEERS:
            raise RelayInvariantError("peer directory size out of bounds")
        by_id = {endpoint.peer_id: endpoint for endpoint in endpoints}
        if len(by_id) != len(endpoints):
            raise RelayInvariantError("peer ids must be unique")
        self._peers = by_id

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "StaticPeerDirectory":
        if not isinstance(payload, dict) or set(payload) != {"schema", "peers"}:
            raise RelayInvariantError("unexpected peer-directory shape")
        if payload["schema"] != "synergynet.static-peer-directory/v1":
            raise RelayInvariantError("unexpected peer-directory schema")
        peers = payload["peers"]
        if not isinstance(peers, list):
            raise RelayInvariantError("peers must be a list")
        endpoints: list[PeerEndpoint] = []
        for peer in peers:
            if not isinstance(peer, dict) or set(peer) != {"peer_id", "host", "port"}:
                raise RelayInvariantError("unexpected peer entry shape")
            endpoints.append(PeerEndpoint(peer_id=peer["peer_id"], host=peer["host"], port=peer["port"]))
        directory = cls(tuple(endpoints))
        _canonical(payload)
        return directory

    def resolve(self, peer_id: str) -> PeerEndpoint:
        peer_id = _peer_id(peer_id)
        try:
            return self._peers[peer_id]
        except KeyError as exc:
            raise RelayInvariantError("peer is not allowlisted") from exc


@dataclass(frozen=True)
class RelayResult:
    request_id: str
    source_peer_id: str
    destination_peer_id: str
    chunk_digest: str
    raw_bytes: int

    def to_response(self, request_digest: str) -> dict[str, Any]:
        response = {
            "schema": _SCHEMA_RESPONSE,
            "request_id": self.request_id,
            "operation": _OPERATION,
            "request_digest": request_digest,
            "source_peer_id": self.source_peer_id,
            "destination_peer_id": self.destination_peer_id,
            "chunk_digest": self.chunk_digest,
            "raw_bytes": self.raw_bytes,
            "relay_scope": "STATIC_ALLOWLISTED_PEERS_ONLY",
            "status": "RELAYED",
            "payment_authority": "NONE",
            "accounting_authority": "NONE",
            "execution_authority": "NONE",
        }
        response["response_digest"] = _digest_payload(response)
        return response


class StaticChunkRelay:
    def __init__(self, directory: StaticPeerDirectory, *, timeout: float = 5.0):
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
            raise RelayInvariantError("timeout must be positive")
        self.directory = directory
        self.timeout = float(timeout)

    def relay_chunk(self, request: dict[str, Any]) -> dict[str, Any]:
        verified = verify_request(request)
        source_id = verified["source_peer_id"]
        destination_id = verified["destination_peer_id"]
        if source_id == destination_id:
            raise RelayInvariantError("source and destination peers must differ")
        source = self.directory.resolve(source_id)
        destination = self.directory.resolve(destination_id)
        digest = verified["chunk_digest"]

        source_client = PersistentContentClient(source.address, timeout=self.timeout)
        destination_client = PersistentContentClient(destination.address, timeout=self.timeout)
        raw = source_client.get_raw(digest)
        if hashlib.sha256(raw).hexdigest() != digest:
            raise RelayInvariantError("source returned wrong content")
        stored = destination_client.put(raw, codec_id="raw")
        if stored != digest or not destination_client.has(digest):
            raise RelayInvariantError("destination failed to commit relayed chunk")

        result = RelayResult(
            request_id=verified["request_id"],
            source_peer_id=source_id,
            destination_peer_id=destination_id,
            chunk_digest=digest,
            raw_bytes=len(raw),
        )
        return result.to_response(_digest_payload(verified))


def verify_request(payload: dict[str, Any]) -> dict[str, Any]:
    expected = {"schema", "request_id", "operation", "source_peer_id", "destination_peer_id", "chunk_digest"}
    if not isinstance(payload, dict) or set(payload) != expected:
        raise RelayInvariantError("unexpected relay request shape")
    if payload["schema"] != _SCHEMA_REQUEST:
        raise RelayInvariantError("unexpected relay request schema")
    if payload["operation"] != _OPERATION:
        raise RelayInvariantError("operation is not allowlisted")
    _request_id(payload["request_id"])
    _peer_id(payload["source_peer_id"])
    _peer_id(payload["destination_peer_id"])
    _sha256(payload["chunk_digest"])
    _canonical(payload)
    return payload


def verify_response(payload: dict[str, Any], request: dict[str, Any], directory: StaticPeerDirectory) -> dict[str, Any]:
    expected = {
        "schema", "request_id", "operation", "request_digest", "source_peer_id", "destination_peer_id",
        "chunk_digest", "raw_bytes", "relay_scope", "status", "payment_authority", "accounting_authority",
        "execution_authority", "response_digest"
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        raise RelayInvariantError("unexpected relay response shape")
    if payload["schema"] != _SCHEMA_RESPONSE or payload["operation"] != _OPERATION:
        raise RelayInvariantError("unexpected relay response identity")
    if payload["relay_scope"] != "STATIC_ALLOWLISTED_PEERS_ONLY" or payload["status"] != "RELAYED":
        raise RelayInvariantError("unexpected relay status")
    for authority in ("payment_authority", "accounting_authority", "execution_authority"):
        if payload[authority] != "NONE":
            raise RelayInvariantError(f"relay cannot grant {authority}")
    if isinstance(payload["raw_bytes"], bool) or not isinstance(payload["raw_bytes"], int) or payload["raw_bytes"] < 0:
        raise RelayInvariantError("invalid raw_bytes")
    verified_request = verify_request(request)
    directory.resolve(verified_request["source_peer_id"])
    directory.resolve(verified_request["destination_peer_id"])
    if payload["request_digest"] != _digest_payload(verified_request):
        raise RelayInvariantError("request digest mismatch")
    for field in ("request_id", "source_peer_id", "destination_peer_id", "chunk_digest"):
        if payload[field] != verified_request[field]:
            raise RelayInvariantError("response does not match request")
    if payload["response_digest"] != _digest_payload(payload, "response_digest"):
        raise RelayInvariantError("response digest mismatch")
    return payload


def serve_jsonl(relay: StaticChunkRelay, reader: BinaryIO, writer: BinaryIO) -> int:
    while True:
        line = reader.readline(_MAX_REQUEST_BYTES + 1)
        if not line:
            return 0
        if len(line) > _MAX_REQUEST_BYTES or not line.endswith(b"\n"):
            writer.write(_canonical({"schema":"synergynet.relay-error/v1","code":"INVALID_FRAME","execution_authority":"NONE"}) + b"\n")
            writer.flush()
            return 2
        try:
            request = json.loads(line.decode("utf-8"))
            response = relay.relay_chunk(request)
        except (UnicodeDecodeError, json.JSONDecodeError, RelayInvariantError, PersistentServiceError, ValueError):
            response = {"schema":"synergynet.relay-error/v1","code":"INVALID_REQUEST","execution_authority":"NONE"}
        writer.write(_canonical(response) + b"\n")
        writer.flush()


def _load_directory(path: str | Path) -> StaticPeerDirectory:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return StaticPeerDirectory.from_payload(payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SynergyNet static peer relay v1")
    parser.add_argument("--peer-directory", required=True, help="local allowlisted peer directory JSON")
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args(argv)
    relay = StaticChunkRelay(_load_directory(args.peer_directory), timeout=args.timeout)
    return serve_jsonl(relay, sys.stdin.buffer, sys.stdout.buffer)


if __name__ == "__main__":
    raise SystemExit(main())
