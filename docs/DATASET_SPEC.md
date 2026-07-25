# Prompt Radar Dataset Contract

Version: `1.0`  
Encoding: UTF-8  
Container: ZIP without nested archives

## Versioning

`manifest.json.schema_version` is mandatory and uses `MAJOR.MINOR`. This
implementation accepts major version `1`. A newer minor version may add
optional fields. An unknown major version stops validation and analysis before
records are processed.

## Archive layout

```text
dataset.zip
├── manifest.json
├── users.jsonl
├── conversations.jsonl
├── messages.jsonl
├── runs.jsonl
├── events.jsonl
├── attachments.jsonl
├── cost_config.json
└── attachments/
    └── <files referenced by attachments.jsonl>
```

`ground_truth.jsonl` is stored next to the ZIP and is never included in or read
by `analyze`.

## Common rules

- IDs are non-empty UTF-8 strings, unique within their entity file.
- Timestamps are ISO 8601. A timezone offset or `Z` is recommended.
- Unknown extra fields are preserved where practical.
- JSONL is read one object per non-empty line. A malformed line is reported
  with file and line number.
- `sequence_number` is a non-negative integer and orders messages/events
  inside a conversation/run. Ties are broken by timestamp and then ID.
- `attachment_ids` is a list; one message may reference any number of
  attachments.
- Text from prompts and documents is untrusted data. It is never executed.

## `manifest.json`

Required:

| Field | Type | Constraint |
|---|---|---|
| `schema_version` | string | `MAJOR.MINOR`, supported major is `1` |
| `dataset_id` | string | non-empty, stable for the logical dataset |
| `created_at` | datetime string | ISO 8601 |

Optional: `description`, `generator`, `synthetic` (boolean), `seed` (integer).

## `users.jsonl`

Required: `user_id`.  
Optional: `display_name`, `department`, `role`, `metadata` (object).

One user may be referenced by multiple conversations.

## `conversations.jsonl`

Required: `conversation_id`, `user_id`, `created_at`.  
Optional: `owner_user_id`, `title`, `metadata`.

`user_id` must exist in `users.jsonl`.
When `owner_user_id` is supplied it must match `user_id`; group-chat ownership
is not part of schema version `1.x`.

## `runs.jsonl`

Required: `run_id`, `conversation_id`, `status`, `started_at`.  
Optional: `user_id`, `finished_at`, `parent_run_id`, `metadata`.

Allowed `status`:

`pending`, `running`, `completed`, `failed`, `cancelled`, `partial`,
`abandoned`, `unknown`.

`conversation_id` must exist. When `user_id` is supplied it must reference an
existing user and match the owning `conversation.user_id`. `parent_run_id`,
when present, must reference another run. One conversation may contain multiple
runs.

Synthetic AI processing-time estimates may be stored in `metadata`:

| Field | Type | Constraint |
|---|---|---|
| `ai_processing_minutes` | number | non-negative minutes |
| `ai_processing_minutes_source` | string | `synthetic_complexity_estimate` |
| `ai_processing_minutes_evidence_level` | string | `E0` |

This value means synthetic AI execution time for the request. It is not human
prompt-authoring time. When any of these fields is supplied, all three are
validated and `finished_at - started_at` must equal
`ai_processing_minutes` within one second.

## `messages.jsonl`

Required:

| Field | Type | Constraint |
|---|---|---|
| `message_id` | string | unique |
| `conversation_id` | string | existing conversation |
| `role` | string | allowed role below |
| `content` | string | may contain an OpenAI-compatible JSON payload |
| `sequence_number` | integer | `>= 0` |
| `created_at` | datetime string | ISO 8601 |

Optional: `run_id` (nullable), `sender_user_id`, `attachment_ids` (list of
strings), `tool_call_id`, `metadata`.

Allowed roles: `system`, `user`, `assistant`, `tool`.

When `run_id` is present it must reference a run in the same conversation.
When `sender_user_id` is supplied on a `user` message it must match the owning
conversation user, and when the linked run also supplies `user_id` it must match
that run user as well.
When absent, the fallback segmenter considers conversation, time gap, explicit
topic-change/dependency phrases and adjacent semantic similarity. It emits a
deterministic ID beginning with `fallback:`.

## `events.jsonl`

Required: `event_id`, `conversation_id`, `event_type`, `status`,
`sequence_number`, `created_at`.

Optional: `run_id`, `message_id`, `tool_name`, `tool_call_id`, `payload`,
`metadata`.

Allowed `status`: `pending`, `running`, `success`, `failed`, `cancelled`,
`unknown`.

Common `event_type` values are `tool_call`, `tool_result`, `llm_call`,
`run_status`, and `artifact`. Other values are retained as metadata. References
to conversation, run and message must exist.

## `attachments.jsonl`

Required: `attachment_id`, `message_id`, `filename`, `path`, `media_type`,
`size_bytes`.

Optional: `sha256`, `metadata`.

