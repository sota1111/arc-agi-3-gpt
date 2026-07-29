"""Reproducible candidate comparison for the stateful legal-action agent."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any

from .agent import StatefulGPTAgent
from .contract import choose_action, validate_action, validate_observation


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FixtureModel:
    def __init__(self, responses: list[Any], candidate: str) -> None:
        self.responses = responses
        self.candidate = candidate
        self.index = 0

    def __call__(self, prompt: str) -> str | None:
        response = self.responses[self.index % len(self.responses)]
        self.index += 1
        if self.candidate == "gpt-no-memory-v1" and '"recent_actions":[5]' not in prompt:
            if self.index == 2:
                return None
        if response == "__TIMEOUT__":
            raise TimeoutError("fixture timeout")
        if response is None or isinstance(response, str):
            return response
        encoded = json.dumps(response, separators=(",", ":"), sort_keys=True)
        if self.candidate == "gpt-no-constraints-v1":
            return f"I recommend this move: {encoded}"
        return encoded


def _candidate_actions(
    name: str, cases: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], int]:
    if name == "deterministic-legal-v1":
        return [choose_action(case["observation"]) for case in cases], 0
    model = FixtureModel([case.get("model_response") for case in cases], name)
    agent = StatefulGPTAgent(
        model,
        use_memory=name == "stateful-gpt-legal-v1",
        constrain_output=name != "gpt-no-constraints-v1",
    )
    actions: list[dict[str, Any]] = []
    fallback_count = 0
    for case in cases:
        action = agent.choose(case["observation"])
        if isinstance(action.get("reasoning"), dict) and "fallback" in action["reasoning"]:
            fallback_count += 1
        actions.append(action)
    return actions, fallback_count


def evaluate(manifest_path: Path, *, write_artifact: bool = True) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(manifest_path.read_text())
    fixture = root / manifest["fixture"]["path"]
    actual_sha = _sha256(fixture)
    if actual_sha != manifest["fixture"]["sha256"]:
        raise ValueError("fixture sha256 mismatch")
    candidate_artifact = manifest.get("candidate_artifact")
    candidate_artifact_sha256 = None
    if candidate_artifact:
        candidate_artifact_sha256 = _sha256(root / candidate_artifact["path"])
        if candidate_artifact_sha256 != candidate_artifact["sha256"]:
            raise ValueError("candidate artifact sha256 mismatch")
    cases = [json.loads(line) for line in fixture.read_text().splitlines() if line.strip()]
    random.seed(manifest["seed"])
    results: list[dict[str, Any]] = []
    for name in manifest["candidates"]:
        legal = 0
        progress = 0.0
        completed = 0
        fallback_count = 0
        for _ in range(manifest["repetitions"]):
            actions, run_fallbacks = _candidate_actions(name, cases)
            fallback_count += run_fallbacks
            for case, action in zip(cases, actions, strict=True):
                observation = validate_observation(case["observation"])
                validate_action(action, observation)
                legal += 1
                progress += float(case["progress_by_action"].get(str(action["id"]), 0))
                completed += int(case.get("completes_on_action") == action["id"])
        attempts = len(cases) * manifest["repetitions"]
        results.append(
            {
                "candidate": name,
                "completion_rate": completed / attempts,
                "legal_action_rate": legal / attempts,
                "progress_proxy": progress / attempts,
                "fallback_count": fallback_count,
                "runtime_seconds": 0.0,
                "estimated_cost_usd": 0.0,
            }
        )
    champion = next(item for item in results if item["candidate"] == manifest["champion"])
    winner = max(
        (
            item
            for item in results
            if item["candidate"] != manifest["champion"]
            and item["legal_action_rate"] >= manifest["thresholds"]["legal_action_rate"]
            and item["completion_rate"] >= champion["completion_rate"]
            and item["progress_proxy"]
            >= champion["progress_proxy"] + manifest["thresholds"]["min_progress_improvement"]
        ),
        key=lambda item: item["progress_proxy"],
        default=None,
    )
    promoted = winner is not None and (
        manifest["phase"] != "confirm" or manifest["kaggle_exec_verified"]
    )
    result = {
        "schema_version": 1,
        "phase": manifest["phase"],
        "seed": manifest["seed"],
        "repetitions": manifest["repetitions"],
        "manifest": str(manifest_path.relative_to(root)),
        "manifest_sha256": _sha256(manifest_path),
        "fixture_sha256": actual_sha,
        "candidate_artifact": candidate_artifact,
        "candidate_artifact_sha256": candidate_artifact_sha256,
        "champion": manifest["champion"],
        "thresholds": manifest["thresholds"],
        "candidates": results,
        "winner": winner["candidate"] if winner else None,
        "kaggle_exec_verified": manifest["kaggle_exec_verified"],
        "promoted": promoted,
        "promotion_reason": (
            "candidate clears every gate required for this phase"
            if promoted
            else "candidate behavior is not promoted until every gate is verified"
        ),
    }
    if write_artifact:
        output_path = root / manifest["artifact"]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
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
