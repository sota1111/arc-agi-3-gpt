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

## Promotion decision

The checked-in confirm manifest intentionally records
`kaggle_exec_verified: false`. Therefore the implementation is retained as an
isolated candidate and testable library, but its behavior is not wired into
`main.py`, `kaggle/kernel/submit.py`, or the champion declaration. This is the
required non-promotion/revert boundary: measurements remain available while
production behavior stays `deterministic-legal-v1`.
