# SynergyNet Research Transport Build Readiness v1

This contract freezes what is actually available for the Research Compute Node from SynergyNet today.

Frozen source identity:
- repository `Shtenco/synergynet`
- source commit `a8fde01c19420dbe63ca30e1da3b009c0c10064d`
- content-defined chunking/content identity
- in-process TCP transport
- persistent raw-byte content store
- codec ABI and persistent transfer lab

Positive evidence:
- current runtime path uses Python standard library only
- the v2 TCP server is bounded and content-addressed
- the v3 store persists canonical raw bytes and re-hashes on read

Still missing for a deployable Meta-OS service:
- a single daemon entrypoint that composes TCP transport with the persistent backend
- a versioned daemon configuration contract
- a reproducibly built service artifact digest
- process lifecycle integration with Meta-OS

Therefore v1 remains:

`IN_PROCESS_SERVER_NOT_DAEMON_ENTRYPOINT`

Canonical readiness digest:

`a41c5bf58ff85ee1b4efafc3975ca975f2ca1c59a020aca056e7351e71659a0e`

No build-readiness artifact grants execution authority.
