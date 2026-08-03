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
Kaggle submission and preserves the screen-to-confirm ordering. This issue adds
and validates the evaluation infrastructure only; it does not claim a live API
comparison or promote an implementation candidate.
