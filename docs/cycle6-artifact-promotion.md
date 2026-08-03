# Cycle 6 artifact promotion decision

SOT-2361 produced no promotion candidate. Its fixed four-condition screen and
independent confirm evidence is `inconclusive` because the Responses features
were not exercised without credentials. Accordingly, SOT-2362 does not package
that diagnostic selection and does not run the downstream exec gate.

`eval/manifests/cycle6-artifact-promotion.json` pins the source manifest,
screen, confirm, and summary hashes. It also maps that outcome to the unchanged
`region-effect-full-v1` candidate/champion artifact. Run:

```bash
python scripts/verify_cycle6_artifact_promotion.py
```

The verifier rejects a packaging claim unless the upstream summary is promoted,
names a candidate, and routes it to `exec-compatibility`. For this no-promotion
path it instead verifies screen/confirm fingerprints, the revert flag, preserved
candidate/champion hashes, skipped exec status, and that no Kaggle submission
was performed.
