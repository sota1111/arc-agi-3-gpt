# GPT champion provenance

The canonical machine-readable record is
[`champion/manifest.json`](../champion/manifest.json). It pins:

- production policy `deterministic-legal-v1`;
- introduction commit `7a145f8d68a93c09a51c69a2bce96388f7cba632`;
- every packaged source, screen/confirm manifest, and result by SHA-256;
- Kaggle kernel `sota1111/arc-agi-3-gpt-registered-champion` version 5;
- completed submission `55067146` and public score `0.08`;
- the explicit non-promotion decision for `stateful-gpt-legal-v1`.

Run `python3 scripts/build_champion_artifact.py --check` to reconstruct
`artifacts/champion/deterministic-legal-v1.zip` byte-for-byte and verify all
inputs. The archive contains only the Kaggle script and metadata, uses fixed
timestamps and permissions, and needs no network access to build.

The entrypoint gate parses and compiles both `submit.py` and its embedded agent
source through Python's `exec`-compatible compiler. The real Kaggle kernel
completed and produced `submission.parquet`; competition submission `55067146`
then completed with public score `0.08`.
