# SynergyNet Persistent Content Service v1

This generation turns the already verified persistent content store into a bounded service candidate without changing prior transport/store implementations.

## Purpose

Expose only content-addressed raw-byte storage operations required by a future `RESEARCH_COMPUTE_NODE`:

- `STATUS`
- `HAS`
- `PUT`
- `GET_RAW`

The network protocol never accepts filesystem paths, process commands, shell fragments, repository refs or arbitrary method names.

## Storage invariant

The canonical object identity is always:

`SHA256(raw chunk bytes)`

Wire compression is representation only. A payload may use an allowlisted codec, but the service decodes it, verifies `raw_size`, verifies SHA-256, and only then commits canonical raw bytes through `DirectoryChunkStore`.

## Local configuration vs wire authority

`--store`, `--host` and `--port` are local operator configuration. They are not network request fields.

A future Meta-OS process adapter must provide these arguments from an allowlisted service manifest/profile; remote peers never choose them.

## Safety boundary

This service:

- does not run arbitrary commands;
- does not accept a network filesystem path;
- does not grant payment/accounting/financial authority;
- does not make the PQ transport production-ready;
- does not claim Internet-wide performance;
- does not grant execution authority merely because the service descriptor verifies.

`execution_authority = NONE` in the service descriptor means that this repository defines a service candidate, not that Meta-OS is authorized to spawn it yet.

## Build state

The descriptor intentionally contains:

- `build_artifact_digest = null`
- `build_status = SERVICE_SOURCE_CANDIDATE_NOT_BUILD_VERIFIED`

The next build-verification generation must be based on a reproducible artifact and independent evidence. A Git commit is not a deployable binary/package digest.
