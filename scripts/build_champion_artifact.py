"""Build or verify the deterministic, offline Kaggle champion package."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "champion" / "manifest.json"
ZIP_TIMESTAMP = (2020, 1, 1, 0, 0, 0)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_file(path: str, expected: str) -> None:
    actual = sha256(ROOT / path)
    if actual != expected:
        raise ValueError(f"{path}: expected {expected}, got {actual}")


def build() -> tuple[Path, str]:
    manifest = json.loads(MANIFEST.read_text())
    if manifest["champion"] == "stateful-gpt-legal-v1":
        try:
            from scripts.build_candidate_artifact import build as build_candidate
        except ModuleNotFoundError:
            from build_candidate_artifact import build as build_candidate

        if sha256(ROOT / manifest["candidate_manifest"]) != manifest["candidate_manifest_sha256"]:
            raise ValueError("candidate manifest hash mismatch")
        output, digest = build_candidate()
        if output.relative_to(ROOT).as_posix() != manifest["artifact"]["path"]:
            raise ValueError("champion artifact path does not match candidate artifact")
        return output, digest
    for path, expected in manifest["package_files"].items():
        verify_file(path, expected)
    evaluation = manifest["evaluation"]
    for key in ("screen", "confirm"):
        verify_file(evaluation[f"{key}_manifest"], evaluation[f"{key}_manifest_sha256"])
        verify_file(evaluation[f"{key}_result"], evaluation[f"{key}_result_sha256"])
    decision = manifest["candidate_decision"]
    verify_file(decision["confirm_result"], decision["confirm_result_sha256"])

    output = ROOT / manifest["artifact"]["path"]
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(manifest["package_files"]):
            info = zipfile.ZipInfo(path.removeprefix("kaggle/kernel/"), ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, (ROOT / path).read_bytes())
    return output, sha256(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output, digest = build()
    expected = json.loads(MANIFEST.read_text())["artifact"]["sha256"]
    print(f"{digest}  {output.relative_to(ROOT)}")
    if args.check and digest != expected:
        raise ValueError(f"artifact: expected {expected}, got {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
