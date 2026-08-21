# SynergyNet Static Peer Relay Service v1

This generation fills the separate `P2P_RELAY` role required by the RESEARCH_COMPUTE_NODE profile without pretending that the persistent content-cache endpoint is itself a relay.

## Data path

`RELAY_CHUNK(source_peer_id, destination_peer_id, chunk_digest)`

1. resolves both peer IDs through a **local operator-owned allowlist**;
2. fetches canonical raw bytes from the source content service;
3. verifies SHA-256 against the requested digest;
4. stores the same raw bytes at the destination content service;
5. verifies destination presence;
6. emits an immutable response containing source/destination IDs, digest and byte count.

## SSRF/open-proxy boundary

The request contains only peer IDs and a SHA-256 digest. It cannot supply:

- host;
- port;
- URL;
- filesystem path;
- shell/process command.

Network addresses are selected exclusively from the local static peer directory supplied by the node operator.

## Scope

V1 is deliberately `STATIC_ALLOWLISTED_PEERS_ONLY`.

It does not yet implement:

- peer discovery;
- DHT/routing tables;
- NAT traversal;
- multipath routing;
- congestion control beyond the underlying TCP services;
- production PQ sessions;
- Internet-wide performance claims.

Those are later SynergyNet generations and must be benchmarked independently.

## Authority

The relay moves content bytes only. It has:

- `payment_authority = NONE`
- `accounting_authority = NONE`
- `execution_authority = NONE`

The service descriptor still has `build_artifact_digest = null`, so the component remains a source candidate until a reproducible build is independently attested.

Current descriptor canonical SHA-256:

`0e4fe4aed2d4eb1339e930ccb7c7ce2d574acdd94c0759dbefd2167e61659e18`
