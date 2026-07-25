# Economics assumptions for generated_800

- The observed run window is 2026-07-01 09:00 UTC through
  2026-07-07 11:38 UTC: 6.109722 days, or 0.203657407 months using a
  30-day month.
- The dataset does not contain measured human prompt-authoring time.
  `default_prompt_minutes=3` is an E0 sensitivity assumption, not telemetry.
- AI wall time is taken from each run's `started_at` and `finished_at`.
- In the absence of provider GPU seconds or usage tokens, locally measured
  `raw_prompt_token_count` is used only as a GPU cost allocation proxy.
- There is no reviewed business-output quality file. Results therefore remain
  potential estimates and must not be presented as proven actual ROI.
- Precomputed cluster passports are E0 reviewed hypotheses. Mixed, known-only,
  and synthetic-context clusters explicitly abstain from economics.
