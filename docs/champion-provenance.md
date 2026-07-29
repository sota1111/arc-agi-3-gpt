# GPT champion provenance

The canonical machine-readable record is
[`champion/manifest.json`](../champion/manifest.json). The repository champion
is `stateful-gpt-legal-v1`. Its manifest pins the candidate sources, reproducible
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

The latest registered Kaggle kernel and completed submission still used
`deterministic-legal-v1` (kernel version 5, submission `55067146`, public score
`0.08`). That historical production state is recorded separately from the
promoted repository champion. The next issue must run the stateful artifact in
the real Kaggle kernel/submission environment before updating those fields.
