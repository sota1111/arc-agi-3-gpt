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


def _frame_grid(frame: list[Any]) -> list[list[Any]]:
    """Normalize the observation frame to a two-dimensional comparable grid."""
    if not isinstance(frame, list):
        return []
    grid: list[list[Any]] = []
    for row in frame:
        if not isinstance(row, list):
            return []
        grid.append(row)
    return grid


def _changed_regions(previous: list[Any], current: list[Any]) -> list[dict[str, int]]:
    """Return four-neighbour connected components of changed frame cells."""
    before = _frame_grid(previous)
    after = _frame_grid(current)
    changed: set[tuple[int, int]] = set()
    height = max(len(before), len(after))
    for y in range(height):
        before_row = before[y] if y < len(before) else []
        after_row = after[y] if y < len(after) else []
        for x in range(max(len(before_row), len(after_row))):
            old = before_row[x] if x < len(before_row) else None
            new = after_row[x] if x < len(after_row) else None
            if old != new:
                changed.add((x, y))
    regions: list[dict[str, int]] = []
    while changed:
        seed = changed.pop()
        component = {seed}
        frontier = [seed]
        while frontier:
            x, y = frontier.pop()
            for neighbour in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if neighbour in changed:
                    changed.remove(neighbour)
                    component.add(neighbour)
                    frontier.append(neighbour)
        xs = [point[0] for point in component]
        ys = [point[1] for point in component]
        regions.append(
            {
                "x_min": min(xs),
                "y_min": min(ys),
                "x_max": max(xs),
                "y_max": max(ys),
                "area": len(component),
            }
        )
    return sorted(regions, key=lambda region: (-region["area"], region["y_min"], region["x_min"]))


def _action_key(action: dict[str, Any]) -> str:
    data = action.get("data", {})
    if action.get("id") == 6:
        return f"6:{data.get('x', 0) // 8}:{data.get('y', 0) // 8}"
    return str(action.get("id"))


@dataclass
class StateTracker:
    """Keep bounded observation deltas and prior actions for one game."""

    max_events: int = 8
    game_id: str | None = None
    previous: dict[str, Any] | None = None
    previous_frame: list[Any] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    actions: list[int] = field(default_factory=list)
    effect_history: dict[str, list[int]] = field(default_factory=dict)
    pending_action: dict[str, Any] | None = None
    regions: list[dict[str, int]] = field(default_factory=list)

    def observe(self, observation: dict[str, Any]) -> dict[str, Any]:
        observation = validate_observation(observation)
        if self.game_id != observation["game_id"]:
            self.game_id = observation["game_id"]
            self.previous = None
            self.previous_frame = []
            self.events.clear()
            self.actions.clear()
            self.effect_history.clear()
            self.pending_action = None
            self.regions.clear()
        frame = observation.get("frame", [])
        self.regions = (
            _changed_regions(self.previous_frame, frame) if self.previous is not None else []
        )
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
        if self.pending_action is not None and self.previous is not None:
            effective = bool(
                self.regions
                or normalized["levels_completed"] > self.previous["levels_completed"]
                or normalized["state"] != self.previous["state"]
            )
            key = _action_key(self.pending_action)
            history = self.effect_history.setdefault(key, [])
            history.append(int(effective))
            history[:] = history[-self.max_events :]
        self.previous = normalized
        self.previous_frame = frame
        return delta

    def record(self, action: int | dict[str, Any]) -> None:
        action_object = action if isinstance(action, dict) else {"id": action, "data": {}}
        self.actions.append(action_object["id"])
        self.actions[:] = self.actions[-self.max_events :]
        self.pending_action = action_object

    def prompt_state(self) -> dict[str, Any]:
        return {
            "recent_deltas": self.events,
            "recent_actions": self.actions,
            "changed_regions": self.regions,
            "effect_history": self.effect_history,
        }

    def exploration_action(
        self,
        observation: dict[str, Any],
        *,
        use_regions: bool,
        use_effect_history: bool,
    ) -> dict[str, Any]:
        available = sorted(set(observation["available_actions"]) & ACTION_IDS - {0})
        if not available:
            return choose_action(observation)
        region = self.regions[0] if use_regions and self.regions else None
        candidates: list[tuple[float, int, dict[str, Any]]] = []
        for action_id in available:
            data: dict[str, Any] = {"game_id": observation["game_id"]}
            if action_id == 6:
                if region:
                    data["x"] = min(63, (region["x_min"] + region["x_max"]) // 2)
                    data["y"] = min(63, (region["y_min"] + region["y_max"]) // 2)
                else:
                    data["x"] = data["y"] = 0
            action = {"id": action_id, "data": data}
            history = self.effect_history.get(_action_key(action), [])
            novelty = 1.0 if not history else 0.0
            effect_rate = sum(history) / len(history) if history else 0.5
            score = (novelty + effect_rate) if use_effect_history else 0.0
            if region and action_id == 6:
                score += 2.0
            candidates.append((score, -action_id, action))
        return max(candidates)[2]


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
        use_regions: bool = False,
        use_effect_history: bool = False,
    ) -> None:
        self.model = model
        self.use_memory = use_memory
        self.constrain_output = constrain_output
        self.retries = retries
        self.use_regions = use_regions
        self.use_effect_history = use_effect_history
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
        exploration = self.tracker.exploration_action(
            observation,
            use_regions=self.use_regions,
            use_effect_history=self.use_effect_history,
        )
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
        if self.use_regions or self.use_effect_history:
            action = {
                **exploration,
                "reasoning": {
                    "policy": "region-effect-gpt-v1",
                    **({"fallback": "region-effect-policy"} if used_fallback else {}),
                    "features": {
                        "connected_regions": self.use_regions,
                        "effect_history": self.use_effect_history,
                    },
                },
            }
        if used_fallback and not (self.use_regions or self.use_effect_history):
            action = {
                **fallback,
                "reasoning": {
                    "policy": "stateful-gpt-legal-v1",
                    "fallback": "deterministic-legal-v1",
                },
            }
        self.tracker.record(action)
        return action
