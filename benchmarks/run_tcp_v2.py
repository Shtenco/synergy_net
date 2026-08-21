from __future__ import annotations

import json

from synergynet.tcp_baseline import RawTcpSinkServer, send_raw_tcp
from synergynet.tcp_transport import TcpChunkServer, TcpContentClient


def main() -> None:
    data = ((b"SYNERGYNET-BENCHMARK-CONTENT-" * 512) + bytes(range(256))) * 16

    with RawTcpSinkServer() as raw_server:
        raw = send_raw_tcp(raw_server.address, data)

    with TcpChunkServer("benchmark-node") as content_server:
        client = TcpContentClient(content_server.address)
        cold = client.transfer(data)
        warm = client.transfer(data)

    output = {
        "schema": "synergynet.tcp-benchmark/v2",
        "scope": "LOOPBACK_APPLICATION_LAYER_ONLY",
        "raw_tcp": {
            "payload_bytes_sent": raw.payload_bytes_sent,
            "wire_bytes_sent": raw.wire_bytes_sent,
        },
        "content_cold": {
            "chunks_total": cold.chunks_total,
            "chunks_transmitted": cold.chunks_transmitted,
            "payload_bytes_transmitted": cold.payload_bytes_transmitted,
            "wire_bytes_sent": cold.wire_bytes_sent,
        },
        "content_warm": {
            "chunks_total": warm.chunks_total,
            "cache_hits": warm.cache_hits,
            "chunks_transmitted": warm.chunks_transmitted,
            "payload_bytes_transmitted": warm.payload_bytes_transmitted,
            "wire_bytes_sent": warm.wire_bytes_sent,
        },
        "claims": {
            "internet_superiority": "NOT_EVALUATED",
            "quic_comparison": "NOT_PERFORMED",
            "pq_transport": "NOT_IMPLEMENTED_IN_V2",
        },
    }
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
