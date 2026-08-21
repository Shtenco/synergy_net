# SynergyNet v2 real transport plan

The next generation must move from the deterministic in-memory lab to real transport without changing v1 evidence.

Sequence:

1. loopback TCP baseline with explicit framing and byte counters;
2. content-addressed protocol over TCP;
3. cold-cache vs warm-cache benchmark;
4. codec adapter interface (`raw`, `zlib`, later `ai_compress`);
5. persistent local content store;
6. only then QUIC baseline and multipath experiments;
7. audited PQ/hybrid session implementation as a separate cryptographic generation.

No claim of Internet-wide superiority is permitted before comparable TCP/QUIC benchmark evidence exists.
