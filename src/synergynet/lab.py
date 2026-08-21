from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import zlib


class MeshInvariantError(ValueError):
    pass


def _gear_table() -> tuple[int, ...]:
    values = []
    for i in range(256):
        digest = hashlib.sha256(f"SYNERGYNET-GEAR-{i}".encode()).digest()
        values.append(int.from_bytes(digest[:8], "big"))
    return tuple(values)


_GEAR = _gear_table()


@dataclass(frozen=True)
class Chunk:
    digest: str
    raw_size: int
    payload: bytes
    encoding: str

    def raw(self) -> bytes:
        if self.encoding == "raw":
            data = self.payload
        elif self.encoding == "zlib":
            data = zlib.decompress(self.payload)
        else:
            raise MeshInvariantError("unknown chunk encoding")
        if len(data) != self.raw_size:
            raise MeshInvariantError("chunk size mismatch")
        if hashlib.sha256(data).hexdigest() != self.digest:
            raise MeshInvariantError("chunk digest mismatch")
        return data


@dataclass
class ChunkStore:
    node_id: str
    chunks: dict[str, Chunk] = field(default_factory=dict)

    def has(self, digest: str) -> bool:
        return digest in self.chunks

    def put_raw(self, data: bytes) -> Chunk:
        digest = hashlib.sha256(data).hexdigest()
        compressed = zlib.compress(data, level=9)
        if len(compressed) < len(data):
            chunk = Chunk(digest, len(data), compressed, "zlib")
        else:
            chunk = Chunk(digest, len(data), data, "raw")
        self.chunks[digest] = chunk
        return chunk

    def put_chunk(self, chunk: Chunk) -> None:
        chunk.raw()
        self.chunks[chunk.digest] = chunk


@dataclass(frozen=True)
class PQProfile:
    schema: str = "synergynet.pq-profile/v1"
    kem: str = "ML-KEM-768"
    signature: str = "ML-DSA-65"
    classical_fallback: str = "X25519+Ed25519"
    implementation_status: str = "CRYPTO_AGILITY_CONTRACT_ONLY"

    def validate(self) -> None:
        if self.kem not in {"ML-KEM-768", "ML-KEM-1024"}:
            raise MeshInvariantError("unsupported KEM profile")
        if self.signature not in {"ML-DSA-65", "ML-DSA-87"}:
            raise MeshInvariantError("unsupported signature profile")
        if self.implementation_status != "CRYPTO_AGILITY_CONTRACT_ONLY":
            raise MeshInvariantError("v1 does not claim production PQ cryptography")


@dataclass(frozen=True)
class TransferReport:
    object_digest: str
    raw_object_bytes: int
    chunks_total: int
    cache_hits: int
    chunks_transmitted: int
    payload_bytes_transmitted: int
    naive_bytes: int
    integrity_verified: bool

    @property
    def bytes_saved(self) -> int:
        return self.naive_bytes - self.payload_bytes_transmitted



def chunk_bytes(data: bytes, *, min_size: int = 512, avg_size: int = 2048, max_size: int = 8192) -> list[bytes]:
    if not isinstance(data, (bytes, bytearray)):
        raise MeshInvariantError("content must be bytes")
    data = bytes(data)
    if not data:
        return [b""]
    if not (0 < min_size <= avg_size <= max_size):
        raise MeshInvariantError("invalid chunk-size policy")
    mask_bits = max(1, avg_size.bit_length() - 1)
    mask = (1 << mask_bits) - 1
    chunks: list[bytes] = []
    start = 0
    rolling = 0
    for index, byte in enumerate(data):
        rolling = ((rolling << 1) + _GEAR[byte]) & ((1 << 64) - 1)
        size = index - start + 1
        boundary = size >= min_size and ((rolling & mask) == 0 or size >= max_size)
        if boundary:
            chunks.append(data[start : index + 1])
            start = index + 1
            rolling = 0
    if start < len(data):
        chunks.append(data[start:])
    return chunks


class MeshLab:
    def __init__(self, node_ids: tuple[str, ...] = ("node-a", "node-b", "node-c")):
        if len(node_ids) != 3 or len(set(node_ids)) != 3:
            raise MeshInvariantError("v1 lab requires exactly three unique nodes")
        self.nodes = {node_id: ChunkStore(node_id) for node_id in node_ids}
        self.pq_profile = PQProfile()
        self.pq_profile.validate()

    def publish(self, source_node: str, data: bytes) -> tuple[str, list[str]]:
        store = self.nodes[source_node]
        chunk_digests = []
        for part in chunk_bytes(data):
            chunk_digests.append(store.put_raw(part).digest)
        return hashlib.sha256(data).hexdigest(), chunk_digests

    def transfer(self, source_node: str, target_node: str, data: bytes) -> TransferReport:
        if source_node == target_node:
            raise MeshInvariantError("source and target must differ")
        object_digest, digests = self.publish(source_node, data)
        source = self.nodes[source_node]
        target = self.nodes[target_node]
        cache_hits = 0
        transmitted = 0
        transmitted_bytes = 0
        reconstructed = bytearray()
        for digest in digests:
            if target.has(digest):
                cache_hits += 1
            else:
                chunk = source.chunks[digest]
                target.put_chunk(chunk)
                transmitted += 1
                transmitted_bytes += len(chunk.payload)
            reconstructed.extend(target.chunks[digest].raw())
        verified = hashlib.sha256(bytes(reconstructed)).hexdigest() == object_digest and bytes(reconstructed) == data
        if not verified:
            raise MeshInvariantError("reconstruction failed")
        return TransferReport(
            object_digest=object_digest,
            raw_object_bytes=len(data),
            chunks_total=len(digests),
            cache_hits=cache_hits,
            chunks_transmitted=transmitted,
            payload_bytes_transmitted=transmitted_bytes,
            naive_bytes=len(data),
            integrity_verified=True,
        )
