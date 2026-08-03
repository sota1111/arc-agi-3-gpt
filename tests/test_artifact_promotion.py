import json

import pytest

from arcagi3_baseline.artifact_promotion import ROOT, evaluate

MANIFEST = ROOT / "eval/manifests/cycle6-artifact-promotion.json"


def test_non_promoted_candidate_is_not_packaged() -> None:
    result = evaluate(MANIFEST)
    assert result["passed"] is True
    assert result["decision"] == "inconclusive"
    assert result["promotion_candidate"] is None
    assert result["packaging"]["performed"] is False
    assert result["exec_compatibility"]["status"] == "not-run"
    assert all(result["checks"].values())


def test_packaging_cannot_be_claimed_without_promoted_evidence(tmp_path) -> None:
    manifest = json.loads(MANIFEST.read_text())
    manifest["packaging"]["performed"] = True
    changed = tmp_path / "manifest.json"
    changed.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="packaging decision"):
        evaluate(changed)
