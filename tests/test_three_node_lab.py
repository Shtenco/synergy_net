import hashlib

import pytest

from synergynet import MeshLab, PQProfile, chunk_bytes
from synergynet.lab import MeshInvariantError


def test_chunking_is_deterministic_and_reconstructs():
    data = (b"abc123" * 3000) + bytes(range(256)) * 10
    a = chunk_bytes(data)
    b = chunk_bytes(data)
    assert a == b
    assert b"".join(a) == data
    assert all(len(part) <= 8192 for part in a)


def test_three_node_transfer_deduplicates_repeated_content():
    mesh = MeshLab()
    data = (b"common-content\n" * 2000) + (b"Z" * 10000)
    first = mesh.transfer("node-a", "node-b", data)
    second = mesh.transfer("node-a", "node-b", data)
    third = mesh.transfer("node-a", "node-c", data)
    assert first.integrity_verified and third.integrity_verified
    assert first.chunks_transmitted > 0
    assert second.chunks_transmitted == 0
    assert second.cache_hits == second.chunks_total
    assert second.payload_bytes_transmitted == 0
    assert first.payload_bytes_transmitted <= first.raw_object_bytes


def test_similar_object_reuses_some_chunks_after_cache_seed():
    mesh = MeshLab()
    shared = b"S" * 20000
    original = shared + b"A" * 9000
    changed = shared + b"B" * 9000
    mesh.transfer("node-a", "node-c", original)
    report = mesh.transfer("node-b", "node-c", changed)
    assert report.cache_hits > 0
    assert report.payload_bytes_transmitted < report.naive_bytes


def test_chunk_tamper_is_detected():
    mesh = MeshLab()
    data = b"integrity" * 2000
    _, digests = mesh.publish("node-a", data)
    chunk = mesh.nodes["node-a"].chunks[digests[0]]
    object.__setattr__(chunk, "payload", chunk.payload + b"x")
    with pytest.raises((MeshInvariantError, Exception)):
        chunk.raw()


def test_pq_profile_is_explicitly_contract_only():
    profile = PQProfile()
    profile.validate()
    assert profile.kem.startswith("ML-KEM")
    assert profile.signature.startswith("ML-DSA")
    assert profile.implementation_status == "CRYPTO_AGILITY_CONTRACT_ONLY"
    with pytest.raises(MeshInvariantError):
        PQProfile(kem="FAKE-KEM").validate()
