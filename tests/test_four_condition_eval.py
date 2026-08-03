import json
from pathlib import Path
from typing import Any

import pytest

from arcagi3_baseline.four_condition_eval import (
    REQUIRED_KPIS,
    PromotionThresholds,
    evaluate,
    judge_promotion,
    load_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "eval/manifests/four-condition-real-game.json"


class FakeGame:
    def __init__(
        self, condition: dict[str, Any], chain_id: str, calls: list[dict[str, Any]]
    ) -> None:
        self.condition = condition
        self.chain_id = chain_id
        self.calls = calls

    def play(self, *, game: str, seed: int, action_budget: int) -> dict[str, int | float]:
        self.calls.append(
            {
                "game": game,
                "seed": seed,
                "budget": action_budget,
                "condition": self.condition["id"],
                "chain": self.chain_id,
            }
        )
        candidate = self.condition["id"] != "baseline"
        return {
            "score": 11 if candidate else 10,
            "levels_completed": 2,
            "actions": 80,
            "input_tokens": 100,
            "output_tokens": 20,
            "reasoning_tokens": 30,
            "duration_seconds": 1.1 if candidate else 1.0,
            "api_cost_usd": 0.105 if candidate else 0.1,
        }


def test_manifest_pins_games_trials_conditions_seed_budget_and_submission_gate() -> None:
    manifest = load_manifest(MANIFEST)
    assert manifest["games"] == ["ls20", "ft09", "sp80"]
    assert manifest["trials"] == 3
    assert manifest["seed_start"] == 2191
    assert manifest["action_budget"] == 100
    assert [item["id"] for item in manifest["conditions"]] == [
        "baseline",
        "retained_reasoning",
        "compaction",
        "retained_reasoning_compaction",
    ]
    assert manifest["gate_order"] == ["screen", "confirm"]
    assert manifest["submission_policy"] == "forbidden"


def test_all_runs_use_fresh_chains_and_write_all_kpis(tmp_path: Path) -> None:
    manifest = json.loads(MANIFEST.read_text())
    manifest["artifact"] = str(tmp_path / "result.json")
    local_manifest = tmp_path / "manifest.json"
    local_manifest.write_text(json.dumps(manifest))
    calls: list[dict[str, Any]] = []

    result = evaluate(local_manifest, lambda condition, chain: FakeGame(condition, chain, calls))

    assert result["run_count"] == 3 * 3 * 4
    assert result["response_chains_unique"] is True
    assert len({call["chain"] for call in calls}) == len(calls)
    assert {call["seed"] for call in calls} == {2191, 2192, 2193}
    assert {call["budget"] for call in calls} == {100}
    assert all(REQUIRED_KPIS <= run["metrics"].keys() for run in result["runs"])
    assert result["kaggle_submission_performed"] is False
    assert result["next_gate"] == "exec_compatibility"
    assert json.loads((tmp_path / "result.json").read_text()) == result


def test_promotion_requires_every_threshold() -> None:
    baseline = {
        "score": 10,
        "levels_completed": 2,
        "input_tokens": 100,
        "output_tokens": 20,
        "reasoning_tokens": 30,
        "api_cost_usd": 1,
        "duration_seconds": 10,
    }
    thresholds = PromotionThresholds(0, 1, 1.1, 1.1, 1.2)
    candidate = {**baseline, "score": 11, "input_tokens": 115}
    assert judge_promotion(baseline, candidate, thresholds)["promoted"] is True

    for field, value in [
        ("score", 10),
        ("levels_completed", 1),
        ("input_tokens", 131),
        ("api_cost_usd", 1.11),
        ("duration_seconds", 12.1),
    ]:
        rejected = judge_promotion(baseline, {**candidate, field: value}, thresholds)
        assert rejected["promoted"] is False


def test_missing_kpi_and_budget_overrun_are_rejected(tmp_path: Path) -> None:
    class InvalidGame:
        def play(self, **_: Any) -> dict[str, int]:
            return {"actions": 101}

    with pytest.raises(ValueError, match="missing required KPIs"):
        evaluate(MANIFEST, lambda _condition, _chain: InvalidGame())


def test_non_promoted_candidates_route_to_revert_and_document(tmp_path: Path) -> None:
    manifest = json.loads(MANIFEST.read_text())
    manifest["artifact"] = str(tmp_path / "rejected.json")
    local_manifest = tmp_path / "manifest.json"
    local_manifest.write_text(json.dumps(manifest))

    class EqualGame:
        def play(self, **_: Any) -> dict[str, int | float]:
            return {
                "score": 10,
                "levels_completed": 2,
                "actions": 80,
                "input_tokens": 100,
                "output_tokens": 20,
                "reasoning_tokens": 30,
                "duration_seconds": 1,
                "api_cost_usd": 0.1,
            }

    result = evaluate(local_manifest, lambda _condition, _chain: EqualGame())

    assert result["next_gate"] is None
    assert result["non_promoted_action"] == "revert_candidate_and_document"
    assert all(not decision["promoted"] for decision in result["promotion_decisions"].values())
