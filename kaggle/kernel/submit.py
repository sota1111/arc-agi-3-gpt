"""Kaggle entrypoint for the deterministic ARC-AGI-3 baseline."""

import os
import shutil
import subprocess
from pathlib import Path

AGENT_SOURCE = r'''
from typing import Any
from arcengine import FrameData, GameAction, GameState
from ..agent import Agent

class DeterministicLegal(Agent):
    MAX_ACTIONS = 80

    def is_done(self, frames: list[FrameData], latest_frame: FrameData) -> bool:
        return latest_frame.state is GameState.WIN

    def choose_action(
        self, frames: list[FrameData], latest_frame: FrameData
    ) -> GameAction:
        if latest_frame.state in (GameState.NOT_PLAYED, GameState.GAME_OVER):
            action_id = 0
        else:
            available = sorted(set(latest_frame.available_actions))
            action_id = next((value for value in available if value != 0), 0)
        action = GameAction.from_id(action_id)
        data: dict[str, Any] = {"game_id": self.game_id}
        if action_id == 6:
            data.update(x=0, y=0)
        action.set_data(data)
        action.reasoning = {"policy": "deterministic-legal-v1"}
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
    (work / "agents" / "templates" / "deterministic_legal.py").write_text(AGENT_SOURCE)
    (work / "agents" / "__init__.py").write_text(
        """from typing import Type
from dotenv import load_dotenv
from .agent import Agent, Playback
from .swarm import Swarm
from .templates.deterministic_legal import DeterministicLegal

load_dotenv()
AVAILABLE_AGENTS: dict[str, Type[Agent]] = {
    "deterministic-legal": DeterministicLegal,
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
        ["python", "main.py", "--agent", "deterministic-legal"],
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
