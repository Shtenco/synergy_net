from __future__ import annotations

import json
from pathlib import Path

from synergynet import MeshLab


def main() -> None:
    mesh = MeshLab()
    shared = (b"SYNERGY-NET-COMMON-BLOCK\n" * 600) + (b"A" * 7000)
    object_a = shared + (b"node-a-unique\n" * 300)
    object_b = shared + (b"node-b-unique\n" * 300)

    first = mesh.transfer("node-a", "node-b", object_a)
    second = mesh.transfer("node-a", "node-c", object_a)
    # Seed node C with A, then transfer B so content-defined overlap becomes cache hits.
    third = mesh.transfer("node-b", "node-c", object_b)

    report = {
        "schema": "synergynet.three-node-benchmark/v1",
        "claims": {
            "internet_speed_superiority": "NOT_CLAIMED",
            "production_pq_security": "NOT_CLAIMED",
            "content_integrity": "VERIFIED_BY_SHA256",
        },
        "transfers": [
            first.__dict__ | {"bytes_saved": first.bytes_saved},
            second.__dict__ | {"bytes_saved": second.bytes_saved},
            third.__dict__ | {"bytes_saved": third.bytes_saved},
        ],
    }
    out = Path("benchmark_output")
    out.mkdir(exist_ok=True)
    (out / "three_node_lab_v1.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
