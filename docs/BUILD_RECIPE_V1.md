# SynergyNet build recipe v1

This artifact freezes the current packaging assumptions for the SynergyNet persistent transport/cache candidate. It does not claim a reproducible wheel build yet.

Source identity:

- repository: `Shtenco/synergynet`
- source commit: `a8fde01c19420dbe63ca30e1da3b009c0c10064d`
- source role: `SYNERGYNET_TRANSPORT_AND_CACHE_CANDIDATE`
- package: `synergynet==0.1.0`
- artifact kind: `PYTHON_WHEEL`

The current package has no declared runtime dependencies, but its build-system requirement is still the open range `setuptools>=68` and there is no content-addressed build-toolchain lock. Therefore v1 deliberately requires:

- `build_toolchain.status = NOT_FROZEN`
- `build_toolchain.lock_digest = null`
- `reproducibility_status = NOT_REPRODUCIBLE_TOOLCHAIN_NOT_FROZEN`
- `artifact_digest = null`
- `execution_authority = NONE`

A later additive generation may freeze exact build-toolchain artifacts and attempt independent byte-for-byte wheel reproduction. This v1 remains source/package provenance and cannot be promoted by changing its outer hash.
