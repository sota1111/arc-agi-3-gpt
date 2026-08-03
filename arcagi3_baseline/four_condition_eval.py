"""Reproducible four-condition real-game evaluation orchestration.

The game adapter is injected deliberately: production can bind the official ARC
gateway while tests use a deterministic fake without weakening the run contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_KPIS = {
    "score",
    "levels_completed",
    "actions",
    "input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "duration_seconds",
    "api_cost_usd",
}


class GameExecutor(Protocol):
    """One fresh response chain bound to one game/trial/condition."""

    def play(self, *, game: str, seed: int, action_budget: int) -> Mapping[str, Any]: ...


ExecutorFactory = Callable[[dict[str, Any], str], GameExecutor]


@dataclass(frozen=True)
class PromotionThresholds:
    score_improvement: float
    completion_ratio: float
    token_ratio: float
    cost_ratio: float
    latency_ratio: float


def load_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text())
    validate_manifest(manifest)
    return manifest


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    if manifest.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    if manifest.get("games") != ["ls20", "ft09", "sp80"]:
        raise ValueError("games must be fixed to ls20, ft09, sp80")
    if manifest.get("trials") != 3 or manifest.get("seed_start") != 2191:
        raise ValueError("trials and seed_start must be fixed to 3 and 2191")
    if manifest.get("action_budget") != 100:
        raise ValueError("action_budget must be 100")
    conditions = manifest.get("conditions")
    expected = {
        "baseline": (False, None),
        "retained_reasoning": (True, None),
        "compaction": (False, 120_000),
        "retained_reasoning_compaction": (True, 120_000),
    }
    if not isinstance(conditions, list) or len(conditions) != len(expected):
        raise ValueError("exactly four conditions are required")
    actual = {
        item.get("id"): (item.get("retain_reasoning"), item.get("compact_threshold"))
        for item in conditions
        if isinstance(item, dict)
    }
    if actual != expected:
        raise ValueError("conditions do not match the fixed four-condition contract")
    thresholds = manifest.get("promotion_thresholds", {})
    if thresholds != {
        "score_improvement": 0.0,
        "completion_ratio": 1.0,
        "token_ratio": 1.1,
        "cost_ratio": 1.1,
        "latency_ratio": 1.2,
    }:
        raise ValueError("promotion thresholds do not match the fixed contract")
    if manifest.get("submission_policy") != "forbidden":
        raise ValueError("Kaggle submission must be forbidden")
    if manifest.get("gate_order") != ["screen", "confirm"]:
        raise ValueError("screen then confirm gate is required")


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError(f"{name} must be a non-negative number")
    return float(value)


def _normalize_metrics(raw: Mapping[str, Any]) -> dict[str, int | float]:
    missing = REQUIRED_KPIS - raw.keys()
    if missing:
        raise ValueError(f"missing required KPIs: {sorted(missing)}")
    metrics: dict[str, int | float] = {}
    for name in sorted(REQUIRED_KPIS):
        value = _number(raw[name], name)
        metrics[name] = int(value) if name in {"levels_completed", "actions"} else value
    return metrics


def _total_tokens(metrics: Mapping[str, int | float]) -> float:
    return sum(float(metrics[key]) for key in ("input_tokens", "output_tokens", "reasoning_tokens"))


def _ratio(candidate: float, baseline: float) -> float:
    if candidate == baseline == 0:
        return 1.0
    return float("inf") if baseline == 0 else candidate / baseline


def judge_promotion(
    baseline: Mapping[str, int | float],
    candidate: Mapping[str, int | float],
    thresholds: PromotionThresholds,
) -> dict[str, Any]:
    ratios = {
        "completion": _ratio(
            float(candidate["levels_completed"]), float(baseline["levels_completed"])
        ),
        "tokens": _ratio(_total_tokens(candidate), _total_tokens(baseline)),
        "cost": _ratio(float(candidate["api_cost_usd"]), float(baseline["api_cost_usd"])),
        "latency": _ratio(
            float(candidate["duration_seconds"]), float(baseline["duration_seconds"])
        ),
    }
    checks = {
        "score_improved": float(candidate["score"])
        > float(baseline["score"]) + thresholds.score_improvement,
        "completion_non_degraded": ratios["completion"] >= thresholds.completion_ratio,
        "tokens_within_limit": ratios["tokens"] <= thresholds.token_ratio,
        "cost_within_limit": ratios["cost"] <= thresholds.cost_ratio,
        "latency_within_limit": ratios["latency"] <= thresholds.latency_ratio,
    }
    return {"promoted": all(checks.values()), "checks": checks, "ratios": ratios}


def _aggregate(runs: list[dict[str, Any]]) -> dict[str, float]:
    return {
        name: sum(float(run["metrics"][name]) for run in runs) / len(runs)
        for name in sorted(REQUIRED_KPIS)
    }


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def evaluate(
    manifest_path: Path,
    factory: ExecutorFactory,
    *,
    phase: str = "screen",
    candidate_ids: list[str] | None = None,
    artifact_path: Path | None = None,
    cohort: str | None = None,
    executor_fingerprint: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute an isolated screen or confirm cohort and write its result."""
    manifest = load_manifest(manifest_path)
    if phase not in {"screen", "confirm"}:
        raise ValueError("phase must be screen or confirm")
    selected = set(candidate_ids or [])
    if phase == "confirm" and not selected:
        raise ValueError("confirm requires at least one selected candidate")
    conditions = [
        condition
        for condition in manifest["conditions"]
        if phase == "screen" or condition["id"] == "baseline" or condition["id"] in selected
    ]
    runs: list[dict[str, Any]] = []
    chain_ids: set[str] = set()
    for game in manifest["games"]:
        for trial in range(manifest["trials"]):
            seed = manifest["seed_start"] + trial
            for condition in conditions:
                chain_id = f"{game}-t{trial + 1}-{condition['id']}-{uuid.uuid4().hex}"
                if chain_id in chain_ids:
                    raise RuntimeError("response chain id collision")
                chain_ids.add(chain_id)
                executor = factory(condition, chain_id)
                started = time.perf_counter()
                raw = executor.play(game=game, seed=seed, action_budget=manifest["action_budget"])
                metrics = _normalize_metrics(raw)
                measured = time.perf_counter() - started
                if metrics["duration_seconds"] == 0:
                    metrics["duration_seconds"] = measured
                if metrics["actions"] > manifest["action_budget"]:
                    raise ValueError("executor exceeded action budget")
                runs.append(
                    {
                        "game": game,
                        "trial": trial + 1,
                        "seed": seed,
                        "condition": condition["id"],
                        "response_chain_id": chain_id,
                        "metrics": metrics,
                    }
                )
    by_condition = {
        condition["id"]: _aggregate(
            [run for run in runs if run["condition"] == condition["id"]]
        )
        for condition in conditions
    }
    raw_thresholds = manifest["promotion_thresholds"]
    thresholds = PromotionThresholds(**raw_thresholds)
    decisions = {
        condition: judge_promotion(by_condition["baseline"], metrics, thresholds)
        for condition, metrics in by_condition.items()
        if condition != "baseline"
    }
    result = {
        "schema_version": 1,
        "phase": phase,
        "cohort": cohort or f"sot-2361-{phase}",
        "manifest": _display_path(manifest_path),
        "run_count": len(runs),
        "response_chains_unique": len(chain_ids) == len(runs),
        "kaggle_submission_performed": False,
        "runs": runs,
        "aggregates": by_condition,
        "promotion_decisions": decisions,
        "next_gate": (
            "exec_compatibility" if any(d["promoted"] for d in decisions.values()) else None
        ),
        "non_promoted_action": "revert_candidate_and_document",
        "executor_fingerprint": dict(executor_fingerprint or {}),
    }
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    result["result_fingerprint_sha256"] = hashlib.sha256(canonical).hexdigest()
    output = artifact_path or ROOT / manifest["artifact"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.parse_args()
    raise SystemExit(
        "bind an official ARC GameExecutor; Kaggle submission is intentionally unavailable"
    )


if __name__ == "__main__":
    main()
