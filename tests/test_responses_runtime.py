import json
from types import SimpleNamespace
from typing import Any

import pytest

from arcagi3_baseline.agent import StatefulGPTAgent
from arcagi3_baseline.responses_runtime import ResponsesRuntime, ResponsesRuntimeConfig


class RecordingResponses:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def create(self, **request: Any) -> SimpleNamespace:
        self.requests.append(request)
        game_id = json.loads(request["input"].splitlines()[-1])["observation"]["game_id"]
        return SimpleNamespace(
            id=f"resp_{len(self.requests)}",
            output_text=json.dumps({"id": 2, "data": {"game_id": game_id}}),
        )


def observation(game_id: str = "game-1") -> dict[str, Any]:
    return {
        "game_id": game_id,
        "frame": [[[1]]],
        "state": "NOT_FINISHED",
        "levels_completed": 0,
        "win_levels": 1,
        "available_actions": [2, 5],
    }


def runtime(responses: RecordingResponses, **overrides: Any) -> ResponsesRuntime:
    config = ResponsesRuntimeConfig(
        model="gpt-5.6",
        instructions="Play ARC and return only a legal action object.",
        **overrides,
    )
    return ResponsesRuntime(SimpleNamespace(responses=responses), config)


def test_response_ids_chain_and_fixed_instructions_are_resent() -> None:
    responses = RecordingResponses()
    agent = StatefulGPTAgent(runtime(responses), retries=0)

    agent.choose(observation())
    agent.choose(observation())

    assert "previous_response_id" not in responses.requests[0]
    assert responses.requests[1]["previous_response_id"] == "resp_1"
    assert [request["instructions"] for request in responses.requests] == [
        "Play ARC and return only a legal action object.",
        "Play ARC and return only a legal action object.",
    ]


def test_retained_reasoning_and_compaction_map_to_responses_request() -> None:
    responses = RecordingResponses()
    model = runtime(responses, retain_reasoning=True, compact_threshold=120_000)

    request = model.build_request("turn")

    assert request["reasoning"] == {"context": "all_turns"}
    assert request["context_management"] == [
        {"type": "compaction", "compact_threshold": 120_000}
    ]


def test_server_state_disables_rolling_memory_in_prompt() -> None:
    responses = RecordingResponses()
    agent = StatefulGPTAgent(runtime(responses), use_memory=True, retries=0)

    agent.choose(observation())

    prompt_payload = json.loads(responses.requests[0]["input"].splitlines()[-1])
    assert "memory" not in prompt_payload


def test_new_game_resets_response_chain() -> None:
    responses = RecordingResponses()
    agent = StatefulGPTAgent(runtime(responses), retries=0)

    agent.choose(observation("game-1"))
    agent.choose(observation("game-2"))

    assert "previous_response_id" not in responses.requests[1]


def test_invalid_compaction_threshold_is_rejected() -> None:
    with pytest.raises(ValueError, match="compact_threshold"):
        ResponsesRuntimeConfig(
            model="gpt-5.6",
            instructions="Return JSON.",
            compact_threshold=0,
        )
