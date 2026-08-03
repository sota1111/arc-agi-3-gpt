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
python3 -m arcagi3_baseline.compare --manifest eval/manifests/agent-screen.json
python3 -m arcagi3_baseline.compare --manifest eval/manifests/agent-confirm.json
python3 scripts/build_candidate_artifact.py --check
python3 -m arcagi3_baseline.exec_gate --manifest eval/manifests/exec-gate.json
```

The fixed real-game comparison contract is
`eval/manifests/four-condition-real-game.json`. It describes 36 isolated runs
(three games × three trials × four Responses configurations), records complete
performance/token/cost metrics, and automatically applies the promotion limits.
See `docs/four-condition-real-game-evaluation.md` for adapter and gate details.

`main.py` accepts one JSON observation per line and emits exactly one JSON
action per line. Diagnostics go to stderr. This makes a fresh subprocess run
equivalent to the competition's `exec` loading boundary and keeps stdout safe
for machine consumption.

## Baseline

The comparison baseline is `deterministic-legal-v1`:

- `NOT_PLAYED` and `GAME_OVER` observations produce `RESET` (`id=0`).
- Otherwise the smallest advertised non-reset `available_actions` id is used.
- `ACTION6` receives deterministic coordinates `(0, 0)`.
- If a running game advertises no usable action, the safe fallback is `RESET`.

This policy is intentionally weak but deterministic and contract-safe. Agent
candidates in later issues must be compared with this champion using the same
screen and confirm manifests.

## Stateful GPT candidate

`StatefulGPTAgent` normalizes each observation into a bounded history of frame
digests, changed fields, and prior action ids. It requests a single official
action-schema object, validates it against the current advertised legal actions,
retries malformed/empty/timeout responses, then falls back to
`deterministic-legal-v1`. The fallback is local and deterministic, so model
failure cannot terminate a game or emit an illegal action.

For live model calls, `ResponsesRuntime` adapts an OpenAI client to this agent
contract. It chains each successful `response.id` through
`previous_response_id`, resends fixed `instructions` on every turn, and can
opt into retained reasoning (`reasoning.context="all_turns"`) plus server-side
compaction (`context_management` with a positive `compact_threshold`). Because
the server owns the conversation chain, the agent does not also send its
bounded rolling memory. A changed `game_id` resets the response chain.

The SOT-2132 replay compares the baseline, no-memory, no-constraint, and full
stateful/constraint variants with seed `2132`. The fixture model is deliberately
offline and costs zero; it exercises the decision boundary without credentials.
SOT-2184 freezes the candidate as
`artifacts/candidates/stateful-gpt-legal-v1.zip`. The archive has no external
dependencies and exposes a JSON-lines stdin/stdout entrypoint. Its isolated
exec gate verifies the artifact hash, imports, action schema, fallback behavior,
and an enforced process timeout. The candidate passed screen and independent
confirm without reducing completion and improved the progress proxy, so it
became the SOT-2184 champion and the baseline for SOT-2185. The previously
registered Kaggle kernel remains
`deterministic-legal-v1` until the follow-up real Kaggle proof.

## Connected-region exploration champion

SOT-2185 adds four-neighbour connected components for frame changes and a
bounded per-action/coordinate effect history. The policy targets action 6 at
the largest changed-region centre, then prioritizes unexplored action keys and
keys with prior effects. The tracker retains at most eight observations,
actions, and outcomes per key.

The screen cohort compares the SOT-2184 champion, region-only, effect-only, and
full variants. Only its winning full variant proceeds to a distinct confirm
cohort. `region-effect-full-v1` improved confirm progress proxy from 0.02 to
0.48, completion from 0.0 to 0.2, unique effective actions from 1 to 3, and
no-op rate from 0.8 to 0.2, with zero faults and no p95 regression. Its
dependency-free exec artifact passed hash, import, stdin/stdout, schema,
fallback, and hard-timeout checks, so it is the repository champion passed to
SOT-2186 for real Kaggle proof.

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
A candidate is promoted to the repository champion only after screen, confirm,
and the offline Kaggle-shaped exec gate pass. A real kernel run and submission
remain a separate downstream gate; the manifest records the registered Kaggle
policy separately so those states cannot be confused.

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
