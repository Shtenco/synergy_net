# SynergyNet BuildRecipe v2

This additive recipe follows the real runtime source generation and `synergy.service-spec/v2` without changing BuildRecipe v1.

It pins the exact parent source commit:

`d2f5256825f4ee3e878476556a427b3172cf5d31`

and both ServiceSpec v2 digests:

- `content-cache`: `5ace3018df97985f12d4c28da619b0598223eab34a710cac37d32edaf42ab1fd`
- `synergynet`: `42c8b0df5e55345bd6b6636dfd4fd311035bd2bca91a9613814beeac08984fce`

The target artifact remains one Python wheel, `synergynet==0.1.0`, which contains the two independently described runtime services.

## Deliberate blocker

The repository still declares:

`build-system.requires = ["setuptools>=68"]`

This is an open version range rather than an exact content-addressed toolchain lock. Therefore v2 must remain:

- `build_toolchain.status = NOT_FROZEN`
- `build_toolchain.lock_digest = null`
- `reproducibility_status = NOT_REPRODUCIBLE_TOOLCHAIN_NOT_FROZEN`
- `artifact_digest = null`
- `build_evidence_digest = null`
- `execution_authority = NONE`

The runtime interface work is real, but it does not erase the independent build reproducibility blocker.

The next reproducibility generation must freeze the actual build frontend/backend/tool versions and their artifact identities, build the same source more than once in controlled environments, compare wheel bytes or a normalized reproducible artifact representation, and emit independent build evidence. Until then a source commit or ServiceSpec digest cannot substitute for an artifact digest.
