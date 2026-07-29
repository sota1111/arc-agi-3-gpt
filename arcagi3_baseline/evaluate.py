"""Run the baseline through a repeatable subprocess contract gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any

from .contract import ContractError, validate_action, validate_observation


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def evaluate(manifest_path: Path) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(manifest_path.read_text())
    fixture = root / manifest["fixture"]["path"]
    actual_sha = _sha256(fixture)
    if actual_sha != manifest["fixture"]["sha256"]:
        raise ContractError(
            f"fixture sha256 mismatch: expected {manifest['fixture']['sha256']}, got {actual_sha}"
        )
    cases = _load_jsonl(fixture)
    observations = [validate_observation(case["observation"]) for case in cases]
    stdin = "".join(json.dumps(item, separators=(",", ":")) + "\n" for item in observations)
    expected = [case["expected_action"] for case in cases]
    runs: list[dict[str, Any]] = []
    canonical_output: str | None = None

    for repetition in range(manifest["repetitions"]):
        started = time.perf_counter()
        timed_out = False
        try:
            process = subprocess.run(
                manifest["command"],
                cwd=root,
                input=stdin,
                text=True,
                capture_output=True,
                timeout=manifest["timeout_seconds"],
                check=False,
            )
            return_code = process.returncode
            stdout = process.stdout
            stderr = process.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            return_code = None
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode(errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")
        elapsed = time.perf_counter() - started
        errors: list[str] = []
        output: list[dict[str, Any]] = []
        if timed_out:
            errors.append(f"timed out after {manifest['timeout_seconds']} seconds")
        elif return_code != 0:
            errors.append(f"exit code {return_code}: {stderr.strip()}")
        try:
            output = [json.loads(line) for line in stdout.splitlines() if line.strip()]
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON output: {exc}")
        if len(output) != len(observations):
            errors.append(f"expected {len(observations)} actions, got {len(output)}")
        for index, (action, observation) in enumerate(zip(output, observations)):
            try:
                validate_action(action, observation)
            except ContractError as exc:
                errors.append(f"case {index}: {exc}")
        if output != expected:
            errors.append("actions differ from fixture expectations")
        normalized = json.dumps(output, sort_keys=True, separators=(",", ":"))
        if canonical_output is None:
            canonical_output = normalized
        elif normalized != canonical_output:
            errors.append("output is non-deterministic")
        runs.append(
            {
                "repetition": repetition + 1,
                "duration_seconds": round(elapsed, 6),
                "exit_code": return_code,
                "errors": errors,
            }
        )

    passed_runs = sum(not run["errors"] for run in runs)
    pass_rate = passed_runs / len(runs)
    result = {
        "schema_version": 1,
        "phase": manifest["phase"],
        "candidate": manifest["candidate"],
        "champion": manifest["champion"],
        "manifest": str(manifest_path.relative_to(root)),
        "manifest_sha256": _sha256(manifest_path),
        "fixture_sha256": actual_sha,
        "repetitions": len(runs),
        "passed_runs": passed_runs,
        "pass_rate": pass_rate,
        "threshold": manifest["pass_threshold"],
        "promoted": pass_rate >= manifest["pass_threshold"],
        "runs": runs,
    }
    output_path = root / manifest["artifact"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.manifest.resolve())
    print(json.dumps(result, sort_keys=True))
    return 0 if result["promoted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
