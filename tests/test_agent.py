import json
from pathlib import Path

import pytest

from arcagi3_baseline.agent import StatefulGPTAgent, StateTracker, parse_model_action
from arcagi3_baseline.compare import evaluate
from arcagi3_baseline.contract import ContractError, validate_action


def observation(actions: list[int] | None = None) -> dict:
    return {
        "game_id": "g",
        "frame": [[[1]]],
        "state": "NOT_FINISHED",
        "levels_completed": 0,
        "win_levels": 1,
        "available_actions": actions or [2, 5],
    }


@pytest.mark.parametrize("response", [None, "", "not json", '{"id":7,"data":{"game_id":"g"}}'])
def test_invalid_or_empty_response_falls_back_to_legal_action(response: str | None) -> None:
    agent = StatefulGPTAgent(lambda prompt: response)
    action = agent.choose(observation())
    assert action["id"] == 2
    assert action["reasoning"]["fallback"] == "deterministic-legal-v1"
    validate_action(action, observation())


def test_timeout_falls_back_to_legal_action() -> None:
    def timeout(prompt: str) -> str:
        raise TimeoutError

    action = StatefulGPTAgent(timeout).choose(observation([6]))
    assert action["id"] == 6
    assert action["data"]["x"] == action["data"]["y"] == 0


def test_retry_accepts_second_legal_response() -> None:
    responses = iter(["", json.dumps({"id": 5, "data": {"game_id": "g"}})])
    action = StatefulGPTAgent(lambda prompt: next(responses), retries=1).choose(observation())
    assert action["id"] == 5
    assert "fallback" not in action["reasoning"]


def test_tracker_keeps_deltas_and_bounded_action_history() -> None:
    tracker = StateTracker(max_events=2)
    first = tracker.observe(observation())
    tracker.record(2)
    second_observation = observation()
    second_observation["frame"] = [[[2]]]
    second = tracker.observe(second_observation)
    tracker.record(5)
    tracker.record(2)
    assert "available_actions" in first
    assert set(second) == {"frame"}
    assert tracker.prompt_state()["recent_actions"] == [5, 2]


def test_parser_accepts_json_fence_and_rejects_prose() -> None:
    assert parse_model_action('```json\n{"id":2,"data":{"game_id":"g"}}\n```')["id"] == 2
    with pytest.raises(ContractError):
        parse_model_action("choose action 2")


def test_screen_winner_is_not_promoted_without_confirm_exec_gate() -> None:
    root = Path(__file__).resolve().parents[1]
    screen = evaluate(root / "eval/manifests/agent-screen.json")
    confirm = evaluate(root / "eval/manifests/agent-confirm.json")
    assert screen["winner"] == confirm["winner"] == "stateful-gpt-legal-v1"
    assert screen["seed"] == confirm["seed"] == 2132
    assert screen["fixture_sha256"] == confirm["fixture_sha256"]
    assert screen["promoted"] is True
    assert confirm["promoted"] is False
