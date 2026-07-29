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
        assert archive.namelist() == ["kernel-metadata.json", "submit.py"]


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
    compile(embedded, "deterministic_legal.py", "exec")


def test_all_provenance_hashes_match() -> None:
    manifest = json.loads((ROOT / "champion/manifest.json").read_text())
    for path, expected in manifest["package_files"].items():
        assert sha256(ROOT / path) == expected
    evaluation = manifest["evaluation"]
    for gate in ("screen", "confirm"):
        assert sha256(ROOT / evaluation[f"{gate}_manifest"]) == evaluation[
            f"{gate}_manifest_sha256"
        ]
        assert sha256(ROOT / evaluation[f"{gate}_result"]) == evaluation[
            f"{gate}_result_sha256"
        ]
