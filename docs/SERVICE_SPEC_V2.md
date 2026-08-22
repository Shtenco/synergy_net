# SynergyNet ServiceSpec v2

This additive generation follows the immutable library-only `synergy.service-spec/v1` and the bounded runtime source generation in PR #10.

It freezes the exact parent runtime commit:

`aa93e18bdeb84a8475419cde83f149c8381428cd`

and the canonical `synergynet.runtime-source/v2` manifest digest:

`d8be0a9023111df54c49704e9a0fea07d0fc5cac5a1a333d1c7bfac7a3708930`

## What changes

The service interface is no longer hypothetical.

### content-cache

- runtime form: `PYTHON_SERVICE`
- entrypoint: `python -m synergynet.content_service_v2`
- health: `STATUS_EXPECT_READY`
- lifecycle: `SIGINT_SIGTERM_GRACEFUL_SHUTDOWN`
- wire: `synergynet.content-wire/v2`
- capability: `CONTENT_CACHE`

### synergynet

- runtime form: `PYTHON_SERVICE`
- entrypoint: `python -m synergynet.relay_service_v2`
- health: `STATUS_EXPECT_READY`
- lifecycle: `SIGINT_SIGTERM_GRACEFUL_SHUTDOWN`
- wire: `synergynet.relay-wire/v2`
- capability: `P2P_RELAY`

Both therefore have:

`interface_status = SERVICE_INTERFACE_IMPLEMENTED_SOURCE_ONLY`

## What does not change

ServiceSpec v2 deliberately does not claim reproducible artifacts or deployment permission:

- `build_artifact_digest = null`
- `build_evidence_digest = null`
- `execution_authority = NONE`

So the implication is deliberately one-way:

`SERVICE_INTERFACE_IMPLEMENTED_SOURCE_ONLY`

**does not imply**

`BUILD_VERIFIED`, `DEPLOYABLE`, or `EXECUTION_AUTHORIZED`.

A later domain-owned BuildRecipe v2 must freeze the exact toolchain/dependency graph and produce independently checked artifact bytes. The architecture root may then consume those new facts in an additive NodeBuildPlan/NodeReadiness generation. Meta-OS remains the final owner of process admission.

The v1 library-only specs stay correct historical provenance for their older source commit and are never edited to pretend they described this newer code.
