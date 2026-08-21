from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import socket
import socketserver
import threading
from typing import BinaryIO

from .lab import Chunk, ChunkStore, MeshInvariantError, chunk_bytes

_MAX_HEADER = 16 * 1024
_MAX_PAYLOAD = 32 * 1024 * 1024


@dataclass(frozen=True)
class TcpTransferReport:
    object_digest: str
    raw_object_bytes: int
    chunks_total: int
    cache_hits: int
    chunks_transmitted: int
    payload_bytes_transmitted: int
    wire_bytes_sent: int
    integrity_verified: bool


class _State:
    def __init__(self, node_id: str):
        self.store = ChunkStore(node_id)
        self.lock = threading.Lock()


class _ChunkHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        state: _State = self.server.state  # type: ignore[attr-defined]
        while True:
            line = self.rfile.readline(_MAX_HEADER + 1)
            if not line:
                return
            if len(line) > _MAX_HEADER or not line.endswith(b"\n"):
                self._reply({"ok": False, "error": "INVALID_HEADER"})
                return
            try:
                request = json.loads(line.decode("utf-8"))
                op = request["op"]
                if op == "HAS":
                    digest = _digest(request["digest"])
                    with state.lock:
                        present = state.store.has(digest)
                    self._reply({"ok": True, "present": present})
                elif op == "PUT":
                    digest = _digest(request["digest"])
                    raw_size = _safe_size(request["raw_size"], "raw_size")
                    payload_size = _safe_size(request["payload_size"], "payload_size")
                    encoding = request["encoding"]
                    if encoding not in {"raw", "zlib"}:
                        raise MeshInvariantError("unsupported encoding")
                    payload = self.rfile.read(payload_size)
                    if len(payload) != payload_size:
                        raise MeshInvariantError("truncated payload")
                    chunk = Chunk(digest=digest, raw_size=raw_size, payload=payload, encoding=encoding)
                    chunk.raw()
                    with state.lock:
                        state.store.put_chunk(chunk)
                    self._reply({"ok": True})
                elif op == "GET_RAW":
                    digest = _digest(request["digest"])
                    with state.lock:
                        if not state.store.has(digest):
                            self._reply({"ok": False, "error": "NOT_FOUND"})
                            continue
                        raw = state.store.chunks[digest].raw()
                    header = _json_line({"ok": True, "raw_size": len(raw)})
                    self.wfile.write(header)
                    self.wfile.write(raw)
                    self.wfile.flush()
                else:
                    self._reply({"ok": False, "error": "UNKNOWN_OP"})
            except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError, MeshInvariantError):
                self._reply({"ok": False, "error": "INVALID_REQUEST"})
                return

    def _reply(self, payload: dict) -> None:
        self.wfile.write(_json_line(payload))
        self.wfile.flush()


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address: tuple[str, int], node_id: str):
        self.state = _State(node_id)
        super().__init__(address, _ChunkHandler)


class TcpChunkServer:
    def __init__(self, node_id: str, host: str = "127.0.0.1", port: int = 0):
        self._server = _Server((host, port), node_id)
        self._thread: threading.Thread | None = None

    @property
    def address(self) -> tuple[str, int]:
        host, port = self._server.server_address[:2]
        return str(host), int(port)

    @property
    def store(self) -> ChunkStore:
        return self._server.state.store

    def start(self) -> "TcpChunkServer":
        if self._thread is not None:
            raise RuntimeError("server already started")
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def __enter__(self) -> "TcpChunkServer":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


class TcpContentClient:
    def __init__(self, address: tuple[str, int], timeout: float = 5.0):
        self.address = address
        self.timeout = timeout

    def transfer(self, data: bytes) -> TcpTransferReport:
        object_digest = hashlib.sha256(data).hexdigest()
        parts = chunk_bytes(data)
        cache_hits = 0
        chunks_sent = 0
        payload_bytes = 0
        wire_bytes = 0
        digests: list[str] = []

        with socket.create_connection(self.address, timeout=self.timeout) as sock:
            reader = sock.makefile("rb")
            for part in parts:
                chunk = ChunkStore("sender").put_raw(part)
                digests.append(chunk.digest)
                has = _json_line({"op": "HAS", "digest": chunk.digest})
                sock.sendall(has)
                wire_bytes += len(has)
                response = _read_json(reader)
                if not response.get("ok"):
                    raise MeshInvariantError("HAS failed")
                if response["present"]:
                    cache_hits += 1
                    continue
                header = _json_line({
                    "op": "PUT",
                    "digest": chunk.digest,
                    "raw_size": chunk.raw_size,
                    "payload_size": len(chunk.payload),
                    "encoding": chunk.encoding,
                })
                sock.sendall(header)
                sock.sendall(chunk.payload)
                wire_bytes += len(header) + len(chunk.payload)
                payload_bytes += len(chunk.payload)
                chunks_sent += 1
                response = _read_json(reader)
                if not response.get("ok"):
                    raise MeshInvariantError("PUT failed")

            reconstructed = bytearray()
            for digest in digests:
                header = _json_line({"op": "GET_RAW", "digest": digest})
                sock.sendall(header)
                wire_bytes += len(header)
                response = _read_json(reader)
                if not response.get("ok"):
                    raise MeshInvariantError("GET_RAW failed")
                raw_size = _safe_size(response["raw_size"], "raw_size")
                raw = reader.read(raw_size)
                if len(raw) != raw_size:
                    raise MeshInvariantError("truncated GET_RAW")
                reconstructed.extend(raw)

        verified = bytes(reconstructed) == data and hashlib.sha256(reconstructed).hexdigest() == object_digest
        if not verified:
            raise MeshInvariantError("TCP reconstruction failed")
        return TcpTransferReport(
            object_digest=object_digest,
            raw_object_bytes=len(data),
            chunks_total=len(parts),
            cache_hits=cache_hits,
            chunks_transmitted=chunks_sent,
            payload_bytes_transmitted=payload_bytes,
            wire_bytes_sent=wire_bytes,
            integrity_verified=True,
        )


def _json_line(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8") + b"\n"


def _read_json(reader: BinaryIO) -> dict:
    line = reader.readline(_MAX_HEADER + 1)
    if not line or len(line) > _MAX_HEADER or not line.endswith(b"\n"):
        raise MeshInvariantError("invalid response header")
    try:
        value = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MeshInvariantError("invalid response JSON") from exc
    if not isinstance(value, dict):
        raise MeshInvariantError("response must be object")
    return value


def _digest(value: object) -> str:
    if not isinstance(value, str) or len(value) != 64 or value.lower() != value:
        raise MeshInvariantError("invalid digest")
    if any(ch not in "0123456789abcdef" for ch in value):
        raise MeshInvariantError("invalid digest")
    return value


def _safe_size(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > _MAX_PAYLOAD:
        raise MeshInvariantError(f"invalid {name}")
    return value
