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
from typing import Any, BinaryIO

from .storage_v3 import CodecRegistry, DirectoryChunkStore, StorageInvariantError


class ContentServiceError(ValueError):
    pass


_MAX_HEADER_BYTES = 16 * 1024
_DEFAULT_MAX_PAYLOAD_BYTES = 32 * 1024 * 1024
_DEFAULT_MAX_CONNECTIONS = 64
_SERVICE_SCHEMA = "synergynet.content-service/v2"
_PROTOCOL = "synergynet.content-wire/v2"
_ALLOWED_OPS = {"STATUS", "HAS", "PUT", "GET_RAW"}


def _canonical(value: Any) -> bytes:
    def check(item: Any) -> None:
        if item is None or isinstance(item, (str, bool)):
            return
        if isinstance(item, int) and not isinstance(item, bool):
            if abs(item) > 2**53 - 1:
                raise ContentServiceError("unsafe integer")
            return
        if isinstance(item, float):
            raise ContentServiceError("floats are forbidden")
        if isinstance(item, list):
            for child in item:
                check(child)
            return
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise ContentServiceError("object keys must be strings")
            for child in item.values():
                check(child)
            return
        raise ContentServiceError("unsupported protocol value")

    check(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _json_line(value: dict[str, Any]) -> bytes:
    return _canonical(value) + b"\n"


def _read_json_line(reader: BinaryIO) -> dict[str, Any]:
    line = reader.readline(_MAX_HEADER_BYTES + 1)
    if not line or len(line) > _MAX_HEADER_BYTES or not line.endswith(b"\n"):
        raise ContentServiceError("invalid frame header")
    try:
        value = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContentServiceError("invalid JSON header") from exc
    if not isinstance(value, dict):
        raise ContentServiceError("frame header must be object")
    _canonical(value)
    return value


def _digest(value: object) -> str:
    if not isinstance(value, str) or len(value) != 64 or value.lower() != value:
        raise ContentServiceError("digest must be lowercase sha256 hex")
    if any(ch not in "0123456789abcdef" for ch in value):
        raise ContentServiceError("digest must be lowercase sha256 hex")
    return value


def _bounded_int(value: object, name: str, lower: int, upper: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper:
        raise ContentServiceError(f"invalid {name}")
    return value


def _exact(payload: dict[str, Any], fields: set[str]) -> None:
    if set(payload) != fields:
        raise ContentServiceError("unexpected request shape")


@dataclass(frozen=True)
class ContentLimits:
    max_payload_bytes: int = _DEFAULT_MAX_PAYLOAD_BYTES
    max_connections: int = _DEFAULT_MAX_CONNECTIONS

    def __post_init__(self) -> None:
        _bounded_int(self.max_payload_bytes, "max_payload_bytes", 1, 256 * 1024 * 1024)
        _bounded_int(self.max_connections, "max_connections", 1, 256)


class _State:
    def __init__(self, store: DirectoryChunkStore, codecs: CodecRegistry, limits: ContentLimits):
        self.store = store
        self.codecs = codecs
        self.limits = limits
        self.lock = threading.Lock()


class _Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        state: _State = self.server.state  # type: ignore[attr-defined]
        while True:
            try:
                request = _read_json_line(self.rfile)
            except ContentServiceError:
                self._reply({"ok": False, "error": "INVALID_FRAME", "execution_authority": "NONE"})
                return
            op = request.get("op")
            if op not in _ALLOWED_OPS:
                self._reply({"ok": False, "error": "UNKNOWN_OP", "execution_authority": "NONE"})
                return
            try:
                if op == "STATUS":
                    _exact(request, {"op"})
                    self._reply({
                        "ok": True,
                        "schema": _SERVICE_SCHEMA,
                        "protocol": _PROTOCOL,
                        "service_id": "content-cache",
                        "status": "READY",
                        "store_kind": "DIRECTORY_SHA256_RAW_BYTES",
                        "max_payload_bytes": state.limits.max_payload_bytes,
                        "max_connections": state.limits.max_connections,
                        "execution_authority": "NONE",
                    })
                    continue
                if op == "HAS":
                    _exact(request, {"op", "digest"})
                    digest = _digest(request["digest"])
                    with state.lock:
                        present = state.store.has(digest)
                    self._reply({"ok": True, "present": present, "execution_authority": "NONE"})
                    continue
                if op == "PUT":
                    _exact(request, {"op", "digest", "raw_size", "payload_size", "codec"})
                    digest = _digest(request["digest"])
                    raw_size = _bounded_int(request["raw_size"], "raw_size", 0, state.limits.max_payload_bytes)
                    payload_size = _bounded_int(request["payload_size"], "payload_size", 0, state.limits.max_payload_bytes)
                    codec_id = request["codec"]
                    if not isinstance(codec_id, str) or codec_id not in {"raw", "zlib-9"}:
                        raise ContentServiceError("codec not allowlisted")
                    payload = self.rfile.read(payload_size)
                    if len(payload) != payload_size:
                        raise ContentServiceError("truncated payload")
                    try:
                        raw = state.codecs.get(codec_id).decode(payload)
                    except Exception as exc:
                        raise ContentServiceError("codec decode failed") from exc
                    if len(raw) != raw_size or len(raw) > state.limits.max_payload_bytes:
                        raise ContentServiceError("decoded content size mismatch")
                    if hashlib.sha256(raw).hexdigest() != digest:
                        raise ContentServiceError("decoded content digest mismatch")
                    with state.lock:
                        stored = state.store.put(raw)
                    if stored != digest:
                        raise ContentServiceError("store digest mismatch")
                    self._reply({"ok": True, "digest": digest, "execution_authority": "NONE"})
                    continue
                if op == "GET_RAW":
                    _exact(request, {"op", "digest"})
                    digest = _digest(request["digest"])
                    with state.lock:
                        raw = state.store.get(digest)
                    if len(raw) > state.limits.max_payload_bytes:
                        raise ContentServiceError("stored object exceeds service limit")
                    self.wfile.write(_json_line({
                        "ok": True,
                        "digest": digest,
                        "raw_size": len(raw),
                        "execution_authority": "NONE",
                    }))
                    self.wfile.write(raw)
                    self.wfile.flush()
                    continue
            except (ContentServiceError, StorageInvariantError, KeyError, TypeError, ValueError):
                self._reply({"ok": False, "error": "INVALID_REQUEST", "execution_authority": "NONE"})
                return

    def _reply(self, payload: dict[str, Any]) -> None:
        self.wfile.write(_json_line(payload))
        self.wfile.flush()


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address: tuple[str, int], state: _State):
        self.state = state
        self._slots = threading.BoundedSemaphore(state.limits.max_connections)
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


class PersistentContentServer:
    def __init__(
        self,
        *,
        store_root: str | Path,
        host: str = "127.0.0.1",
        port: int = 0,
        limits: ContentLimits | None = None,
        codecs: CodecRegistry | None = None,
    ):
        if not isinstance(host, str) or not host:
            raise ContentServiceError("host is required")
        _bounded_int(port, "port", 0, 65535)
        state = _State(DirectoryChunkStore(store_root), codecs or CodecRegistry(), limits or ContentLimits())
        self._server = _Server((host, port), state)
        self._thread: threading.Thread | None = None

    @property
    def address(self) -> tuple[str, int]:
        host, port = self._server.server_address[:2]
        return str(host), int(port)

    def start(self) -> "PersistentContentServer":
        if self._thread is not None:
            raise ContentServiceError("server already started")
        self._thread = threading.Thread(target=self._server.serve_forever, name="synergynet-content-cache-v2", daemon=True)
        self._thread.start()
        return self

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def __enter__(self) -> "PersistentContentServer":
        return self.start()

    def __exit__(self, *_args) -> None:
        self.close()


class PersistentContentClient:
    def __init__(self, address: tuple[str, int], timeout: float = 5.0):
        self.address = address
        self.timeout = float(timeout)

    def _header(self, request: dict[str, Any]) -> dict[str, Any]:
        with socket.create_connection(self.address, timeout=self.timeout) as sock:
            reader = sock.makefile("rb")
            sock.sendall(_json_line(request))
            return _read_json_line(reader)

    def status(self) -> dict[str, Any]:
        return self._header({"op": "STATUS"})

    def has(self, digest: str) -> bool:
        response = self._header({"op": "HAS", "digest": _digest(digest)})
        if not response.get("ok"):
            raise ContentServiceError("HAS failed")
        return bool(response["present"])

    def put(self, raw: bytes, *, codec_id: str = "raw") -> str:
        raw = bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        codec = CodecRegistry().get(codec_id)
        payload = codec.encode(raw)
        with socket.create_connection(self.address, timeout=self.timeout) as sock:
            reader = sock.makefile("rb")
            sock.sendall(_json_line({
                "op": "PUT",
                "digest": digest,
                "raw_size": len(raw),
                "payload_size": len(payload),
                "codec": codec_id,
            }))
            sock.sendall(payload)
            response = _read_json_line(reader)
        if not response.get("ok") or response.get("digest") != digest:
            raise ContentServiceError("PUT failed")
        return digest

    def get_raw(self, digest: str) -> bytes:
        digest = _digest(digest)
        with socket.create_connection(self.address, timeout=self.timeout) as sock:
            reader = sock.makefile("rb")
            sock.sendall(_json_line({"op": "GET_RAW", "digest": digest}))
            response = _read_json_line(reader)
            if not response.get("ok") or response.get("digest") != digest:
                raise ContentServiceError("GET_RAW failed")
            raw_size = _bounded_int(response["raw_size"], "raw_size", 0, 256 * 1024 * 1024)
            raw = reader.read(raw_size)
        if len(raw) != raw_size or hashlib.sha256(raw).hexdigest() != digest:
            raise ContentServiceError("GET_RAW integrity failure")
        return raw


def probe(address: tuple[str, int], timeout: float = 2.0) -> bool:
    try:
        response = PersistentContentClient(address, timeout=timeout).status()
    except OSError:
        return False
    return (
        response.get("ok") is True
        and response.get("status") == "READY"
        and response.get("schema") == _SERVICE_SCHEMA
        and response.get("execution_authority") == "NONE"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SynergyNet bounded persistent content service v2")
    parser.add_argument("--store", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7791)
    parser.add_argument("--max-payload-bytes", type=int, default=_DEFAULT_MAX_PAYLOAD_BYTES)
    parser.add_argument("--max-connections", type=int, default=_DEFAULT_MAX_CONNECTIONS)
    args = parser.parse_args(argv)
    stop = threading.Event()

    def stop_now(_signum, _frame) -> None:
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop_now)
    limits = ContentLimits(args.max_payload_bytes, args.max_connections)
    with PersistentContentServer(store_root=args.store, host=args.host, port=args.port, limits=limits):
        stop.wait()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
