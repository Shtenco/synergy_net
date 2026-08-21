# SYNERGYNET

**Post-quantum P2P mesh and content-transport layer for SYNERGY nodes.**

Architecture root: `Shtenco/synergy_system`  
Compression source: `Shtenco/ai_compress`  
Target node orchestrator: `Shtenco/synergy_meta_os`  
Target host: `Shtenco/turbo_linux`

## Role

SynergyNet is a planned network overlay in which a node can act as client, server, router, relay and content cache.

A SYNERGY blockchain/financial/autopilot node may also run SynergyNet, but **network participation alone never grants financial, validator or treasury authority**.

## Target architecture

```text
Application Object / Stream / Packet
        ↓
Canonical Framing
        ↓
Content-Defined Chunking
        ↓
Content Hash
        ↓
Local Deduplication
        ↓
Network-Wide Dedup / Cache Lookup
        ↓
Compression Profile Selection
        ↓
Post-Quantum Authenticated Session Protection
        ↓
Multipath Route Selection
        ↓
P2P Relay / Store-and-Forward / Direct Path
        ↓
Receiver Cache
        ↓
Decompression / Reconstruction
        ↓
Hash + Integrity Verification
```

## Main research hypothesis

Repeated content across users/nodes can reduce network traffic when the network exchanges content identities/chunks instead of retransmitting identical bytes, especially when combined with domain-appropriate lossless compression from `ai_compress`.

This is a hypothesis to benchmark, not a performance claim.

## Node capabilities

Possible node profiles:

```text
CLIENT
RELAY
CACHE
GATEWAY
BLOCKCHAIN_PEER
NEXUS_COMPUTE
METAPAY_EDGE
FULL_SYNERGY_NODE
```

Roles must be explicit and separately authorized.

## Content-addressed transport

Recommended object model:

```text
Object Manifest
  ├─ object hash
  ├─ ordered chunk hashes
  ├─ original size
  ├─ codec/profile id
  ├─ compression metadata
  ├─ optional erasure coding metadata
  └─ integrity/signature metadata
```

A node that already possesses a chunk should not download the same chunk again merely because another logical object references it.

## Deduplication layers

```text
L0 process-local cache
L1 node-local content store
L2 trusted/LAN peer cache
L3 wider mesh distributed cache / DHT-like discovery
```

Privacy policy must constrain what content hashes or cache-presence information can be exposed to peers.

## Compression integration

`ai_compress` is the technology source for validated codecs and archive research.

SynergyNet needs a network-specific codec policy because best archive ratio is not necessarily best network performance.

Selection should optimize a cost function such as:

```text
network_cost =
    bytes_on_wire
  + encode_cpu_cost
  + decode_cpu_cost
  + latency_penalty
  + memory_penalty
  + cache_amplification
```

Possible profiles may use raw/no compression, established external codecs and validated SYNERGY codecs. Every selected profile must preserve exact reconstruction where the transport contract is lossless.

## Post-quantum security target

The project targets post-quantum-ready identity/session security, but must use reviewable standard primitives and explicit algorithm/version negotiation.

Security layers should distinguish:

- node identity;
- session key establishment;
- packet/message authentication;
- content integrity;
- blockchain keys;
- financial/payment keys.

A network identity key must not automatically become a treasury or validator key.

## Routing target

Research areas:

- direct peer discovery;
- relay routing;
- multipath transport;
- latency/loss-aware routing;
- store-and-forward for intermittent nodes;
- congestion control;
- NAT traversal;
- local-first routing;
- optional erasure coding;
- content-aware route/cache selection.

## Performance constitution

The network must not call itself “the fastest Internet” without matched evidence.

Required benchmark dimensions:

```text
latency
throughput
goodput
bytes transmitted
compression ratio
encode/decode CPU
memory
packet loss tolerance
recovery time
cache hit rate
dedup savings
first-byte latency
energy/resource cost where measurable
```

Compare against explicit baselines such as conventional TCP/HTTP, QUIC/HTTP3 and a selected P2P/content-distribution baseline under the same hardware/network impairment profile.

## Privacy and abuse resistance

A global dedup/cache network can leak information if designed naively. Research must consider:

- private/salted content addressing where needed;
- encrypted content and access control;
- cache-probing resistance;
- peer reputation / abuse controls;
- bandwidth/resource quotas;
- spam/Sybil resistance;
- metadata minimization.

## Initial repository structure

```text
synergynet/
  protocol/
  identity/
  session/
  framing/
  chunking/
  content_store/
  dedup/
  compression/
  routing/
  discovery/
  transport/
  cache/
  simulation/
  benchmarks/
  evidence/
  tests/
```

## First milestone

Build a local 3–10 node testbed that can:

1. establish authenticated sessions;
2. transfer a content-addressed object;
3. deduplicate repeated chunks across transfers;
4. negotiate a compression profile;
5. reconstruct bytes exactly;
6. switch between direct and relay paths;
7. survive controlled loss/reordering;
8. export raw benchmark evidence against a conventional baseline.

Only after this should larger “new Internet” performance claims be evaluated.

## Principle

**SynergyNet moves and deduplicates verified information. It does not create economic or consensus authority merely because it transports the bytes.**
