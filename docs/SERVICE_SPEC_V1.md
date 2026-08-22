# SynergyNet service specifications v1

This generation records a deliberate service-readiness gap for the first persistent transport/cache candidate.

The current package contains useful transport, chunk/cache and codec building blocks, but it does not yet expose package-level Meta-OS service interfaces. Therefore two logical services are described separately while both remain library-only:

- `synergynet` / `SYNERGYNET` / capability `P2P_RELAY`
- `content-cache` / `CONTENT_CACHE` / capability `CONTENT_CACHE`

For both services v1 requires:

- `runtime_form = PYTHON_LIBRARY_ONLY`
- `entrypoint = null`
- `health_probe = null`
- `lifecycle_protocol = null`
- `wire_protocol = null`
- `readiness_status = SERVICE_INTERFACE_NOT_IMPLEMENTED`
- `execution_authority = NONE`

Keeping transport and cache as separate service IDs allows future generations to define independent lifecycle, health and scaling semantics even if they initially share one package artifact.

A future additive service generation must implement bounded entrypoints and health/lifecycle/wire contracts before Meta-OS may consider the artifacts runnable. Reproducible wheel identity alone is not sufficient.
