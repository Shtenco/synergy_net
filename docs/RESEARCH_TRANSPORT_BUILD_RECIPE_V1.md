# Research Transport build recipe v1

This generation deterministically packages the exact SynergyNet service candidate frozen at commit `874a83b6510420ec43ce99fc4b7936e106ad2339`.

One artifact contains the two research-node service roles that share the same runtime foundation:

- `CONTENT_CACHE` via `synergynet.persistent_service_v1`;
- `SYNERGYNET` relay via `synergynet.static_relay_v1`.

All packaged files are allowlisted and verified from raw bytes against their frozen Git blob identities. Archive entries are sorted, stored without compression, use a fixed timestamp and fixed permissions. Content identity remains SHA-256 of the resulting deterministic artifact; it does not grant network/payment/accounting/execution authority.

The runtime is Python-stdlib only. This removes the third-party dependency-lock blocker present in NEXUS, but the artifact still does not become `BUILD_VERIFIED` merely because the recipe exists. A runner must actually execute protocol tests and produce reproducible artifact/evidence bytes.

The same artifact digest may later be referenced by both `content-cache` and `synergynet` service entries in a Meta-OS build lock, while their service kinds/capabilities remain distinct.
