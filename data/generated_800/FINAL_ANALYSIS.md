# Final analysis of generated_800

## Final fixed dataset

- Dataset id: `prompt_radar_generated_800`
- Final archive: `data/generated_800/dataset.zip`
- Final archive SHA-256:
  `0f6770410200ae0ced25a168f67e3409271df901f5ead950b807bce8f75cb9f5`
- Stable analysis hash:
  `3b6daa5dddcbb8ae330eee10225caa03016ffd0ebaebd87daae86f63527bcb27`
- Model: `Qwen/Qwen3-Embedding-0.6B`
- Model revision:
  `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`
- Seed: `42`
- External generative API calls on the final fixed dataset: `0`

The project now contains a strict local registry entry for this exact archive.
When `analyze --enrich-clusters` is launched on this dataset, the pipeline
matches by archive hash, analysis hash, cluster fingerprint and member-run hash,
uses pre-reviewed local answers for cluster naming/economic passports and does
not spend money on external API calls.

## Validation summary

- 20 users
- 140 conversations
- 934 messages
- 800 runs
- 480 events
- 60 attachments
- 0 validation issues
- 8 prompts contain exactly 100,000 generator tokens

This final version is materially different from the previous draft of
`generated_800`; older summaries that referenced archive hash
`2e2c5d6ec80b66ca0caeb8d89e4debe571f29718a8df9a3031c2b605488f0f78`
must no longer be used.

## Final analyze run

- Command:

```powershell
python -m prompt_radar.cli analyze `
  --input data/generated_800/dataset.zip `
  --offline `
  --enrich-clusters
```

- Output:
  `outputs/prompt_radar_generated_800_20260725T103536Z`
- `precomputed_dataset_matched`: `true`
- `precomputed_enrichment_count`: `16`
- `external_generative_api_call_count`: `0`

## Qwen + HDBSCAN quality on the final dataset

- Clusters: `16`
- Predicted known coverage: `0.73375`
- Emerging coverage: `0.26125`
- Unresolved coverage: `0.005`
- Noise rate: `0.005`
- Known-use-case micro F1: `0.510797`
- Category micro F1: `0.597113`
- Discovery status accuracy: `0.85625`
- ARI: `0.501785`
- NMI: `0.720093`

Important interpretation: this is a synthetic benchmark for pipeline mechanics,
not a production-quality estimate on real KROK traffic.

## Local precomputed cluster decisions

The final fixed dataset has 16 reviewed cluster decisions:

- 8 `enrich` decisions for coherent emerging themes
- 8 `abstain` decisions for mixed, noisy or actually-known groups

This means the first part of the task is fully reproducible on the final
dataset:

- Qwen embeddings are deterministic for the fixed model revision
- HDBSCAN clustering is deterministic here because the upstream embedding and
  UMAP seed are fixed
- local cluster answers are bound to this exact archive and exact cluster
  fingerprints

For any other dataset, the architecture remains different on purpose:

- if the strict registry does not match, the pipeline does **not** reuse these
  answers;
- it must call the configured external API enrichment path or abstain,
  depending on runtime settings.

## Final economics run

- Command:

```powershell
python -m prompt_radar.cli economics `
  --analysis outputs/prompt_radar_generated_800_20260725T103536Z `
  --cost-config data/generated_800/economics_cost_config.json `
  --output outputs/prompt_radar_generated_800_20260725T103536Z/economics_final
```

- Human prompt-authoring time is still not measured in the dataset itself.
  Economics therefore uses the explicit E0 assumption from
  `data/generated_800/economics_cost_config.json`.
- AI processing time is available from the synthetic dataset and report
  metadata.
- Output quality measurements are absent, so the run produces potential ROI,
  not proven production ROI.

### Economics summary

- Runs: `800`
- Users in statistics: `20`
- Conversations in statistics: `140`
- Request types in statistics: `59`
- Total AI processing minutes: `6520.32`
- Fully loaded platform-period cost: `644,915.12 RUB`
- BASE potential saved minutes: `10,943.6067`
- BASE potential gross value: `273,590.32 RUB`
- BASE potential net value: `-371,324.80 RUB`
- BASE potential ROI: `-0.575773`

Cluster status counts:

- `POTENTIALLY_EFFECTIVE`: 27
- `POTENTIALLY_INEFFECTIVE`: 1
- `IMPOSSIBLE_TO_BREAK_EVEN`: 1
- `HIGH_RISK`: 4
- `INSUFFICIENT_EVIDENCE`: 210

These figures are internally consistent for the current assumptions, but they
should be interpreted as a sensitivity analysis until real prompt-authoring
time and reviewed quality labels are attached.

## Final reporting outputs

Analyze outputs:

- `outputs/prompt_radar_generated_800_20260725T103536Z/report.md`
- `outputs/prompt_radar_generated_800_20260725T103536Z/evaluation_final.json`
- `outputs/prompt_radar_generated_800_20260725T103536Z/pipeline_metadata.json`
- `outputs/prompt_radar_generated_800_20260725T103536Z/cluster_enrichments.json`

Economics outputs:

- `outputs/prompt_radar_generated_800_20260725T103536Z/economics_final/economics_report.md`
- `outputs/prompt_radar_generated_800_20260725T103536Z/economics_final/platform_economics.json`
- `outputs/prompt_radar_generated_800_20260725T103536Z/economics_final/cluster_economics.json`
- `outputs/prompt_radar_generated_800_20260725T103536Z/economics_final/statistics_summary.json`
- `outputs/prompt_radar_generated_800_20260725T103536Z/economics_final/statistics_report.html`

The HTML statistics report is the main “beautiful detailed stats” artifact:
it contains overall platform metrics, distribution by request type and a
separate block for each of the 20 users with counts, time and economy.
