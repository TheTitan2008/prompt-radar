# Economics Baseline and Episodes

This note explains the second economics layer additions that keep Prompt Radar
auditable while preserving a clear demo interpretation of ROI.

## Baseline

`manual_minutes` means the expected manual/organizational effort to complete
the business task without the agent platform: reading source materials,
searching internal systems, moving data between tools, Excel work, checking and
preparing the final answer.

Supported baseline routes:

- `baseline_manual`
- `baseline_colleague`

Every baseline carries `baseline_evidence_source`:

- `MODEL_ESTIMATE`
- `EXPERT_REVIEWED`
- `PROCESS_OWNER_APPROVED`
- `MEASURED`

Potential ROI may use any source. Proven economics requires a baseline source
of `PROCESS_OWNER_APPROVED` or `MEASURED` plus sufficient quality evidence and
coverage. A pure `MODEL_ESTIMATE` stays potential-only.

## Run Adjustment

A cluster passport describes a typical task. Each run receives an adjusted
baseline:

```text
M_run = M_cluster * size_factor * complexity_factor * attachment_factor
```

The run ledger stores:

- `baseline_cluster_minutes_low/base/high`
- `size_factor`
- `complexity_factor`
- `attachment_factor`
- `adjusted_manual_minutes_low/base/high`
- `baseline_evidence_source`
- `baseline_type`
- `baseline_assumptions`

Factors are derived from already available analysis data: prompt length,
token count, attachment count and volume, long-context signals, multi-goal
signals, category and known-use-case hints. Weak inputs are recorded as
assumptions. In the demo configuration factors do not reduce a normal task
below the passport baseline; they mainly increase the baseline for larger,
file-heavy or multi-step tasks.

## Business Task Episodes

Several technical runs may be one business task: draft a report, fix it, and
redraft a table. Prompt Radar therefore adds `business_task_episode_id`.

Value is counted once per episode. Cost is counted for every run inside the
episode, including failed, partial and cancelled attempts.

## Unknown Value

Unknown tasks are not removed from platform economics. If value is unknown,
the conservative platform view treats value as zero and keeps the allocated
cost in the denominator.

Platform outputs include:

- `insufficient_evidence_runs`
- `insufficient_evidence_cost`
- `insufficient_evidence_token_cost`
- `insufficient_evidence_share`

## Cluster Homogeneity

HDBSCAN clusters are text clusters. They are not automatically business
scenarios. Cluster economics therefore exposes:

- `cluster_coherence`
- `economic_homogeneity`
- `economic_passport_status`
- `economic_passport_reason`

Only economically homogeneous clusters should be used for strong ROI claims.
