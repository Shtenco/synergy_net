from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import signal
import socket
import socketserver
import threading
from typing import Any

from .content_service_v2 import ContentServiceError, PersistentContentClient, _canonical, _digest, _json_line, _read_json_line


class RelayServiceError(ValueError):
    pass


_MAX_PEERS = 256
_MAX_PEER_ID_BYTES = 128
_DEFAULT_MAX_CONNECTIONS = 32
_SCHEMA = "synergynet.relay-service/v2"
_PROTOCOL = "synergynet.relay-wire/v2"


def _peer_id(value: object) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > _MAX_PEER_ID_BYTES:
        raise RelayServiceError("invalid peer id")
    return value


def _request_id(value: object) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 128:
        raise RelayServiceError("invalid request id")
    return value


def _exact(payload: dict[str, Any], fields: set[str]) -> None:
    if set(payload) != fields:
        raise RelayServiceError("unexpected request shape")


def _body_digest(payload: dict[str, Any], field: str | None = None) -> str:
    body = dict(payload)
    if field is not None:
        body.pop(field, None)
    return hashlib.sha256(_canonical(body)).hexdigest()


@dataclass(frozen=True)
class PeerEndpoint:
    peer_id: str
    host: str
    port: int

    def __post_init__(self) -> None:
        _peer_id(self.peer_id)
        if not isinstance(self.host, str) or not self.host or len(self.host.encode("utf-8")) > 255:
            raise RelayServiceError("invalid host")
        if isinstance(self.port, bool) or not isinstance(self.port, int) or not 1 <= self.port <= 65535:
            raise RelayServiceError("invalid port")

    @property
    def address(self) -> tuple[str, int]:
        return self.host, self.port


class StaticPeerDirectory:
    def __init__(self, endpoints: tuple[PeerEndpoint, ...]):
        if not endpoints or len(endpoints) > _MAX_PEERS:
            raise RelayServiceError("peer directory size out of bounds")
        self._peers = {endpoint.peer_id: endpoint for endpoint in endpoints}
        if len(self._peers) != len(endpoints):
            raise RelayServiceError("peer ids must be unique")

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "StaticPeerDirectory":
        if not isinstance(payload, dict) or set(payload) != {"schema", "peers"}:
            raise RelayServiceError("invalid peer directory")
        if payload.get("schema") != "synergynet.static-peer-directory/v2":
            raise RelayServiceError("invalid peer directory schema")
        peers = payload["peers"]
        if not isinstance(peers, list):
            raise RelayServiceError("peers must be list")
        endpoints: list[PeerEndpoint] = []
        for peer in peers:
            if not isinstance(peer, dict) or set(peer) != {"peer_id", "host", "port"}:
                raise RelayServiceError("invalid peer entry")
            endpoints.append(PeerEndpoint(peer["peer_id"], peer["host"], peer["port"]))
        _canonical(payload)
        return cls(tuple(endpoints))

    @classmethod
    def from_file(cls, path: str | Path) -> "StaticPeerDirectory":
        return cls.from_payload(json.loads(Path(path).read_text(encoding="utf-8")))

    def resolve(self, peer_id: str) -> PeerEndpoint:
        try:
            return self._peers[_peer_id(peer_id)]
        except KeyError as exc:
            raise RelayServiceError("peer is not allowlisted") from exc

    @property
    def size(self) -> int:
        return len(self._peers)


class StaticChunkRelay:
    def __init__(self, directory: StaticPeerDirectory, timeout: float = 5.0):
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0 or timeout > 60:
            raise RelayServiceError("invalid timeout")
        self.directory = directory
        self.timeout = float(timeout)

    def relay(self, request: dict[str, Any]) -> dict[str, Any]:
        _exact(request, {"op", "request_id", "source_peer_id", "destination_peer_id", "chunk_digest"})
        if request["op"] != "RELAY_CHUNK":
            raise RelayServiceError("operation not allowlisted")
        request_id = _request_id(request["request_id"])
        source_id = _peer_id(request["source_peer_id"])
        destination_id = _peer_id(request["destination_peer_id"])
        digest = _digest(request["chunk_digest"])
        if source_id == destination_id:
            raise RelayServiceError("source and destination must differ")
        source = self.directory.resolve(source_id)
        destination = self.directory.resolve(destination_id)
        raw = PersistentContentClient(source.address, self.timeout).get_raw(digest)
        if hashlib.sha256(raw).hexdigest() != digest:
            raise RelayServiceError("source integrity failure")
        destination_client = PersistentContentClient(destination.address, self.timeout)
        stored = destination_client.put(raw, codec_id="raw")
        if stored != digest or not destination_client.has(digest):
            raise RelayServiceError("destination commit failure")
        response = {
            "ok": True,
            "schema": _SCHEMA,
            "protocol": _PROTOCOL,
            "operation": "RELAY_CHUNK",
            "request_id": request_id,
            "request_digest": _body_digest(request),
            "source_peer_id": source_id,
            "destination_peer_id": destination_id,
            "chunk_digest": digest,
            "raw_bytes": len(raw),
            "relay_scope": "STATIC_LOCAL_ALLOWLIST",
            "payment_authority": "NONE",
            "accounting_authority": "NONE",
            "execution_authority": "NONE",
        }
        response["response_digest"] = _body_digest(response)
        return response


