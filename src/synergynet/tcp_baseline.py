from __future__ import annotations

from dataclasses import dataclass
import hashlib
import socket
import socketserver
import threading

from .lab import MeshInvariantError

_MAX_OBJECT = 64 * 1024 * 1024


class _RawHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        header = _recv_exact(self.request, 8)
        size = int.from_bytes(header, "big")
        if size < 0 or size > _MAX_OBJECT:
            return
        payload = _recv_exact(self.request, size)
        digest = hashlib.sha256(payload).digest()
        self.server.last_digest = digest.hex()  # type: ignore[attr-defined]
        self.server.last_size = size  # type: ignore[attr-defined]
        self.request.sendall(digest)


class _RawServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address: tuple[str, int]):
        self.last_digest: str | None = None
        self.last_size: int | None = None
        super().__init__(address, _RawHandler)


class RawTcpSinkServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        self._server = _RawServer((host, port))
        self._thread: threading.Thread | None = None

    @property
    def address(self) -> tuple[str, int]:
        host, port = self._server.server_address[:2]
        return str(host), int(port)

    def start(self) -> "RawTcpSinkServer":
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

    def __enter__(self) -> "RawTcpSinkServer":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


@dataclass(frozen=True)
class RawTcpReport:
    object_digest: str
    payload_bytes_sent: int
    wire_bytes_sent: int
    server_verified: bool


def send_raw_tcp(address: tuple[str, int], data: bytes, timeout: float = 5.0) -> RawTcpReport:
    if len(data) > _MAX_OBJECT:
        raise MeshInvariantError("object exceeds v2 raw TCP benchmark limit")
    expected = hashlib.sha256(data).digest()
    with socket.create_connection(address, timeout=timeout) as sock:
        header = len(data).to_bytes(8, "big")
        sock.sendall(header)
        sock.sendall(data)
        reply = _recv_exact(sock, 32)
    if reply != expected:
        raise MeshInvariantError("raw TCP sink digest mismatch")
    return RawTcpReport(
        object_digest=expected.hex(),
        payload_bytes_sent=len(data),
        wire_bytes_sent=len(data) + 8,
        server_verified=True,
    )


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        part = sock.recv(remaining)
        if not part:
            raise MeshInvariantError("truncated TCP payload")
        chunks.append(part)
        remaining -= len(part)
    return b"".join(chunks)
