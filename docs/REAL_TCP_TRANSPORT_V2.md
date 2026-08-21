# SynergyNet real TCP transport v2

V2 adds real loopback TCP framing while preserving the in-memory v1 lab unchanged.

## Protocol surface

The content server supports only three bounded operations:

- `HAS(digest)`
- `PUT(digest, raw_size, payload_size, encoding, payload)`
- `GET_RAW(digest)`

It does not expose filesystem paths, shell commands, dynamic imports or arbitrary object deserialization.

Every `PUT` is decoded and SHA-256 verified before the chunk enters the node cache.

## Baseline

`RawTcpSinkServer` sends the entire object over a real TCP socket and returns the receiver SHA-256. It exists only as an application-layer byte baseline.

## Benchmark semantics

The v2 benchmark reports:

- raw object bytes over TCP;
- cold-cache content payload bytes;
- warm-cache content payload bytes;
- application framing bytes sent by the content client.

It does **not** claim to measure Ethernet/IP/TCP header bytes, Internet latency, QUIC performance or production PQ security.

A repeated warm-cache transfer is expected to transmit zero chunk payload bytes, although small protocol request frames still cross the socket.

## Next gates

1. persistent content store;
2. codec adapter including validated `ai_compress` profiles;
3. TCP latency/goodput benchmark under controlled payload distributions;
4. QUIC baseline;
5. hybrid/PQ authenticated session implementation with external conformance evidence.
