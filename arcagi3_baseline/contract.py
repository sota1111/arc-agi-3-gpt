"""Dependency-free representation of the pinned ARC-AGI-3 wire contract."""

from __future__ import annotations

import json
from typing import Any

STATES = {"NOT_PLAYED", "NOT_FINISHED", "WIN", "GAME_OVER"}
ACTION_IDS = set(range(8))
MAX_REASONING_BYTES = 16 * 1024


class ContractError(ValueError):
    """Raised when an observation or action violates the pinned contract."""


def _require_int(value: Any, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ContractError(f"{name} must be in {minimum}..{maximum}")
    return value


def validate_observation(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError("observation must be an object")
    game_id = value.get("game_id")
    if not isinstance(game_id, str):
        raise ContractError("game_id must be a string")
    state = value.get("state")
    if state not in STATES:
        raise ContractError(f"state must be one of {sorted(STATES)}")
    actions = value.get("available_actions")
    if not isinstance(actions, list):
        raise ContractError("available_actions must be an array")
    for index, action_id in enumerate(actions):
        _require_int(action_id, f"available_actions[{index}]", 0, 7)
    frame = value.get("frame", [])
    if not isinstance(frame, list):
        raise ContractError("frame must be an array")
    _require_int(value.get("levels_completed", 0), "levels_completed", 0, 254)
    _require_int(value.get("win_levels", 0), "win_levels", 0, 254)
    return value


def validate_action(value: Any, observation: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError("action must be an object")
    action_id = _require_int(value.get("id"), "id", 0, 7)
    data = value.get("data")
    if not isinstance(data, dict):
        raise ContractError("data must be an object")
    if data.get("game_id") != observation["game_id"]:
        raise ContractError("data.game_id must match the observation")
    if action_id == 6:
        _require_int(data.get("x"), "data.x", 0, 63)
        _require_int(data.get("y"), "data.y", 0, 63)
    elif set(data) != {"game_id"}:
        raise ContractError("simple actions only accept data.game_id")
    available = observation["available_actions"]
    if observation["state"] not in {"NOT_PLAYED", "GAME_OVER"} and available:
        if action_id not in available:
            raise ContractError("action id is not advertised by available_actions")
    reasoning = value.get("reasoning")
    try:
        encoded = json.dumps(reasoning, separators=(",", ":")).encode()
    except (TypeError, ValueError) as exc:
        raise ContractError("reasoning must be JSON-serializable") from exc
    if len(encoded) > MAX_REASONING_BYTES:
        raise ContractError("reasoning exceeds 16 KiB")
    return value


def choose_action(observation: dict[str, Any]) -> dict[str, Any]:
    validate_observation(observation)
    available = sorted(set(observation["available_actions"]) & ACTION_IDS)
    if observation["state"] in {"NOT_PLAYED", "GAME_OVER"}:
        action_id = 0
    else:
        action_id = next((candidate for candidate in available if candidate != 0), 0)
    data: dict[str, Any] = {"game_id": observation["game_id"]}
    if action_id == 6:
        data.update(x=0, y=0)
    action = {
        "id": action_id,
        "data": data,
        "reasoning": {"policy": "deterministic-legal-v1"},
    }
    return validate_action(action, observation)
