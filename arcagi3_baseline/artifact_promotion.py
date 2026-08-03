"""Validate the cycle evaluation before allowing candidate packaging."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text())
    evidence = manifest["evaluation_evidence"]
    resolved: dict[str, str] = {}
    for name, item in evidence.items():
        path = ROOT / item["path"]
        digest = sha256(path)
        if digest != item["sha256"]:
            raise ValueError(f"{name} evidence hash mismatch")
        resolved[name] = digest

    summary = json.loads((ROOT / evidence["summary"]["path"]).read_text())
    screen = json.loads((ROOT / evidence["screen"]["path"]).read_text())
    confirm = json.loads((ROOT / evidence["confirm"]["path"]).read_text())
    promotion_eligible = (
        summary["decision"] == "promoted"
        and summary["promotion_candidate"] is not None
        and summary["next_gate"] == "exec-compatibility"
    )
    if manifest["packaging"]["performed"] != promotion_eligible:
        raise ValueError("packaging decision does not match evaluation outcome")

    current = manifest["preserved_release"]
    candidate_hash = sha256(ROOT / current["candidate_manifest"])
    champion_hash = sha256(ROOT / current["champion_manifest"])
    artifact_hash = sha256(ROOT / current["artifact"])
    preserved = (
        candidate_hash == current["candidate_manifest_sha256"]
        and champion_hash == current["champion_manifest_sha256"]
        and artifact_hash == current["artifact_sha256"]
    )
    checks = {
        "screen_fingerprint": screen["result_fingerprint_sha256"]
        == summary["screen_fingerprint"],
        "confirm_fingerprint": confirm["result_fingerprint_sha256"]
        == summary["confirm_fingerprint"],
        "promotion_guard": not promotion_eligible,
        "candidate_change_reverted": summary["candidate_change_reverted"],
        "release_preserved": preserved,
        "exec_gate_not_run": manifest["exec_compatibility"]["status"] == "not-run",
        "kaggle_submission_not_run": not summary["kaggle_submission_performed"],
    }
    return {
        "schema_version": 1,
        "issue": manifest["issue"],
        "decision": summary["decision"],
        "promotion_candidate": summary["promotion_candidate"],
        "packaging": manifest["packaging"],
        "exec_compatibility": manifest["exec_compatibility"],
        "preserved_release": current,
        "evidence_sha256": resolved,
        "checks": checks,
        "passed": all(checks.values()),
    }
