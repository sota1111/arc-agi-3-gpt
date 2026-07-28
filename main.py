#!/usr/bin/env python3
"""JSON-lines entrypoint for the deterministic ARC-AGI-3 baseline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TextIO

from arcagi3_baseline import ContractError, choose_action


def run(source: TextIO, destination: TextIO) -> int:
    for line_number, line in enumerate(source, 1):
        if not line.strip():
            continue
        try:
            observation = json.loads(line)
            if isinstance(observation, dict) and "observation" in observation:
                observation = observation["observation"]
            action = choose_action(observation)
        except (json.JSONDecodeError, ContractError) as exc:
            print(f"observation {line_number}: {exc}", file=sys.stderr)
            return 2
        destination.write(json.dumps(action, separators=(",", ":"), sort_keys=True) + "\n")
        destination.flush()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path)
    args = parser.parse_args()
    if args.input:
        with args.input.open() as source:
            return run(source, sys.stdout)
    return run(sys.stdin, sys.stdout)


if __name__ == "__main__":
    raise SystemExit(main())
