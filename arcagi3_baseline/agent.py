"""Stateful GPT-agent primitives with a contract-safe deterministic fallback."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .contract import (
    ACTION_IDS,
    ContractError,
    choose_action,
    validate_action,
    validate_observation,
)

Model = Callable[[str], str | None]


def _frame_digest(frame: list[Any]) -> str:
    encoded = json.dumps(frame, separators=(",", ":"), sort_keys=True)
    return f"{len(encoded)}:{sum(encoded.encode()) % 65521}"


@dataclass
class StateTracker:
    """Keep bounded observation deltas and prior actions for one game."""

    max_events: int = 8
    game_id: str | None = None
    previous: dict[str, Any] | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    actions: list[int] = field(default_factory=list)

    def observe(self, observation: dict[str, Any]) -> dict[str, Any]:
        observation = validate_observation(observation)
        if self.game_id != observation["game_id"]:
            self.game_id = observation["game_id"]
            self.previous = None
            self.events.clear()
            self.actions.clear()
        normalized = {
            "state": observation["state"],
            "levels_completed": observation.get("levels_completed", 0),
            "available_actions": sorted(set(observation["available_actions"])),
            "frame": _frame_digest(observation.get("frame", [])),
        }
        delta = {
            key: value
            for key, value in normalized.items()
            if self.previous is None or self.previous.get(key) != value
        }
        self.events.append(delta)
        self.events[:] = self.events[-self.max_events :]
        self.previous = normalized
        return delta

    def record(self, action_id: int) -> None:
        self.actions.append(action_id)
        self.actions[:] = self.actions[-self.max_events :]

    def prompt_state(self) -> dict[str, Any]:
        return {"recent_deltas": self.events, "recent_actions": self.actions}


def parse_model_action(raw: str | None) -> dict[str, Any]:
    """Extract a single action object from plain JSON or a fenced response."""
    if not raw or not raw.strip():
        raise ContractError("empty model response")
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) < 3 or not lines[-1].strip().startswith("```"):
            raise ContractError("unterminated JSON fence")
        text = "\n".join(lines[1:-1])
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:].lstrip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ContractError("model response is not JSON") from exc
    if not isinstance(value, dict):
        raise ContractError("model action must be an object")
    return value


class StatefulGPTAgent:
    """Call a model with bounded memory and always return a legal action."""

    def __init__(
        self,
        model: Model,
        *,
        use_memory: bool = True,
        constrain_output: bool = True,
        retries: int = 1,
    ) -> None:
        self.model = model
        self.use_memory = use_memory
        self.constrain_output = constrain_output
        self.retries = retries
        self.tracker = StateTracker()

    def _prompt(self, observation: dict[str, Any]) -> str:
        available = sorted(set(observation["available_actions"]) & ACTION_IDS)
        payload: dict[str, Any] = {
            "observation": {
                "game_id": observation["game_id"],
                "state": observation["state"],
                "levels_completed": observation.get("levels_completed", 0),
                "available_actions": available,
                "frame_digest": _frame_digest(observation.get("frame", [])),
            }
        }
        if self.use_memory:
            payload["memory"] = self.tracker.prompt_state()
        instruction = "Return one action JSON object."
        if self.constrain_output:
            instruction += (
                " id must be one of available_actions; data.game_id must match;"
                " action 6 also needs integer x/y in 0..63. No prose."
            )
        return instruction + "\n" + json.dumps(payload, separators=(",", ":"), sort_keys=True)

    def choose(self, observation: dict[str, Any]) -> dict[str, Any]:
        observation = validate_observation(observation)
        self.tracker.observe(observation)
        fallback = choose_action(observation)
        action = fallback
        used_fallback = True
        for _ in range(self.retries + 1):
            try:
                candidate = parse_model_action(self.model(self._prompt(observation)))
                candidate.setdefault("reasoning", {"policy": "stateful-gpt-legal-v1"})
                action = validate_action(candidate, observation)
                used_fallback = False
                break
            except (ContractError, TimeoutError):
                continue
        if used_fallback:
            action = {
                **fallback,
                "reasoning": {
                    "policy": "stateful-gpt-legal-v1",
                    "fallback": "deterministic-legal-v1",
                },
            }
        self.tracker.record(action["id"])
        return action
