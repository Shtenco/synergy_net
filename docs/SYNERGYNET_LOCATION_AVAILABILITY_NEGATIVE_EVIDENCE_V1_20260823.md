# SynergyNet current locator availability negative evidence v1

This additive evidence generation records a **current availability failure of the old connected-Drive locator**. It does not revoke or rewrite the artifact identity, BuildRecipe v3, BuildEvidence v1, previous LocationEvidence v2, transport binding, or the already executed LAB deployment evidence.

Negative-evidence root:

`2529d725e426c5028daab7346d1c704d643ffd209d35ceace7f7330203a6353f`

Pinned artifact:

- SHA-256 `7f22e68d80a7df879af71ebccdb45f8edb10cae3698bf07faa7076ce76fd0ef7`
- size `12,837`
- BuildRecipe v3 `37cb503fb8c6d5e8ef2305ce03d0332abee2d9eed5bb29f90364e20874d128df`
- BuildEvidence v1 `8c4f44f1b0b95221d660bb4a7c0598ada17e86f59bade16e85d93789bf1ddd8c`
- previous LocationEvidence v2 `c4102a8e668b79fc961a5f1767154154f4a600d320442770d74c7a006a5cee08`
- old provider file id `1zuB8rjKO0HHIZmvUEGZnAbnkKGNN59qp`.

Observed on 2026-08-23 through the current connected Drive context: the old provider file id returned NOT_FOUND. Therefore the current locator state is `UNRESOLVABLE_CURRENT_CONNECTION`.

## Exact effect

`DO_NOT_ASSUME_CURRENT_DRIVE_RESOLVABILITY`.

The artifact remains exactly identified and reproducible. Production now requires a **new durable locator generation plus fresh SHA-256/size verification** before the node can cross the production bootstrap gate.

This is intentionally additive: historical evidence that the binary existed at its old locator remains preserved as historical evidence. The new object only updates the present-time availability claim.
