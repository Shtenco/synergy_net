# LEGACY DISTILLATION V2 — Import Queue

Canonical owner: `Shtenco/synergynet`

Nothing in this queue is auto-promoted to production. Every mechanism must pass the listed gate in this repository authority boundary.

| Priority | ID | Family | Action | Occurrences | Test gate | Representative |
|---|---|---|---|---:|---|---|
| P1_PROMOTE_WITH_GATE | M111 | NETWORK_P2P_TRANSPORT | PROMOTION_CANDIDATE | 74 | `authority_separation` | init_blockchain_db |
| P1_PROMOTE_WITH_GATE | M199 | VERIFICATION_SYBIL | PROMOTION_CANDIDATE | 24 | `adaptive_drift_and_quorum` | _verified_bloc_growth |
| P1_PROMOTE_WITH_GATE | M112 | NETWORK_P2P_TRANSPORT | PROMOTION_CANDIDATE | 12 | `authority_separation` | receiveTaskUpdate |
| P1_PROMOTE_WITH_GATE | M113 | NETWORK_P2P_TRANSPORT | PROMOTION_CANDIDATE | 9 | `authority_separation` | start_tunnel |
| P1_PROMOTE_WITH_GATE | M114 | NETWORK_P2P_TRANSPORT | PROMOTION_CANDIDATE | 8 | `authority_separation` | neighbors |
| P1_PROMOTE_WITH_GATE | M200 | VERIFICATION_SYBIL | PROMOTION_CANDIDATE | 4 | `adaptive_drift_and_quorum` | claimVested |
