"""Kaggle entrypoint for the cycle-5 region/effect GPT champion."""

import os
import shutil
import subprocess
from pathlib import Path

AGENT_SOURCE = r'''
from collections import defaultdict
from typing import Any
from arcengine import FrameData, GameAction, GameState
from ..agent import Agent

def flatten_layers(layers):
    height = max((len(layer) for layer in layers), default=0)
    width = max((len(row) for layer in layers for row in layer), default=0)
    frame = [[0 for _ in range(width)] for _ in range(height)]
    for layer in layers:
        for y, row in enumerate(layer):
            for x, value in enumerate(row):
                if value != 0:
                    frame[y][x] = value
    return frame

def largest_changed_region(previous, current):
    changed = set()
    for y in range(max(len(previous), len(current))):
        before = previous[y] if y < len(previous) else []
        after = current[y] if y < len(current) else []
        for x in range(max(len(before), len(after))):
            old = before[x] if x < len(before) else None
            new = after[x] if x < len(after) else None
            if old != new:
                changed.add((x, y))
    regions = []
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
        regions.append(component)
    return max(regions, key=lambda region: (len(region), -min(region)), default=set())

class RegionEffectChampion(Agent):
    MAX_ACTIONS = 80

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.previous_frame = []
        self.pending_key = None
        self.effect_history = defaultdict(list)

    def is_done(self, frames: list[FrameData], latest_frame: FrameData) -> bool:
        return latest_frame.state is GameState.WIN

    def choose_action(
        self, frames: list[FrameData], latest_frame: FrameData
    ) -> GameAction:
        if latest_frame.state in (GameState.NOT_PLAYED, GameState.GAME_OVER):
            self.previous_frame = []
            self.pending_key = None
            self.effect_history.clear()
            action = GameAction.RESET
        else:
            current = flatten_layers(latest_frame.frame)
            region = largest_changed_region(self.previous_frame, current)
            if self.pending_key is not None:
                history = self.effect_history[self.pending_key]
                history.append(int(bool(region)))
                del history[:-8]
            available = sorted(
                {int(getattr(value, "value", value)) for value in latest_frame.available_actions}
                - {0}
            )
            if not available:
                action = GameAction.RESET
                self.pending_key = None
            elif 6 in available and region:
                xs = [point[0] for point in region]
                ys = [point[1] for point in region]
                x = min(63, (min(xs) + max(xs)) // 2)
                y = min(63, (min(ys) + max(ys)) // 2)
                action = GameAction.from_id(6)
                action.set_data({"x": x, "y": y})
                self.pending_key = f"6:{x // 8}:{y // 8}"
            else:
                def score(action_id):
                    history = self.effect_history[str(action_id)]
                    novelty = 1.0 if not history else 0.0
                    effect_rate = sum(history) / len(history) if history else 0.5
                    return (novelty + effect_rate, -action_id)
                action_id = max(available, key=score)
                action = GameAction.from_id(action_id)
                if action_id == 6:
                    action.set_data({"x": 0, "y": 0})
                self.pending_key = str(action_id)
            self.previous_frame = current
        action.reasoning = {"policy": "region-effect-full-v1"}
        return action
'''


if os.getenv("KAGGLE_IS_COMPETITION_RERUN"):
    competition = Path("/kaggle/input/competitions/arc-prize-2026-arc-agi-3")
    wheels = competition / "arc_agi_3_wheels"
    subprocess.run(
        [
            "python",
            "-m",
            "pip",
            "install",
            "--no-index",
            "--find-links",
            str(wheels),
            "arc-agi==0.9.8",
            "python-dotenv",
        ],
        check=True,
        timeout=180,
    )
    subprocess.run(
        [
            "curl",
            "--fail",
            "--retry",
            "60",
            "--retry-all-errors",
            "--retry-delay",
            "5",
            "--retry-max-time",
            "600",
            "http://gateway:8001/api/games",
        ],
        check=True,
        timeout=620,
    )
    source = competition / "ARC-AGI-3-Agents"
    work = Path("/kaggle/working/ARC-AGI-3-Agents")
    shutil.copytree(source, work, dirs_exist_ok=True)
    (work / "agents" / "templates" / "region_effect.py").write_text(AGENT_SOURCE)
    (work / "agents" / "__init__.py").write_text(
        """from typing import Type
from dotenv import load_dotenv
from .agent import Agent, Playback
from .swarm import Swarm
from .templates.region_effect import RegionEffectChampion

load_dotenv()
AVAILABLE_AGENTS: dict[str, Type[Agent]] = {
    "region-effect": RegionEffectChampion,
}
"""
    )
    (work / ".env").write_text(
        "SCHEME=http\n"
        "HOST=gateway\n"
        "PORT=8001\n"
        "ARC_API_KEY=test-key-123\n"
        "ARC_BASE_URL=http://gateway:8001/\n"
        "OPERATION_MODE=online\n"
        "ENVIRONMENTS_DIR=\n"
        "RECORDINGS_DIR=/kaggle/working/server_recording\n"
    )
    subprocess.run(
        ["python", "main.py", "--agent", "region-effect"],
        cwd=work,
        check=True,
        timeout=10800,
        env={**os.environ, "MPLBACKEND": "agg"},
    )
else:
    import pandas as pd

    pd.DataFrame(
        [["1_0", "1", True, 1]],
        columns=["row_id", "game_id", "end_of_game", "score"],
    ).to_parquet("/kaggle/working/submission.parquet", index=False)
    print("Wrote local-run placeholder submission.parquet")
