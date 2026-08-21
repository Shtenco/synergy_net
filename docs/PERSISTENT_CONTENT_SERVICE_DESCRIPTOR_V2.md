# Persistent Content Service descriptor v2

The runtime implementation in `persistent_service_v1.py` is a persistent network-accessible content cache. It is **not yet a complete SynergyNet P2P relay** because it does not implement peer discovery, route selection, relay forwarding or multi-peer topology management.

Therefore descriptor v2 intentionally narrows the service to:

- `service_kind = CONTENT_CACHE`
- `required_capabilities = [CONTENT_CACHE]`

Descriptor v1 is preserved as historical design provenance but must not be used as the current federation candidate because it over-associated the service with `P2P_RELAY`.

The RESEARCH_COMPUTE_NODE architecture continues to require a separate `SYNERGYNET` / `P2P_RELAY` service. That service must be implemented and evidenced independently before the node can become deployable.

Current descriptor-v2 canonical SHA-256 over sorted compact JSON bytes (excluding no fields; the descriptor has no self-digest field):

`648f0b8bcbcff244e7dfd2e5d4d660e48a6c30dbbe9310e8f45b72dd73e35c63`

This clarification changes no prior code or historical artifact.
