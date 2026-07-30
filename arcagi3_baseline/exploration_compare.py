"""Reproducible connected-region and action-effect feature ablation."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from .agent import StatefulGPTAgent
from .candidate_entrypoint import RecordModel
from .contract import validate_action, validate_observation

ROOT = Path(__file__).resolve().parents[1]
FEATURES = {
    "stateful-gpt-legal-v1": (False, False),
    "region-only-v1": (True, False),
    "effect-history-only-v1": (False, True),
    "region-effect-full-v1": (True, True),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _percentile_95(values: list[float]) -> float:
    return sorted(values)[max(0, (95 * len(values) + 99) // 100 - 1)] if values else 0.0


def _evaluate_candidate(
    name: str, records: list[dict[str, Any]], repetitions: int
) -> dict[str, Any]:
    use_regions, use_effect_history = FEATURES[name]
    legal = completed = faults = no_ops = 0
    progress = 0.0
    effective: set[str] = set()
    durations: list[float] = []
    region_count = 0
    attempts = len(records) * repetitions
    for _ in range(repetitions):
        model = RecordModel()
        agent = StatefulGPTAgent(
            model,
            use_regions=use_regions,
            use_effect_history=use_effect_history,
        )
        for record in records:
            observation = validate_observation(record["observation"])
            model.response = record.get("model_response")
            started = time.perf_counter()
            try:
                action = agent.choose(observation)
                validate_action(action, observation)
                legal += 1
            except Exception:  # pragma: no cover - recorded as a gate metric
                faults += 1
                continue
            durations.append(time.perf_counter() - started)
            region_count += len(agent.tracker.regions)
            action_id = str(action["id"])
            value = float(record["progress_by_action"].get(action_id, 0.0))
            progress += value
            completed += int(record.get("completes_on_action") == action["id"])
            if value > 0:
                effective.add(action_id)
            else:
                no_ops += 1
    return {
        "candidate": name,
        "features": {
            "connected_regions": use_regions,
            "effect_history": use_effect_history,
        },
        "attempts": attempts,
        "legal_action_rate": legal / attempts,
        "completion_rate": completed / attempts,
        "progress_proxy": progress / attempts,
        "unique_effective_actions": len(effective),
        "no_op_rate": no_ops / attempts,
        "fault_count": faults,
        # Millisecond precision is sufficient for the 50 ms gate and keeps the
        # checked-in comparison artifact reproducible across host schedulers.
        "p95_action_seconds": round(_percentile_95(durations), 3),
        "changed_region_count": region_count,
    }


def evaluate(manifest_path: Path, *, write_artifact: bool = True) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text())
    fixture = ROOT / manifest["fixture"]["path"]
    if _sha256(fixture) != manifest["fixture"]["sha256"]:
        raise ValueError("fixture sha256 mismatch")
    records = [json.loads(line) for line in fixture.read_text().splitlines() if line.strip()]
    results = [
        _evaluate_candidate(candidate, records, manifest["repetitions"])
        for candidate in manifest["candidates"]
    ]
    champion = next(item for item in results if item["candidate"] == manifest["champion"])
    limits = manifest["thresholds"]
    eligible = [
        item
        for item in results
        if item["candidate"] != manifest["champion"]
        and item["legal_action_rate"] >= limits["legal_action_rate"]
        and item["completion_rate"] >= champion["completion_rate"]
        and item["fault_count"] <= champion["fault_count"]
        and item["p95_action_seconds"]
        <= max(limits["max_p95_action_seconds"], champion["p95_action_seconds"])
        and item["progress_proxy"]
        >= champion["progress_proxy"] + limits["min_progress_improvement"]
    ]
    winner = max(eligible, key=lambda item: item["progress_proxy"], default=None)
    promoted = bool(
        manifest["phase"] == "confirm"
        and winner
        and manifest.get("kaggle_exec_verified", False)
    )
    result = {
        "schema_version": 1,
        "phase": manifest["phase"],
        "manifest": str(manifest_path.relative_to(ROOT)),
        "manifest_sha256": _sha256(manifest_path),
        "fixture": manifest["fixture"],
        "cohort": manifest["cohort"],
        "repetitions": manifest["repetitions"],
        "champion": manifest["champion"],
        "thresholds": limits,
        "candidates": results,
        "screen_passed_candidates": [item["candidate"] for item in eligible],
        "selected_for_confirm": (
            winner["candidate"] if manifest["phase"] == "screen" and winner else None
        ),
        "winner": winner["candidate"] if winner else None,
        "kaggle_exec_verified": manifest.get("kaggle_exec_verified", False),
        "promoted": promoted,
        "promotion_reason": (
            "independent confirm improved progress without completion, fault, or p95 regression; "
            "dependency-free exec gate passed"
            if promoted
            else "confirm and exec gates are required"
        ),
    }
    if write_artifact:
        output = ROOT / manifest["artifact"]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.manifest.resolve())
    print(json.dumps(result, sort_keys=True))
    return 0 if result["winner"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
