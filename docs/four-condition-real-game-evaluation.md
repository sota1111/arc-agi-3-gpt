# Fixed four-condition real-game evaluation

`eval/manifests/four-condition-real-game.json` is the reproducible contract for
comparing baseline, retained reasoning only, compaction only, and both features.
It pins games `ls20`, `ft09`, and `sp80`, three trials with seeds 2191–2193, and
an action budget of 100. Production binds the official ARC gateway through the
`GameExecutor` protocol; each factory call receives a unique response-chain id,
so no chain crosses a game, trial, condition, or Linear issue boundary.

The machine-readable artifact contains score, level completion, actions, input,
output, and reasoning tokens, wall time, and API cost for every run. Candidates
advance only when score improves, completion does not regress, and total tokens,
cost, and latency remain within 1.1x, 1.1x, and 1.2x of baseline respectively.
An advancing candidate is handed to the downstream exec-compatibility gate.
A rejected candidate must be reverted and its evidence documented before the
next axis is attempted.

This harness exposes no submission operation. Its manifest explicitly forbids
Kaggle submission and preserves the screen-to-confirm ordering.

SOT-2361 ran the pinned local implementations of all three games for the full
36-run screen cohort. The repository environment did not contain an
`OPENAI_API_KEY`, so the run used an equal deterministic policy for all four
conditions. This intentionally does **not** claim to exercise Responses
retained reasoning or server compaction. It measures the real-game execution
boundary and resource/accounting pipeline, and records the feature comparison
as `inconclusive`.

`artifacts/four-condition-real-game/screen.json` contains 36 unique response
chain identities. A diagnostic lexical tie-break selected `compaction` for an
independent 18-run confirm cohort in
`artifacts/four-condition-real-game/confirm.json` (baseline plus selection).
The cohort names, result fingerprints, environment metadata fingerprint, every
required KPI, threshold check, and the no-submission flag are stored in those
artifacts. `summary.json` records that no candidate advances to exec
compatibility and that the candidate change was reverted. A credentialed run
is required before this axis can be promoted or rejected on Responses behavior.

After installing the pinned competition wheels, reproduce the evidence with:

```bash
python scripts/run_four_condition_real_games.py \
  --environments /path/to/environment_files
```
