# AUTOPILOT V5 AI Node — SynergyNet Transport Binding v1

This generation binds the outer `synergy-autopilot-v5-ai-node` to the existing SynergyNet relay protocol while preserving NEXUS isolation.

## Bound transport

- node source commit: `c39f6f0ee0e37c08366a63ec160c580b9ae954ba`
- node integration root: `a793250aaa2299fdaf1661e985423c2b62687a19395ceabcc7bb63c005defe54`
- SynergyNet artifact: `7f22e68d80a7df879af71ebccdb45f8edb10cae3698bf07faa7076ce76fd0ef7`
- SynergyNet LocationEvidence v2: `c4102a8e668b79fc961a5f1767154154f4a600d320442770d74c7a006a5cee08`
- relay RuntimeSpec: `8c38cd130e3dd73723e3a3241d2df61bef218abdab2d16785ccec5b172fac4df`
- wire: `synergynet.relay-wire/v3`
- transport binding: `3c8198e10863c52c0492ca422c404a1e05e6fd2f48f4c393587d9d87eee3855f`

The binding scope is `OUTER_AUTOPILOT_NODE_ONLY`. The embedded exact NEXUS proof kernel remains `network_access=NONE`; it receives bounded evidence through the outer node and never owns a socket, arbitrary destination selector or remote filesystem path.

This is a protocol binding, not a live socket. Host address, port and peer directory remain deferred to a future Meta-OS HostProfile and static operator-local allowlist. Therefore `materialization_status=PROTOCOL_BOUND_HOST_ADDRESS_NOT_MATERIALIZED` and `auto_start=false`.

No financial/payment/accounting/blockchain/execution authority is granted by transport binding.
