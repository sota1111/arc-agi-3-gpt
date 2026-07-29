"""Build the reproducible, dependency-free stateful GPT candidate artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "candidate" / "manifest.json"
ZIP_TIMESTAMP = (2020, 1, 1, 0, 0, 0)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> tuple[Path, str]:
    manifest = json.loads(MANIFEST.read_text())
    for path, expected in manifest["source_files"].items():
        actual = sha256(ROOT / path)
        if actual != expected:
            raise ValueError(f"{path}: expected {expected}, got {actual}")
    output = ROOT / manifest["artifact"]["path"]
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(manifest["source_files"]):
            info = zipfile.ZipInfo(path, ZIP_TIMESTAMP)
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
