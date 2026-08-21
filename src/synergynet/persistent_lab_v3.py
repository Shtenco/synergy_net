from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

from .lab import chunk_bytes
from .storage_v3 import CodecRegistry, DirectoryChunkStore


@dataclass(frozen=True)
class PersistentTransferReport:
    object_digest: str
    raw_object_bytes: int
    chunks_total: int
    cache_hits: int
    chunks_transmitted: int
    encoded_payload_bytes: int
    reconstructed: bool


class PersistentMeshNode:
    def __init__(self, node_id: str, root: str | Path, codecs: CodecRegistry | None = None):
        if not isinstance(node_id, str) or not node_id:
            raise ValueError("node_id is required")
        self.node_id = node_id
        self.store = DirectoryChunkStore(root)
        self.codecs = codecs or CodecRegistry()


def transfer(source: PersistentMeshNode, target: PersistentMeshNode, data: bytes) -> PersistentTransferReport:
    if source.node_id == target.node_id:
        raise ValueError("source and target must differ")
    data = bytes(data)
    parts = chunk_bytes(data)
    digests: list[str] = []
    transmitted = 0
    payload_bytes = 0
    hits = 0
    for part in parts:
        digest = source.store.put(part)
        digests.append(digest)
        if target.store.has(digest):
            hits += 1
            continue
        encoded = source.codecs.encode_best(source.store.get(digest))
        decoded = source.codecs.get(encoded.codec).decode(encoded.payload)
        if hashlib.sha256(decoded).hexdigest() != digest:
            raise ValueError("codec changed chunk identity")
        target.store.put(decoded)
        transmitted += 1
        payload_bytes += len(encoded.payload)

    rebuilt = b"".join(target.store.get(digest) for digest in digests)
    object_digest = hashlib.sha256(data).hexdigest()
    ok = rebuilt == data and hashlib.sha256(rebuilt).hexdigest() == object_digest
    if not ok:
        raise ValueError("persistent reconstruction failed")
    return PersistentTransferReport(
        object_digest=object_digest,
        raw_object_bytes=len(data),
        chunks_total=len(parts),
        cache_hits=hits,
        chunks_transmitted=transmitted,
        encoded_payload_bytes=payload_bytes,
        reconstructed=True,
    )
