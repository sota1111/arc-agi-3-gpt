"""OpenAI Responses API runtime for retained multi-turn game reasoning."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ResponsesRuntimeConfig:
    """Request options for one Responses API-backed gameplay runtime."""

    model: str
    instructions: str
    retain_reasoning: bool = False
    compact_threshold: int | None = None

    def __post_init__(self) -> None:
        if not self.model:
            raise ValueError("model must not be empty")
        if not self.instructions:
            raise ValueError("instructions must not be empty")
        if self.compact_threshold is not None and self.compact_threshold <= 0:
            raise ValueError("compact_threshold must be positive")


class ResponsesRuntime:
    """Adapt ``client.responses.create`` to the agent's callable model contract.

    The server owns conversation history through ``previous_response_id``. The
    runtime therefore exposes ``uses_server_state`` so callers do not also send
    a client-side rolling transcript.
    """

    uses_server_state = True

    def __init__(self, client: Any, config: ResponsesRuntimeConfig) -> None:
        self.client = client
        self.config = config
        self.previous_response_id: str | None = None
        self.game_id: str | None = None

    def reset(self) -> None:
        """Start a fresh response chain for a new game."""
        self.previous_response_id = None

    def build_request(self, prompt: str) -> dict[str, Any]:
        """Build one API request without mutating the response chain."""
        request: dict[str, Any] = {
            "model": self.config.model,
            "instructions": self.config.instructions,
            "input": prompt,
        }
        if self.previous_response_id is not None:
            request["previous_response_id"] = self.previous_response_id
        if self.config.retain_reasoning:
            request["reasoning"] = {"context": "all_turns"}
        if self.config.compact_threshold is not None:
            request["context_management"] = [
                {
                    "type": "compaction",
                    "compact_threshold": self.config.compact_threshold,
                }
            ]
        return request

    def _prepare_prompt(self, prompt: str) -> str:
        """Strip rolling memory and reset the server chain on a new game."""
        prefix, separator, raw_payload = prompt.rpartition("\n")
        if not separator:
            return prompt
        try:
            payload = json.loads(raw_payload)
            game_id = payload["observation"]["game_id"]
        except (json.JSONDecodeError, KeyError, TypeError):
            return prompt
        if isinstance(game_id, str) and game_id != self.game_id:
            self.reset()
            self.game_id = game_id
        payload.pop("memory", None)
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        return prefix + separator + encoded

    def __call__(self, prompt: str) -> str | None:
        response = self.client.responses.create(**self.build_request(self._prepare_prompt(prompt)))
        response_id = getattr(response, "id", None)
        if not isinstance(response_id, str) or not response_id:
            raise ValueError("Responses API result is missing response.id")
        self.previous_response_id = response_id
        output_text = getattr(response, "output_text", None)
        return output_text if isinstance(output_text, str) else None