class _State:
    def __init__(self, relay: StaticChunkRelay, max_connections: int):
        self.relay = relay
        self.max_connections = max_connections


class _Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        try:
            request = _read_json_line(self.rfile)
        except Exception:
            self._reply({"ok": False, "error": "INVALID_FRAME", "execution_authority": "NONE"})
            return
        try:
            op = request.get("op")
            if op == "STATUS":
                _exact(request, {"op"})
                state: _State = self.server.state  # type: ignore[attr-defined]
                self._reply({
                    "ok": True,
                    "schema": _SCHEMA,
                    "protocol": _PROTOCOL,
                    "service_id": "synergynet",
                    "status": "READY",
                    "peer_directory_mode": "STATIC_LOCAL_ALLOWLIST",
                    "peer_count": state.relay.directory.size,
                    "max_connections": state.max_connections,
                    "execution_authority": "NONE",
                })
                return
            if op != "RELAY_CHUNK":
                raise RelayServiceError("unknown op")
            state: _State = self.server.state  # type: ignore[attr-defined]
            self._reply(state.relay.relay(request))
        except (RelayServiceError, ContentServiceError, OSError, ValueError, KeyError, TypeError):
            self._reply({"ok": False, "error": "INVALID_REQUEST", "execution_authority": "NONE"})

    def _reply(self, payload: dict[str, Any]) -> None:
        self.wfile.write(_json_line(payload))
        self.wfile.flush()


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address: tuple[str, int], state: _State):
        self.state = state
        self._slots = threading.BoundedSemaphore(state.max_connections)
        super().__init__(address, _Handler)

    def process_request(self, request, client_address) -> None:
        if not self._slots.acquire(blocking=False):
            try:
                request.sendall(_json_line({"ok": False, "error": "BUSY", "execution_authority": "NONE"}))
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._slots.release()
            raise

    def shutdown_request(self, request) -> None:
        try:
            super().shutdown_request(request)
        finally:
            try:
                self._slots.release()
            except ValueError:
                pass


class RelayServer:
    def __init__(
        self,
        *,
        directory: StaticPeerDirectory,
        host: str = "127.0.0.1",
        port: int = 0,
        timeout: float = 5.0,
        max_connections: int = _DEFAULT_MAX_CONNECTIONS,
    ):
        if not isinstance(host, str) or not host:
            raise RelayServiceError("host required")
        if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
            raise RelayServiceError("invalid port")
        if isinstance(max_connections, bool) or not isinstance(max_connections, int) or not 1 <= max_connections <= 256:
            raise RelayServiceError("invalid max_connections")
        self._server = _Server((host, port), _State(StaticChunkRelay(directory, timeout), max_connections))
        self._thread: threading.Thread | None = None

    @property
    def address(self) -> tuple[str, int]:
        host, port = self._server.server_address[:2]
        return str(host), int(port)

    def start(self) -> "RelayServer":
        if self._thread is not None:
            raise RelayServiceError("server already started")
        self._thread = threading.Thread(target=self._server.serve_forever, name="synergynet-relay-v2", daemon=True)
        self._thread.start()
        return self

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def __enter__(self) -> "RelayServer":
        return self.start()

    def __exit__(self, *_args) -> None:
        self.close()


class RelayClient:
    def __init__(self, address: tuple[str, int], timeout: float = 5.0):
        self.address = address
        self.timeout = timeout

    def request(self, payload: dict[str, Any]) -> dict[str, Any]:
        with socket.create_connection(self.address, timeout=self.timeout) as sock:
            reader = sock.makefile("rb")
            sock.sendall(_json_line(payload))
            return _read_json_line(reader)

    def status(self) -> dict[str, Any]:
        return self.request({"op": "STATUS"})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SynergyNet bounded static relay service v2")
    parser.add_argument("--peer-directory", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7792)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--max-connections", type=int, default=_DEFAULT_MAX_CONNECTIONS)
    args = parser.parse_args(argv)
    stop = threading.Event()

    def stop_now(_signum, _frame) -> None:
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop_now)
    with RelayServer(
        directory=StaticPeerDirectory.from_file(args.peer_directory),
        host=args.host,
        port=args.port,
        timeout=args.timeout,
        max_connections=args.max_connections,
    ):
        stop.wait()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
