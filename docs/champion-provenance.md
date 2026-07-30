# GPT champion provenance

The canonical machine-readable record is
[`champion/manifest.json`](../champion/manifest.json). The repository champion
is `region-effect-full-v1`. Its manifest pins the candidate sources, reproducible
ZIP, screen and independent confirm results, and offline Kaggle-shaped exec gate
by SHA-256.

Run these commands to reconstruct and verify the decision:

```bash
python3 scripts/build_candidate_artifact.py --check
python3 -m arcagi3_baseline.compare --manifest eval/manifests/agent-screen.json
python3 -m arcagi3_baseline.compare --manifest eval/manifests/agent-confirm.json
python3 -m arcagi3_baseline.exec_gate --manifest eval/manifests/exec-gate.json
python3 scripts/build_champion_artifact.py --check
```

Kaggle kernel version 6 embeds the same connected-region/effect-history policy
and completed its ordinary execution. Code-competition submission `55095979`
completed its real rerun with public score `0.00`. This trails the historical
`deterministic-legal-v1` score of `0.08`; both results remain explicit for the
next promotion decision.
