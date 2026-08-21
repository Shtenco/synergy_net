# SynergyNet Persistent Store / Codec Boundary v3

V3 separates **content identity**, **storage** and **wire encoding**.

## Invariants

- content identity is always `SHA-256(raw chunk bytes)`;
- the durable store persists canonical raw bytes, never codec-specific bytes;
- filenames derive only from validated lowercase SHA-256 digests;
- writes use fsync + atomic replace;
- every read re-hashes content;
- codecs must round-trip exactly before they can be selected;
- codec choice cannot change chunk identity;
- a restarted node retains warm-cache dedup state.

## Why codec payloads are not persisted as identity

Compression algorithms and versions will evolve. If object identity depended on zlib/zstd/AI-compress output, changing codecs would change the network object graph. V3 therefore makes codec output a transport optimization only.

## ai_compress integration

`Shtenco/ai_compress` is **not** invoked through shell/subprocess in this generation. A future adapter must implement the same byte-to-byte codec ABI, declare a version/artifact digest, pass deterministic round-trip tests and publish benchmark evidence before it can be preferred over standard codecs.

## Status

This generation proves durable local cache semantics. It does not yet prove production multi-host networking, QUIC, globally shared dedup state, production post-quantum sessions, or superiority over the public Internet.
