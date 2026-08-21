from synergynet.tcp_baseline import RawTcpSinkServer, send_raw_tcp
from synergynet.tcp_transport import TcpChunkServer, TcpContentClient


def _payload() -> bytes:
    block = (b"SYNERGY-NET-CONTENT-" * 256) + bytes(range(256))
    return block * 8


def test_raw_tcp_baseline_sends_full_object():
    data = _payload()
    with RawTcpSinkServer() as server:
        report = send_raw_tcp(server.address, data)
    assert report.payload_bytes_sent == len(data)
    assert report.wire_bytes_sent == len(data) + 8
    assert report.server_verified is True


def test_content_transport_cold_then_warm_cache():
    data = _payload()
    with TcpChunkServer("node-b") as server:
        client = TcpContentClient(server.address)
        cold = client.transfer(data)
        warm = client.transfer(data)

    assert cold.integrity_verified is True
    assert cold.chunks_transmitted > 0
    assert cold.payload_bytes_transmitted > 0
    assert cold.payload_bytes_transmitted <= len(data)

    assert warm.integrity_verified is True
    assert warm.chunks_transmitted == 0
    assert warm.payload_bytes_transmitted == 0
    assert warm.cache_hits == warm.chunks_total


def test_content_transport_reuses_partial_chunks():
    base = _payload()
    changed = base[: len(base) // 2] + b"NEW-TAIL-" * 512
    with TcpChunkServer("node-c") as server:
        client = TcpContentClient(server.address)
        first = client.transfer(base)
        second = client.transfer(changed)

    assert first.chunks_transmitted == first.chunks_total
    assert 0 < second.cache_hits < second.chunks_total
    assert second.chunks_transmitted < second.chunks_total