`path` must be a safe relative path below `attachments/`. The referenced
message must exist and must list the same `attachment_id` in
`attachment_ids`. The file must exist after secure extraction. The declared
size is metadata; archive limits and actual file size remain authoritative.

Supported text extraction: TXT, MD, JSON, CSV, XLSX, DOCX and text-bearing
PDF. PNG/JPG/JPEG yield `unsupported_without_ocr` without failing analysis.
Macros, formulas, JavaScript and instructions from files are never executed.

## `cost_config.json`

Required: `currency` (string). The pipeline always normalizes
`employee_cost_per_hour` to `1500`. If the field is supplied with any other
value, validation fails. Role-specific labor pricing is not accepted.

Example:

```json
{"currency":"RUB","employee_cost_per_hour":1500}
```

Optional versioned allocation metadata may be retained. Manual-time estimates
are not sufficient to claim factual ROI.

The dataset-level `cost_config.json` remains compatible with ingestion.
Evidence-aware economics uses a separate strict financial configuration
supplied to the `economics` command. It fixes the rate at 1500 RUB/hour and
adds GPU, license, allocation-period and reproducibility settings.

## Economics inputs

Economics is deliberately downstream from `analyze` and accepts:

- an immutable analysis output directory;
- `cluster_economic_passports.json`, schema `1.0`;
- strict economics `cost_config.json`, schema `1.0`;
- optional `quality_evaluations.jsonl`.

Passports may target `cluster`, `known_use_case`, or `category`. A missing or
abstained passport produces `INSUFFICIENT_EVIDENCE`; values are not invented.

The passport field `manual_minutes` means expected manual/organizational effort
without the agent platform: reading, searching, moving data between systems,
Excel work, checking and preparing the final answer. The exact route is
recorded with:

| Field | Type | Notes |
|---|---|---|
| `baseline_type` | string | One primary baseline route |
| `baseline_components` | array | One or more baseline routes |
| `baseline_evidence_source` | string | `MODEL_ESTIMATE`, `EXPERT_REVIEWED`, `PROCESS_OWNER_APPROVED`, or `MEASURED` |
| `baseline_assumptions` | array | Explicit assumptions behind the baseline |

Economics adds run-level fields that are not part of the input ZIP:
`business_task_episode_id`, `episode_confidence`,
`baseline_cluster_minutes_low/base/high`, `size_factor`,
`complexity_factor`, `attachment_factor`,
`adjusted_manual_minutes_low/base/high`, `baseline_evidence_source`,
`baseline_type` and `baseline_assumptions`.

Quality rows are unique by `run_id`. Criteria weights must sum to one, scores
must be in `[0,1]`, and all minute fields are non-negative. A quality
evaluation's `completed` field is an explicit binary review label; the
technical status stored in the original run is never used as a quality label.

## Relationship invariants

```text
user_id
└── conversation_id
    ├── run_id
    │   ├── message_id
    │   ├── event_id
    │   └── attachment_id (through message_id)
    └── fallback segment(s) for messages without run_id
```

Duplicate IDs, orphan references, cross-conversation run references, missing
attachment files and undeclared attachment references are validation errors.

## Valid examples

One user with two conversations:

```json
{"user_id":"u1"}
{"conversation_id":"c1","user_id":"u1","created_at":"2026-01-01T09:00:00Z"}
{"conversation_id":"c2","user_id":"u1","created_at":"2026-01-02T09:00:00Z"}
```

One conversation with two runs and a multi-message task:

```json
{"run_id":"r1","conversation_id":"c1","status":"completed","started_at":"2026-01-01T09:00:00Z"}
{"run_id":"r2","conversation_id":"c1","status":"completed","started_at":"2026-01-01T10:00:00Z"}
{"message_id":"m1","conversation_id":"c1","run_id":"r1","role":"user","content":"Найди письма клиента","sequence_number":1,"created_at":"2026-01-01T09:00:00Z"}
{"message_id":"m2","conversation_id":"c1","run_id":"r1","role":"user","content":"И подготовь ответ","sequence_number":2,"created_at":"2026-01-01T09:01:00Z"}
```

Message with two attachments:

```json
{"message_id":"m3","conversation_id":"c1","run_id":"r2","role":"user","content":"Сравни файлы","sequence_number":3,"created_at":"2026-01-01T10:00:00Z","attachment_ids":["a1","a2"]}
```

## Invalid examples

Unknown major schema:

```json
{"schema_version":"2.0","dataset_id":"bad","created_at":"2026-01-01T00:00:00Z"}
```

Orphan run and attachment:

```json
{"message_id":"m9","conversation_id":"missing","run_id":"missing","role":"user","content":"x","sequence_number":0,"created_at":"2026-01-01T00:00:00Z","attachment_ids":["missing"]}
```

Invalid role and sequence:

```json
{"message_id":"m10","conversation_id":"c1","role":"developer","content":"x","sequence_number":-1,"created_at":"2026-01-01T00:00:00Z"}
```
