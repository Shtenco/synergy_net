# SynergyNet three-node lab v1

## Purpose

Measure properties that are actually implemented before making Internet-speed or post-quantum production claims.

The lab has exactly three logical nodes. Each node is a client/server/cache in the simulation.

```text
bytes
→ deterministic content-defined chunks
→ SHA-256 identity
→ local target cache lookup
→ zlib only when encoded bytes are smaller
→ transfer missing encoded chunks
→ decode
→ SHA-256 + byte equality reconstruction
```

## Measurements

For every transfer the benchmark records:

- raw object bytes;
- total chunk count;
- target cache hits;
- transmitted chunk count;
- actual encoded payload bytes transmitted;
- naive whole-object bytes;
- bytes avoided by cache/compression;
- end-to-end integrity result.

It does not yet model wire framing, congestion control, RTT, packet loss, CPU energy or real sockets, so it cannot support a claim that SynergyNet is faster than QUIC/TCP.

## PQ boundary

`PQProfile` names the target crypto-agility suite (`ML-KEM` + `ML-DSA`) but v1 deliberately has `implementation_status=CRYPTO_AGILITY_CONTRACT_ONLY`.

Production PQ status requires an audited implementation, KAT/conformance evidence, downgrade protection, key lifecycle, hybrid-transition policy and network benchmark under encrypted sessions.

## Next benchmark generation

The next version should compare over real sockets:

1. raw TCP;
2. QUIC/HTTP3 baseline;
3. content-addressed transport without compression;
4. content-addressed + standard compression;
5. content-addressed + selected `ai_compress` codec;
6. cold cache vs warm cache;
7. repeated multi-node corpus.
