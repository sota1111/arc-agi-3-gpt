"""JSON-lines entrypoint embedded in the stateful GPT candidate artifact."""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, TextIO

from .agent import StatefulGPTAgent
from .contract import ContractError


class RecordModel:
    """Expose the fixture/model response attached to the current observation."""

    response: Any = None

    def __call__(self, _prompt: str) -> str | None:
        if self.response == "__TIMEOUT__":
            raise TimeoutError("model timeout")
        if self.response is None or isinstance(self.response, str):
            return self.response
        return json.dumps(self.response, separators=(",", ":"), sort_keys=True)


def run(source: TextIO, destination: TextIO) -> int:
    model = RecordModel()
    agent = StatefulGPTAgent(model)
    for line_number, line in enumerate(source, 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            observation = record.get("observation", record)
            model.response = record.get("model_response")
            action = agent.choose(observation)
        except (AttributeError, json.JSONDecodeError, ContractError) as exc:
            print(f"record {line_number}: {exc}", file=sys.stderr)
            return 2
        destination.write(json.dumps(action, separators=(",", ":"), sort_keys=True) + "\n")
        destination.flush()
    return 0


def main() -> int:
    delay = float(os.getenv("ARC_EXEC_STARTUP_DELAY_SECONDS", "0"))
    if delay:
        time.sleep(delay)
    return run(sys.stdin, sys.stdout)


if __name__ == "__main__":
    raise SystemExit(main())
