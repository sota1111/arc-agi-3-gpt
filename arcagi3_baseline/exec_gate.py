"""Offline Kaggle-shaped exec gate for a frozen candidate artifact."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from .contract import validate_action, validate_observation

ROOT = Path(__file__).resolve().parents[1]
STDLIB_IMPORTS = {
    "__future__",
    "collections",
    "dataclasses",
    "json",
    "os",
    "sys",
    "time",
    "typing",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _imports(source: str) -> set[str]:
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".", 1)[0])
    return names


def evaluate(manifest_path: Path, *, write_artifact: bool = True) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text())
    artifact = ROOT / manifest["candidate_artifact"]["path"]
    actual_hash = _sha256(artifact)
    if actual_hash != manifest["candidate_artifact"]["sha256"]:
        raise ValueError("candidate artifact sha256 mismatch")
    fixture = ROOT / manifest["fixture"]["path"]
    if _sha256(fixture) != manifest["fixture"]["sha256"]:
        raise ValueError("fixture sha256 mismatch")
    records = [json.loads(line) for line in fixture.read_text().splitlines() if line.strip()]

    with tempfile.TemporaryDirectory() as directory:
        isolated = Path(directory)
        with zipfile.ZipFile(artifact) as archive:
            archive.extractall(isolated)
            member_names = sorted(archive.namelist())
        imported: set[str] = set()
        for source_path in isolated.rglob("*.py"):
            imported.update(_imports(source_path.read_text()))
        external = sorted(imported - STDLIB_IMPORTS)
        command = [
            sys.executable,
            "-I",
            "-c",
            (
                "import sys;sys.path.insert(0,'.');"
                "from arcagi3_baseline.candidate_entrypoint import main;"
                "raise SystemExit(main())"
            ),
        ]
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": "",
            "PYTHONNOUSERSITE": "1",
        }
        completed = subprocess.run(
            command,
            cwd=isolated,
            env=environment,
            input=fixture.read_text(),
            text=True,
            capture_output=True,
            timeout=manifest["limits"]["process_timeout_seconds"],
            check=False,
        )
        outputs = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
        schema_valid = completed.returncode == 0 and len(outputs) == len(records)
        fallback_count = 0
        if schema_valid:
            for record, action in zip(records, outputs, strict=True):
                observation = validate_observation(record["observation"])
                validate_action(action, observation)
                reasoning = action.get("reasoning", {})
                fallback_count += int(isinstance(reasoning, dict) and "fallback" in reasoning)
        timeout_enforced = False
        timeout_environment = {**environment, "ARC_EXEC_STARTUP_DELAY_SECONDS": "0.2"}
        try:
            subprocess.run(
                command,
                cwd=isolated,
                env=timeout_environment,
                input="",
                text=True,
                capture_output=True,
                timeout=manifest["limits"]["timeout_probe_seconds"],
                check=False,
            )
        except subprocess.TimeoutExpired:
            timeout_enforced = True

    checks = {
        "artifact_hash": True,
        "dependency_free": not external,
        "standard_io": schema_valid,
        "action_schema": schema_valid,
        "fallback": fallback_count >= manifest["limits"]["minimum_fallbacks"],
        "hard_timeout": timeout_enforced,
    }
    result = {
        "schema_version": 1,
        "candidate": manifest["candidate"],
        "artifact": str(artifact.relative_to(ROOT)),
        "artifact_sha256": actual_hash,
        "artifact_members": member_names,
        "manifest": str(manifest_path.relative_to(ROOT)),
        "manifest_sha256": _sha256(manifest_path),
        "fixture_sha256": _sha256(fixture),
        "command": command,
        "limits": manifest["limits"],
        "checks": checks,
        "external_imports": external,
        "records": len(records),
        "fallback_count": fallback_count,
        "passed": all(checks.values()),
    }
    if write_artifact:
        output = ROOT / manifest["artifact"]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.manifest.resolve())
    print(json.dumps(result, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
