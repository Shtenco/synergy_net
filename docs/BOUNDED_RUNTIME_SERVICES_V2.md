# SynergyNet bounded runtime services v2

This additive generation turns the previously library-only transport/cache candidate into two real, bounded source-level services without claiming build reproducibility or deployment authority.

## content-cache

Entrypoint: `python -m synergynet.content_service_v2`

Wire protocol: `synergynet.content-wire/v2`

Allowed operations are exactly:

- `STATUS`
- `HAS`
- `PUT`
- `GET_RAW`

The service stores canonical raw bytes under `SHA256(raw bytes)`, reuses the durable `DirectoryChunkStore`, verifies decoded size and digest before commit, and never accepts filesystem paths or process commands over the wire.

Local operator configuration controls store root, bind host/port, maximum payload bytes and maximum concurrent connections. Remote peers cannot set those values.

`STATUS` reports `READY`, protocol identity and configured resource ceilings. SIGINT/SIGTERM cause an orderly server shutdown.

## synergynet relay

Entrypoint: `python -m synergynet.relay_service_v2`

Wire protocol: `synergynet.relay-wire/v2`

Allowed operations are exactly:

- `STATUS`
- `RELAY_CHUNK`

A relay request can name only a request id, source peer id, destination peer id and SHA-256 chunk digest. Host, port, URL, path and command fields are rejected by exact-shape validation.

Peer addresses come only from the local operator-owned `synergynet.static-peer-directory/v2` allowlist. V2 deliberately remains static-peer only: discovery, DHT, NAT traversal, multipath and production PQ sessions are later generations.

Relay integrity is end-to-end: fetch exact raw bytes from the allowlisted source content service, verify SHA-256, commit the same bytes to the allowlisted destination, then verify destination presence.

## Authority and evidence state

This branch is source implementation evidence only.

- `source_status = IMPLEMENTED_NOT_FROZEN`
- `build_artifact_digest = null`
- `build_evidence_digest = null`
- `execution_authority = NONE`

A later additive generation must freeze the exact commit that contains these services and issue `synergy.service-spec/v2`. A later build recipe/evidence generation must then produce reproducible artifact bytes. Meta-OS execution admission remains a separate final gate.

The prior `synergy.service-spec/v1` library-only generation remains immutable provenance; it is not edited or reinterpreted.
