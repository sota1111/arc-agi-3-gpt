#!/usr/bin/env python3
"""Run SOT-2361 against the pinned local ARC-AGI-3 environments.

The repository has no OpenAI API credential, so this runner deliberately uses
one deterministic action policy for every Responses condition.  It still runs
the real game implementations and measures the complete fixed cohorts, but the
feature comparison is marked inconclusive rather than pretending an offline
proxy exercised server-retained reasoning or compaction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from arcagi3_baseline.four_condition_eval import evaluate  # noqa: E402


class OfflineRealGame:
    def __init__(self, condition: dict[str, Any], chain_id: str, environments: Path) -> None:
        self.condition = condition
        self.chain_id = chain_id
        self.environments = environments

    def play(self, *, game: str, seed: int, action_budget: int) -> dict[str, int | float]:
        from arc_agi import Arcade, OperationMode
        from arcengine import GameAction, GameState

        arcade = Arcade(
            operation_mode=OperationMode.OFFLINE,
            environments_dir=str(self.environments),
            logger=logging.getLogger("sot2361"),
        )
        env = arcade.make(game, seed=seed)
        if env is None:
            raise RuntimeError(f"failed to load pinned environment {game}")
        frame = env.reset()
        if frame is None:
            raise RuntimeError(f"{game} reset returned no frame")
        actions = 0
        input_tokens = output_tokens = reasoning_tokens = 0
        while actions < action_budget and frame.state not in {GameState.WIN, GameState.GAME_OVER}:
            available = sorted(set(frame.available_actions or []))
            action_id = 0 if frame.state is GameState.NOT_PLAYED else next(
                (item for item in available if item != 0), 0
            )
            action = GameAction.from_id(action_id)
            data: dict[str, Any] = {"game_id": frame.game_id}
            if action_id == 6:
                data.update({"x": 0, "y": 0})
            action.set_data(data)
            # Stable estimates make resource ratios auditable without claiming
            # that a Responses request happened in this credential-free run.
            input_tokens += len(json.dumps(frame.available_actions or [])) + 8
            output_tokens += 12
            frame = env.step(action, data=data, reasoning={"chain": self.chain_id})
            if frame is None:
                raise RuntimeError(f"{game} returned no frame after action {actions + 1}")
            actions += 1
        levels = int(frame.levels_completed or 0)
        win_levels = max(int(frame.win_levels or 0), 1)
        return {
            "score": levels / win_levels,
            "levels_completed": levels,
            "actions": actions,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "reasoning_tokens": reasoning_tokens,
            "duration_seconds": 0,
            "api_cost_usd": 0,
        }


def fingerprint(environments: Path) -> dict[str, Any]:
    files = sorted(environments.glob("*/**/metadata.json"))
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(environments).as_posix().encode())
        digest.update(path.read_bytes())
    return {
        "adapter": "offline-real-game-equal-policy-v1",
        "environment_metadata_sha256": digest.hexdigest(),
        "openai_api_available": bool(os.environ.get("OPENAI_API_KEY")),
        "responses_features_exercised": False,
        "comparison_validity": "inconclusive",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environments", type=Path, required=True)
    args = parser.parse_args()
    manifest = ROOT / "eval/manifests/four-condition-real-game.json"
    fp = fingerprint(args.environments)
    def factory(condition: dict[str, Any], chain: str) -> OfflineRealGame:
        return OfflineRealGame(condition, chain, args.environments)
    screen = evaluate(
        manifest,
        factory,
        phase="screen",
        artifact_path=ROOT / "artifacts/four-condition-real-game/screen.json",
        cohort="sot-2361-screen-seeds-2191-2193",
        executor_fingerprint=fp,
    )
    # A diagnostic confirm is still independent. Compaction is selected by a
    # deterministic tie-break; it is not an advancement or promotion.
    selected = min(screen["promotion_decisions"])
    confirm = evaluate(
        manifest,
        factory,
        phase="confirm",
        candidate_ids=[selected],
        artifact_path=ROOT / "artifacts/four-condition-real-game/confirm.json",
        cohort="sot-2361-confirm-independent-seeds-2191-2193",
        executor_fingerprint=fp,
    )
    summary = {
        "schema_version": 1,
        "screen_artifact": "artifacts/four-condition-real-game/screen.json",
        "confirm_artifact": "artifacts/four-condition-real-game/confirm.json",
        "selected_condition": selected,
        "selection_reason": "diagnostic lexical tie-break; no screen condition passed promotion",
        "decision": "inconclusive",
        "promotion_candidate": None,
        "next_gate": None,
        "candidate_change_reverted": True,
        "kaggle_submission_performed": False,
        "screen_fingerprint": screen["result_fingerprint_sha256"],
        "confirm_fingerprint": confirm["result_fingerprint_sha256"],
    }
    output = ROOT / "artifacts/four-condition-real-game/summary.json"
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
