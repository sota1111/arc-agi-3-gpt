# SOT-2185 connected-region / action-effect evaluation

## Decision

`region-effect-full-v1` is promoted from repository champion
`stateful-gpt-legal-v1`. The registered Kaggle submission remains unchanged;
SOT-2186 owns the real kernel/submission proof.

## Reproduction

```bash
python3 -m arcagi3_baseline.exploration_compare --manifest eval/manifests/region-screen.json
python3 -m arcagi3_baseline.exploration_compare --manifest eval/manifests/region-confirm.json
python3 scripts/build_candidate_artifact.py --check
python3 -m arcagi3_baseline.exec_gate --manifest eval/manifests/exec-gate.json
```

The screen and confirm manifests pin distinct fixture hashes and cohort names.
The screen result records every ablation that clears the safety/progress
threshold and explicitly records `region-effect-full-v1` as
`selected_for_confirm`; the confirm manifest contains only the existing
champion and that selected candidate.

## Metrics

| Confirm metric | stateful-gpt-legal-v1 | region-effect-full-v1 |
| --- | ---: | ---: |
| legal action rate | 1.0 | 1.0 |
| completion rate | 0.0 | 0.2 |
| progress proxy | 0.02 | 0.48 |
| unique effective actions | 1 | 3 |
| no-op rate | 0.8 | 0.2 |
| faults | 0 | 0 |
| p95 limit | ≤ 0.05s | ≤ 0.05s |

The full candidate clears the required +0.2 progress margin, preserves legal
actions and faults, improves completion, and stays below the same p95 bound.
The frozen ZIP is dependency-free and passes the Kaggle-shaped exec gate,
including deterministic fallback and hard-timeout enforcement.
