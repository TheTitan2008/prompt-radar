# Final submission checklist

Use this checklist after the replacement dataset is ready.

## Required before the final demo

- Validate the archive with `prompt-radar validate`.
- Run the same archive twice and compare analysis/configuration hashes,
  cluster fingerprints and the evaluation metrics.
- Confirm all expected runs have `prompt_minutes`; missing values must remain
  unknown, never zero.
- Review the 31 known-use-case passports with a process owner.
- Review every emerging-cluster label and economic passport used in slides.
- Add quality evaluations for the runs used to support an actual ROI claim.
- Confirm the executive report contains frequency, dynamics, problem signals
  and recommended actions.
- Confirm the economics report shows acceptable data coverage and confidence
  intervals, not only potential ROI.
- Verify that immutable-demo enrichments match archive SHA-256 and all binding
  hashes. Do not bind by filename alone.
- Run `python -m pytest -m "not integration"` and the real cached-Qwen
  integration test.
- Copy the final curated reports into a version-controlled submission folder;
  normal timestamped `outputs/` are intentionally ignored.
- Record the exact Python version, model revision, seed, configuration hash,
  archive SHA-256 and commands used for the final run.
- Make the first intentional Git commit and tag the submitted revision.

## Claims that must stay qualified

- Cosine similarity is not a probability.
- HDBSCAN cluster IDs are not persistent business identifiers.
- E0 model estimates are hypotheses, not measured savings.
- Potential ROI assumes successful output; actual ROI requires quality
  evidence and a validated manual baseline.
- A fixed random seed improves reproducibility but cannot by itself guarantee
  bit-for-bit identity across different hardware and dependency versions.
