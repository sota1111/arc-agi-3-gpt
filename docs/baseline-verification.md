# Baseline verification record

## Contract provenance

- Competition: `arc-prize-2026-arc-agi-3`
- Competition asset timestamp inspected: 2026-04-17
- Official framework: `ARC-AGI-3-Agents`
- Pinned wheels: `arc-agi==0.9.8`, `arcengine==0.9.3`
- Baseline/champion: `deterministic-legal-v1`

The fixture and validators cover initial reset, a legal simple action, the
coordinate-bearing complex action, and reset after game over. Invalid input,
unavailable actions, malformed output, subprocess errors, timeouts, and
non-deterministic output are rejected by the entrypoint or evaluation harness.

## SOT-2131 measurements

| Gate | Manifest | Result |
| --- | --- | --- |
| Screen | `eval/manifests/screen.json` | 3/3 passed, pass rate 1.0 |
| Confirm | `eval/manifests/confirm.json` | 10/10 passed, pass rate 1.0 |
| Unit | `python3 -m pytest -q` | 5 passed |
| Lint | `uvx ruff check .` | passed |
| Type check | `uvx --with pytest pyright arcagi3_baseline main.py tests` | passed |
| Clean runtime | `uv run --isolated --no-project python main.py --input tests/fixtures/replay.jsonl` | passed |
| Kaggle kernel | registered champion, version 5 | COMPLETE; output schema inspected |

The local and kernel gates promote the initial baseline because there is no
prior behavior to replace. Future candidates that fail screen or confirm must
be reverted while this champion and their rejection artifact remain recorded.
