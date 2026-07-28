import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from arcagi3_baseline.contract import ContractError, choose_action, validate_action

ROOT = Path(__file__).resolve().parents[1]


def test_fixture_entrypoint_matches_expected_actions() -> None:
    fixture = ROOT / "tests/fixtures/replay.jsonl"
    cases = [json.loads(line) for line in fixture.read_text().splitlines()]
    process = subprocess.run(
        [sys.executable, "main.py"],
        cwd=ROOT,
        input="".join(json.dumps(case["observation"]) + "\n" for case in cases),
        text=True,
        capture_output=True,
        check=True,
    )
    assert [json.loads(line) for line in process.stdout.splitlines()] == [
        case["expected_action"] for case in cases
    ]


def test_policy_is_deterministic() -> None:
    observation = {
        "game_id": "g",
        "frame": [],
        "state": "NOT_FINISHED",
        "available_actions": [7, 3, 6],
    }
    assert choose_action(observation) == choose_action(observation)
    assert choose_action(observation)["id"] == 3


def test_rejects_unavailable_action() -> None:
    observation = {
        "game_id": "g",
        "frame": [],
        "state": "NOT_FINISHED",
        "available_actions": [2],
    }
    with pytest.raises(ContractError, match="not advertised"):
        validate_action(
            {"id": 3, "data": {"game_id": "g"}, "reasoning": None},
            observation,
        )


def test_complex_action_coordinates_are_in_contract_range() -> None:
    observation = {
        "game_id": "g",
        "frame": [],
        "state": "NOT_FINISHED",
        "available_actions": [6],
    }
    assert choose_action(observation)["data"] == {"game_id": "g", "x": 0, "y": 0}


def test_entrypoint_rejects_invalid_observation_without_stdout() -> None:
    process = subprocess.run(
        [sys.executable, "main.py"],
        cwd=ROOT,
        input='{"game_id": 3}\n',
        text=True,
        capture_output=True,
        check=False,
    )
    assert process.returncode == 2
    assert process.stdout == ""
    assert "game_id must be a string" in process.stderr


def test_embedded_kaggle_agent_source_compiles() -> None:
    module = ast.parse((ROOT / "kaggle/kernel/submit.py").read_text())
    assignment = next(
        node
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "AGENT_SOURCE"
            for target in node.targets
        )
    )
    source = ast.literal_eval(assignment.value)
    compile(source, "deterministic_legal.py", "exec")
