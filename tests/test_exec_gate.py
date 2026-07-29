import json
import zipfile

from arcagi3_baseline.exec_gate import ROOT, evaluate
from scripts.build_candidate_artifact import build


def test_candidate_artifact_is_reproducible() -> None:
    manifest = json.loads((ROOT / "candidate/manifest.json").read_text())
    artifact, first = build()
    artifact, second = build()
    assert first == second == manifest["artifact"]["sha256"]
    with zipfile.ZipFile(artifact) as archive:
        assert sorted(archive.namelist()) == sorted(manifest["source_files"])


def test_candidate_runs_from_frozen_artifact_with_standard_io() -> None:
    result = evaluate(ROOT / "eval/manifests/exec-gate.json", write_artifact=False)
    assert result["passed"]
    assert result["checks"] == {
        "artifact_hash": True,
        "dependency_free": True,
        "standard_io": True,
        "action_schema": True,
        "fallback": True,
        "hard_timeout": True,
    }


def test_checked_in_exec_gate_result_is_reproducible() -> None:
    expected = json.loads((ROOT / "artifacts/exec-gate/result.json").read_text())
    actual = evaluate(ROOT / "eval/manifests/exec-gate.json", write_artifact=False)
    assert actual == expected
