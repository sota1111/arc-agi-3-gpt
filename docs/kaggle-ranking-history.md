# Kaggle ranking history

- Competition: [ARC Prize 2026 — ARC-AGI-3](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3)
- Kaggle team: `sota1111`
- Lineage: GPT

| Observed at (UTC) | Official team rank | Teams | This lineage's observed public score |
| --- | ---: | ---: | --- |
| 2026-07-26 13:38 | 1,782 | 1,922 | ERROR (unscored) |
| 2026-07-28 15:57 | 1,418 | 1,949 | ERROR (no completed GPT score) |
| 2026-07-29 01:24 | 1,420 | 1,953 | **0.08 COMPLETE** (`55067146`) |
| 2026-07-30 01:23 | pending | pending | **0.00 COMPLETE** (`55095979`, `region-effect-full-v1`) |

The official rank is shared by the GPT and Claude repositories because both
submit under the same Kaggle team. Submission `55067146`, produced by kernel
`sota1111/arc-agi-3-gpt-registered-champion` version 5, is the first completed
score attributed to the GPT lineage.

The separately evaluated `stateful-gpt-legal-v1` candidate is not the submitted
champion: its confirm artifact still records `kaggle_exec_verified: false`.
Production, the packaged artifact, and the submission therefore consistently
remain `deterministic-legal-v1`. A second submission was not made on 2026-07-29
because the competition's configured daily cap of one had already been consumed
by `55067146`. Resume after the next daily reset by pushing a newly verified
kernel version and submitting its generated `submission.parquet`.

Kernel version 6 and submission `55095979` completed. The candidate improved
the fixed local progress proxy but scored `0.00`, below the prior GPT
submission's `0.08`; the next cycle must use this production mismatch when
deciding whether to retain or replace the repository champion. The daily
allowance is exhausted, so no duplicate submission was attempted.

Source: Kaggle CLI `competitions list`, `kernels status`, and `competitions
submissions`. Earlier official-rank snapshots were not retained, so they are
not reconstructed or estimated.
