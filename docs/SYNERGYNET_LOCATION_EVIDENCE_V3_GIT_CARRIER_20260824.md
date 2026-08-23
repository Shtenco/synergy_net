# SynergyNet Artifact LocationEvidence v3

This generation remediates the unavailable historical Drive locator without changing the proven SynergyNet artifact identity.

## Exact artifact
- SHA-256: `7f22e68d80a7df879af71ebccdb45f8edb10cae3698bf07faa7076ce76fd0ef7`
- size: `12,837`
- artifact manifest: `fde462820a5d8a1b8c48c565a1ccd5fa3a72a9f36a2deec5305af3ce021d4de6`
- BuildRecipe v3: `37cb503fb8c6d5e8ef2305ce03d0332abee2d9eed5bb29f90364e20874d128df`
- BuildEvidence v1: `8c4f44f1b0b95221d660bb4a7c0598ada17e86f59bade16e85d93789bf1ddd8c`

## New durable locator
The exact historical base64 carrier blobs are rebound under a new Git tree/branch so locator durability no longer depends on the unavailable Drive file ID.

- durable branch: `feat/location-evidence-v3-git-carrier-20260824`
- durable commit: `5fd3d2b7e2ce934c32fcc5221cddb343c9742a69`
- durable tree: `3c5fcbc3dca75967544add4b99a5f17b5f933bfc`
- carrier manifest Git blob: `0b59c384a0ce86f344cc6cb62c20955d09afff1e`
- carrier manifest digest: `28b7069e0715145d5821ea2106de9f8f2f86c45ddc52c97b386b3c6fc86b6528`
- LocationEvidence v3: `b1ca1c1f5849deac30a0aac14748c21b8a74a26776ba2134a448c9427a839220`

Resolution is fail-closed: read the six immutable blob-backed chunks in ordinal order, verify each chunk SHA-256 and length, concatenate ASCII, strict-base64 decode, then verify final artifact SHA-256 and size.

The old Drive unavailability evidence `2529d725e426c5028daab7346d1c704d643ffd209d35ceace7f7330203a6353f` remains preserved. v3 supersedes only the current locator, not BuildEvidence or historical LAB execution.

`execution_authority=NONE`.
