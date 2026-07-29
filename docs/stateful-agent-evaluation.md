# Stateful legal-action GPT candidate evaluation

## Design

`stateful-gpt-legal-v1` keeps at most eight observation deltas and prior action
ids. Frames are represented by deterministic compact digests rather than copied
into prompt history. Model output is parsed as one JSON object and checked by
the pinned official action validator. Empty, malformed, illegal, or timed-out
responses receive one retry and then the deterministic champion action.

## Reproducible comparison

Both phases pin seed `2132` and the SHA-256 of
`tests/fixtures/agent_replay.jsonl`. Screen repeats the fixture 3 times and
confirm repeats it 20 times. Screen compares:

- `deterministic-legal-v1`
- `gpt-no-memory-v1`
- `gpt-no-constraints-v1`
- `stateful-gpt-legal-v1`

Confirm compares only the baseline and screen winner. Metrics are completion
rate, legal-action rate, mean progress proxy, fallback count, runtime, and
estimated cost. Promotion requires legal-action rate 1.0, no completion-rate
regression, progress improvement of at least 0.1, and a verified Kaggle exec
for confirm.

## Artifact and exec gate

`candidate/manifest.json` freezes the four dependency-free Python sources and
their hashes. `scripts/build_candidate_artifact.py --check` reconstructs the
ZIP byte-for-byte. `eval/manifests/exec-gate.json` then extracts that exact ZIP
to a temporary directory and launches it with isolated Python, an empty
`PYTHONPATH`, and JSON-lines standard I/O. The checked-in gate proves:

- no imports outside Python's standard library and the embedded package;
- one schema-valid legal action for every production-shaped record;
- deterministic fallback for empty, malformed, illegal, and timeout responses;
- a hard subprocess timeout, independently probed with delayed startup.

## Promotion decision

The frozen artifact won screen and the independent 20-repetition confirm:
legal-action rate `1.0`, completion `0.3333` versus `0.0`, and progress proxy
`0.4333` versus `0.2500`. The exec gate passed all six checks. Therefore
`stateful-gpt-legal-v1` is promoted in `champion/manifest.json`. The manifest
keeps the previously registered Kaggle submission (`deterministic-legal-v1`)
separate and names the real Kaggle kernel/submission proof as the next gate.
