from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile


RECIPE_RELATIVE_PATH = "config/synergynet_source_capsule_recipe_v1.json"
EXPECTED_RECIPE_DIGEST = "5202b60cd607a8c88f97aa4cd5b9ba9ed6c304715f445f32cc610fcd61ee2bd3"
FIXED_ZIP_DATETIME = (1980, 1, 1, 0, 0, 0)
MANIFEST_NAME = "CAPSULE_MANIFEST.json"


class CapsuleBuildError(ValueError):
    pass


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _recipe_digest(recipe: dict[str, object]) -> str:
    body = dict(recipe)
    body.pop("recipe_digest", None)
    return _sha256(canonical_json_bytes(body))


def _validate_relative_path(raw: object) -> str:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise CapsuleBuildError("capsule path must be non-empty POSIX relative path")
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise CapsuleBuildError("capsule path traversal/absolute path forbidden")
    return path.as_posix()


def load_and_verify_recipe(root: Path) -> dict[str, object]:
    recipe = json.loads((root / RECIPE_RELATIVE_PATH).read_text(encoding="utf-8"))
    expected_fields = {
        "schema", "recipe_id", "artifact_kind", "archive_format", "fixed_timestamp",
        "source_paths", "dependency_manifest", "dependency_lock_status", "output_name",
        "build_evidence_status", "execution_authority", "recipe_digest"
    }
    if not isinstance(recipe, dict) or set(recipe) != expected_fields:
        raise CapsuleBuildError("unexpected source-capsule recipe shape")
    if recipe["schema"] != "synergynet.source-capsule-recipe/v1":
        raise CapsuleBuildError("unexpected source-capsule recipe schema")
    if recipe["recipe_id"] != "SYNERGYNET_RESEARCH_TRANSPORT_SOURCE_CAPSULE_V1":
        raise CapsuleBuildError("unexpected source-capsule recipe id")
    if recipe["artifact_kind"] != "NON_EXECUTABLE_DETERMINISTIC_SOURCE_CAPSULE":
        raise CapsuleBuildError("source capsule cannot claim executable artifact kind")
    if recipe["archive_format"] != "ZIP_STORED_FIXED_TIMESTAMP" or recipe["fixed_timestamp"] != "1980-01-01T00:00:00Z":
        raise CapsuleBuildError("unexpected deterministic archive profile")
    paths = recipe["source_paths"]
    if not isinstance(paths, list) or not paths:
        raise CapsuleBuildError("source paths required")
    normalized = [_validate_relative_path(item) for item in paths]
    if normalized != sorted(set(normalized)):
        raise CapsuleBuildError("source paths must be sorted and unique")
    if RECIPE_RELATIVE_PATH not in normalized:
        raise CapsuleBuildError("recipe must be included in its own source capsule")
    if recipe["dependency_manifest"] is not None:
        raise CapsuleBuildError("stdlib-only v1 must not invent dependency manifest")
    if recipe["dependency_lock_status"] != "STDLIB_ONLY_DEPENDENCIES_INTERPRETER_NOT_PINNED":
        raise CapsuleBuildError("v1 must disclose unpinned interpreter/OS environment")
    if recipe["output_name"] != "synergynet_research_transport_source_v1.zip":
        raise CapsuleBuildError("unexpected capsule output name")
    if recipe["build_evidence_status"] != "NOT_EXECUTED" or recipe["execution_authority"] != "NONE":
        raise CapsuleBuildError("recipe cannot overclaim build/execution evidence")
    supplied = recipe["recipe_digest"]
    recomputed = _recipe_digest(recipe)
    if supplied != recomputed or recomputed != EXPECTED_RECIPE_DIGEST:
        raise CapsuleBuildError("source-capsule recipe digest mismatch")
    return recipe


def _read_source(root: Path, relative: str) -> bytes:
    candidate = root / relative
    if candidate.is_symlink():
        raise CapsuleBuildError(f"symlink source forbidden: {relative}")
    resolved_root = root.resolve()
    resolved = candidate.resolve(strict=True)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise CapsuleBuildError(f"source escapes repository root: {relative}") from exc
    if not resolved.is_file():
        raise CapsuleBuildError(f"source is not a regular file: {relative}")
    return resolved.read_bytes()


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(filename=name, date_time=FIXED_ZIP_DATETIME)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    info.flag_bits = 0
    return info


