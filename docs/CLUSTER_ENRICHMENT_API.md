# Emerging-cluster enrichment API

## Purpose

The API is used only after known-use-case matching and residual HDBSCAN
clustering. It names a stable unknown cluster and estimates the manual
counterfactual needed for later economic analysis.

The API is not called for:

- any of the 31 known scenarios;
- an HDBSCAN noise point;
- an unresolved individual task;
- an emerging cluster below `cluster_enrichment.min_cluster_members`.

The default minimum is five runs. This is deliberately higher than the
mechanical HDBSCAN minimum so that one random task is never sent for
enrichment.

## Explicit activation

No HTTP call is made by default. Activation requires both the CLI flag
`--enrich-clusters` and three environment variables:

```text
CLUSTER_ENRICHMENT_API_BASE
CLUSTER_ENRICHMENT_API_KEY
CLUSTER_ENRICHMENT_MODEL
```

The variables may be placed in the ignored local file `D:\Codex_mifi\.env`.
Copy `.env.example` to `.env` and replace the placeholders. The loader accepts
only the allowlisted Qwen/DeepSeek enrichment variables, never overwrites
variables already set by the operating system and never writes secrets to
outputs.

Legacy provider-specific aliases are also accepted:

```text
QWEN_API_BASE / QWEN_API_KEY / QWEN_CHAT_MODEL
DEEPSEEK_API_BASE / DEEPSEEK_API_KEY / DEEPSEEK_CHAT_MODEL
```

The Qwen/DeepSeek base must expose a compatible `POST /chat/completions`
endpoint.
Secrets are read from the environment and are never written to output files.

## The 31 known use cases

Known scenarios do not need an API call during normal analysis. Their draft
passports are precomputed in:

```text
configs/known_use_case_passports.yaml
```

The catalog contains exactly one strictly validated passport for every ID in
`configs/known_use_cases.yaml`. Missing, duplicate or unknown IDs stop
analysis. Each matched known run receives:

```text
economic_passport
economic_passports
local_economics
```

The primary passport is also flattened into CSV columns for base manual time,
base human follow-up and base manual-work value.

To prepare one unsent review request for each of the 31 scenarios:

```powershell
python -m prompt_radar.cli prepare-known-passport-requests `
  --output outputs/known_use_case_passport_requests.json `
  --model "<qwen-or-deepseek-model>"
```

This preparation command performs no network operation. The seed values are
expert estimates without production telemetry and must be reviewed by process
owners before being used in a business case.

## Request

The client sends:

```json
{
  "model": "<configured model>",
  "messages": [
    {"role": "system", "content": "<strict estimation prompt>"},
    {
      "role": "user",
      "content": "<bounded cluster facts and representative examples>"
    }
  ],
  "response_format": {"type": "json_object"},
  "temperature": 0.1,
  "max_tokens": 1400,
  "stream": false
}
```

At most five representative examples of at most 1500 characters each are
sent by default. These limits are configurable. Cluster examples are treated
as untrusted data; the system prompt tells the model to ignore instructions
inside them.

Before transmission, common email addresses, Russian-format phone numbers
and inline API keys/tokens/passwords are replaced with redaction markers.
This is a safety layer, not a complete anonymization guarantee: production
deployments should still apply their corporate DLP policy.

The complete prompts and attachments are never sent by this enrichment call.
The bounded request includes only locally extracted representative task
passports, cluster keywords and the required response schema. Reducing these
limits further saves tokens, but can remove context needed to distinguish
multi-step business tasks.

Every request and accepted result carries `analysis_dataset_id`,
`analysis_hash`, `analysis_configuration_hash`, `cluster_fingerprint`,
`member_run_ids_hash`, source model/revision and prompt version. Economics
reads these results automatically and rejects a reviewed cluster override
whose binding does not match the current analysis. The numeric HDBSCAN
`cluster_id` is display metadata only, not a persistent business identifier.

Validated responses are cached locally in `.cache/cluster_enrichment` by a
SHA-256 hash of the endpoint, model revision and exact redacted request body.
An identical request therefore does not consume paid API tokens twice. Cache
hits and provider token usage are written to the enrichment artifacts and
pipeline metadata; API keys are never part of the cache. Failed or
schema-invalid responses are not cached.

## Immutable demo datasets

Before an external call, the pipeline checks the optional strict registry
`configs/precomputed_cluster_enrichments.json`. A decision is accepted only
when all of the following match:

- manifest dataset id;
- input archive filename;
- input archive SHA-256;
- analysis hash;
- cluster fingerprint;
- member-run hash.

The registry may contain either a validated enrichment result or an explicit
abstention for an incoherent cluster. A matched local decision never calls the
external API. If it does not match, the external provider is initialized only
when `--enrich-clusters` was explicitly passed.

The exact prompt is stored in
`src/prompt_radar/naming/payload_builder.py` and is included in the auditable
`cluster_naming_payloads.json` preview.

## Required response

```json
{
  "cluster_name": "Анализ причин падения продаж",
  "manual_steps": [
    {"step": "Изучить исходные данные", "minutes_base": 15},
    {"step": "Рассчитать и сравнить показатели", "minutes_base": 20},
    {"step": "Определить причины отклонений", "minutes_base": 20},
    {"step": "Подготовить выводы", "minutes_base": 10}
  ],
  "manual_minutes": {"low": 35, "base": 65, "high": 120},
  "human_followup_minutes": {"low": 3, "base": 10, "high": 25},
  "active_wait_ratio": {"low": 0.0, "base": 0.25, "high": 1.0},
  "manual_time_confidence": 0.65,
  "assumptions": [
    "обрабатывается таблица среднего размера",
    "исходные данные доступны в одном файле"
  ]
}
```

Validation rules:

- unknown fields are rejected;
- all values are bounded;
- `low <= base <= high`;
- `active_wait_ratio` is between zero and one;
- the sum of `manual_steps[].minutes_base` equals
  `manual_minutes.base`;
- profession, wage, RUB values and ROI are not requested from the model.

## Local monetary context

The application uses one immutable rate:

```text
employee_cost_per_hour = 1500 RUB
employee_cost_per_minute = 1500 / 60 = 25 RUB
```

The value of an observed amount of saved time is:

```text
saved_time_value_rub = saved_minutes / 60 * 1500
```

For example:

```text
53 / 60 * 1500 = 1325 RUB
```

The response alone does not contain factual saved minutes. Actual savings
also require AI elapsed-time telemetry, active-wait adjustment, human
follow-up and verified task quality. Therefore the current output reports
manual-work value and follow-up cost context, but does not claim proven ROI.
