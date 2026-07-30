import ast
import json
import zipfile

from scripts.build_champion_artifact import ROOT, build, sha256


def test_champion_package_is_reproducible_and_matches_manifest() -> None:
    manifest = json.loads((ROOT / "champion/manifest.json").read_text())
    output, first = build()
    output, second = build()
    assert first == second == manifest["artifact"]["sha256"]
    with zipfile.ZipFile(output) as archive:
        candidate = json.loads((ROOT / manifest["candidate_manifest"]).read_text())
        assert sorted(archive.namelist()) == sorted(candidate["source_files"])


def test_kaggle_entrypoint_and_embedded_agent_are_exec_compatible() -> None:
    source = (ROOT / "kaggle/kernel/submit.py").read_text()
    module = ast.parse(source)
    compile(module, "submit.py", "exec")
    assignment = next(
        node
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "AGENT_SOURCE"
            for target in node.targets
        )
    )
    embedded = ast.literal_eval(assignment.value)
    compile(embedded, "region_effect.py", "exec")
    assert "class RegionEffectChampion" in embedded
    assert '"policy": "region-effect-full-v1"' in embedded


def test_all_provenance_hashes_match() -> None:
    manifest = json.loads((ROOT / "champion/manifest.json").read_text())
    assert sha256(ROOT / manifest["candidate_manifest"]) == manifest[
        "candidate_manifest_sha256"
    ]
    evaluation = manifest["evaluation"]
    for gate in ("screen", "confirm", "exec"):
        assert sha256(ROOT / evaluation[f"{gate}_manifest"]) == evaluation[
            f"{gate}_manifest_sha256"
        ]
        assert sha256(ROOT / evaluation[f"{gate}_result"]) == evaluation[
            f"{gate}_result_sha256"
        ]