def build_capsule_bytes(root: Path) -> tuple[bytes, dict[str, object]]:
    root = Path(root)
    recipe = load_and_verify_recipe(root)
    source_data: dict[str, bytes] = {}
    records: list[dict[str, object]] = []
    for raw in recipe["source_paths"]:  # type: ignore[index]
        relative = _validate_relative_path(raw)
        data = _read_source(root, relative)
        source_data[relative] = data
        records.append({"path": relative, "bytes": len(data), "sha256": _sha256(data)})

    manifest_body: dict[str, object] = {
        "schema": "synergynet.source-capsule-manifest/v1",
        "recipe_digest": recipe["recipe_digest"],
        "artifact_kind": recipe["artifact_kind"],
        "archive_format": recipe["archive_format"],
        "fixed_timestamp": recipe["fixed_timestamp"],
        "dependency_lock_status": recipe["dependency_lock_status"],
        "files": records,
        "execution_authority": "NONE",
    }
    manifest = dict(manifest_body)
    manifest["manifest_digest"] = _sha256(canonical_json_bytes(manifest_body))
    entries = dict(source_data)
    entries[MANIFEST_NAME] = canonical_json_bytes(manifest) + b"\n"

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        for name in sorted(entries):
            archive.writestr(_zip_info(name), entries[name])
    return buffer.getvalue(), manifest


def verify_capsule_bytes(capsule: bytes) -> dict[str, object]:
    with zipfile.ZipFile(io.BytesIO(capsule), "r") as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if names != sorted(names) or len(names) != len(set(names)):
            raise CapsuleBuildError("capsule entries must be sorted and unique")
        if MANIFEST_NAME not in names:
            raise CapsuleBuildError("capsule manifest missing")
        for info in infos:
            _validate_relative_path(info.filename)
            if info.date_time != FIXED_ZIP_DATETIME or info.compress_type != zipfile.ZIP_STORED:
                raise CapsuleBuildError("capsule entry violates deterministic ZIP profile")
        manifest = json.loads(archive.read(MANIFEST_NAME).decode("utf-8"))
        if manifest.get("schema") != "synergynet.source-capsule-manifest/v1":
            raise CapsuleBuildError("unexpected capsule manifest schema")
        if manifest.get("execution_authority") != "NONE":
            raise CapsuleBuildError("source capsule cannot gain execution authority")
        body = dict(manifest)
        supplied_manifest_digest = body.pop("manifest_digest", None)
        if supplied_manifest_digest != _sha256(canonical_json_bytes(body)):
            raise CapsuleBuildError("capsule manifest digest mismatch")
        records = manifest.get("files")
        if not isinstance(records, list):
            raise CapsuleBuildError("capsule file records missing")
        validated_paths: list[str] = []
        for record in records:
            if not isinstance(record, dict) or set(record) != {"path", "bytes", "sha256"}:
                raise CapsuleBuildError("unexpected capsule file record shape")
            path = _validate_relative_path(record["path"])
            validated_paths.append(path)
            data = archive.read(path)
            if record["bytes"] != len(data) or record["sha256"] != _sha256(data):
                raise CapsuleBuildError(f"capsule file integrity mismatch: {path}")
        if set(validated_paths) | {MANIFEST_NAME} != set(names):
            raise CapsuleBuildError("capsule entries do not match file manifest")
        return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic non-executable SynergyNet source capsule v1")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    capsule, manifest = build_capsule_bytes(args.root)
    verify_capsule_bytes(capsule)
    output = args.output or (args.root / "dist" / "synergynet_research_transport_source_v1.zip")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(capsule)
    result = {
        "schema": "synergynet.source-capsule-build-result/v1",
        "artifact_kind": "NON_EXECUTABLE_DETERMINISTIC_SOURCE_CAPSULE",
        "output": output.name,
        "output_bytes": len(capsule),
        "output_sha256": _sha256(capsule),
        "manifest_digest": manifest["manifest_digest"],
        "execution_authority": "NONE",
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
