from pathlib import Path

import pytest

from synergynet.persistent_lab_v3 import PersistentMeshNode, transfer
from synergynet.storage_v3 import CodecRegistry, DirectoryChunkStore, StorageInvariantError


def test_store_survives_restart_and_reverifies_hash(tmp_path: Path):
    root = tmp_path / "store"
    first = DirectoryChunkStore(root)
    digest = first.put(b"persistent-bytes" * 100)
    second = DirectoryChunkStore(root)
    assert second.has(digest)
    assert second.get(digest) == b"persistent-bytes" * 100


def test_store_detects_on_disk_corruption(tmp_path: Path):
    store = DirectoryChunkStore(tmp_path / "store")
    digest = store.put(b"hello")
    path = store.root / digest[:2] / digest[2:]
    path.write_bytes(b"evil")
    with pytest.raises(StorageInvariantError):
        store.get(digest)


def test_codec_registry_uses_smallest_roundtrip_payload():
    encoded = CodecRegistry().encode_best(b"A" * 10_000)
    assert encoded.codec == "zlib-9"
    assert len(encoded.payload) < encoded.raw_size


def test_warm_cache_remains_warm_after_target_restart(tmp_path: Path):
    source = PersistentMeshNode("a", tmp_path / "a")
    target = PersistentMeshNode("b", tmp_path / "b")
    data = (b"shared-header:" + b"x" * 4000 + b"\n") * 20
    cold = transfer(source, target, data)
    assert cold.chunks_transmitted > 0
    assert cold.encoded_payload_bytes > 0

    restarted_target = PersistentMeshNode("b", tmp_path / "b")
    warm = transfer(source, restarted_target, data)
    assert warm.chunks_transmitted == 0
    assert warm.encoded_payload_bytes == 0
    assert warm.cache_hits == warm.chunks_total


def test_digests_cannot_be_used_as_paths(tmp_path: Path):
    store = DirectoryChunkStore(tmp_path / "store")
    for bad in ("../x", "A" * 64, "z" * 64, "0" * 63):
        with pytest.raises(StorageInvariantError):
            store.has(bad)
