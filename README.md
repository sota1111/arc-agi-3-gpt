# ARC-AGI-3 GPT baseline

A deterministic, dependency-free baseline for the ARC Prize 2026 ARC-AGI-3
observation/action contract. It gives later GPT agents a reproducible champion,
a local `exec`-equivalent contract harness, and a Kaggle submission entrypoint.

## Quick start

Python 3.11 or newer is the only runtime dependency.

```bash
python3 main.py --input tests/fixtures/replay.jsonl
python3 -m arcagi3_baseline.evaluate --manifest eval/manifests/screen.json
python3 -m arcagi3_baseline.evaluate --manifest eval/manifests/confirm.json
```

`main.py` accepts one JSON observation per line and emits exactly one JSON
action per line. Diagnostics go to stderr. This makes a fresh subprocess run
equivalent to the competition's `exec` loading boundary and keeps stdout safe
for machine consumption.

## Baseline/champion

The current baseline and champion are both `deterministic-legal-v1`:

- `NOT_PLAYED` and `GAME_OVER` observations produce `RESET` (`id=0`).
- Otherwise the smallest advertised non-reset `available_actions` id is used.
- `ACTION6` receives deterministic coordinates `(0, 0)`.
- If a running game advertises no usable action, the safe fallback is `RESET`.

This policy is intentionally weak but deterministic and contract-safe. Agent
candidates in later issues must be compared with this champion using the same
screen and confirm manifests.

## Evaluation and promotion

The checked-in manifests pin the command, fixture SHA-256, repetitions,
timeout, and pass threshold. Results are written to
`artifacts/<phase>/result.json`.

```bash
python3 -m arcagi3_baseline.evaluate --manifest eval/manifests/screen.json
python3 -m arcagi3_baseline.evaluate --manifest eval/manifests/confirm.json
```

Screen runs 3 repetitions; confirm runs 10. Both require every invocation to
exit successfully, return the expected legal action for every observation,
stay deterministic, and complete each repetition within the manifest timeout.
A candidate is promoted only after both phases pass and the Kaggle kernel run
finishes successfully. Otherwise revert the candidate behavior, retain
`deterministic-legal-v1`, and record the rejection reason in the result
artifact/docs.

## Kaggle execution

`kaggle/kernel/submit.py` follows the official competition rerun contract:
offline-install the supplied `arc-agi` wheels, wait for the gateway, copy the
official `ARC-AGI-3-Agents` source, register the deterministic agent, and invoke
its official `main.py`. A non-rerun kernel execution writes a schema-correct
placeholder `submission.parquet`, as required for kernel version creation.

```bash
kaggle kernels push -p kaggle/kernel
kaggle kernels status sota1111/arc-agi-3-gpt-registered-champion
kaggle kernels output sota1111/arc-agi-3-gpt-registered-champion -p /tmp/arc3-output
```

The kernel is intentionally internet-disabled. During competition reruns the
gateway and official competition assets are provided by Kaggle. A local
fixture pass proves the observation/action boundary, but it does not substitute
for a successful competition rerun before promoting a stronger candidate.

## Pinned official contract

The implementation targets the competition files published on 2026-04-17:
`arcengine==0.9.3` and `arc-agi==0.9.8`. Observations use `game_id`, `frame`,
`state`, `levels_completed`, `win_levels`, `guid`, `full_reset`, and
`available_actions`. Actions use integer `id` 0–7, `data.game_id`, optional
`x`/`y` in 0–63 for action 6, and JSON-serializable `reasoning` no larger than
16 KiB.
