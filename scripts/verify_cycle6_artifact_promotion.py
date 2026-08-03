"""Verify and materialize the cycle-6 artifact promotion decision."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arcagi3_baseline.artifact_promotion import ROOT, evaluate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "eval/manifests/cycle6-artifact-promotion.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts/cycle6-artifact-promotion/result.json",
    )
    args = parser.parse_args()
    result = evaluate(args.manifest.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
