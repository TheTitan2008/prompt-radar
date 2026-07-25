# Prompt Radar

Prompt Radar is an offline-first Python 3.11 pipeline for turning corporate
AI-agent logs into run-level analytics: current user goals, broad categories,
known use cases, residual clusters and an auditable Markdown report.

The first version deliberately focuses on prompt/category/use-case analysis.
It does not claim proven ROI, execute prompt-supplied tools or claim that
synthetic metrics describe real KROK traffic. External cluster enrichment is
available only through an explicit opt-in flag and a separately configured
endpoint.

The separate `economics` layer calculates evidence-aware potential and proven
economics from an existing analysis directory. It never calls an API.

## Why the unit of analysis is `run_id`

One business task may contain several user clarifications, assistant messages,
tool calls and attachments. Counting each message as a separate task would
double-count work and lose the active goal. Prompt Radar therefore builds one
analysis record per explicit `run_id`. Messages without `run_id` go through a
separate fallback segmenter and receive an ID beginning with `fallback:`.

One user may own several conversations; one conversation may contain several
runs; one run may contain several ordered messages; one message may reference
several attachments. The full contract and valid/invalid examples are in
[docs/DATASET_SPEC.md](docs/DATASET_SPEC.md).

Datasets may optionally include normalized ownership fields
(`conversation.owner_user_id`, `run.user_id`, `message.sender_user_id`) and a
run metadata estimate named `ai_processing_minutes`. That estimate is synthetic
AI execution time with an explicit source/evidence level, not measured human
prompt-authoring time.

## Pipeline

```text
dataset.zip
    ↓
Validation and secure extraction
    ↓
Users / conversations / runs / messages / attachments
    ↓
Run-level task construction
    ↓
Message-aware goal extraction
    ↓
Prompt routing
    ├── short prompt
    ├── short + attachments → RAG Top-K
    └── long prompt → chunking + extractive passport
    ↓
Qwen3-Embedding
    ↓
Known use-case matching
    ├── Known
    └── Residual pool
         ↓
       HDBSCAN
         ├── Emerging
         └── Unresolved
    ↓
Statistics, clusters and representatives
    ↓
Local provisional labels
    ↓
Payloads for future Qwen API
```

### Message-aware goal extraction

Before token chunking, the parser respects `system`, `user`, `assistant` and
`tool` roles. It inspects the last active user message and recognizes
XML-like `<user_query>`, `<context>` and `<source>` sections inside an
OpenAI-compatible payload. A command in `<user_query>` wins over a large
untrusted context block. The output retains message IDs, spans, method,
confidence and ambiguity.

### Three processing modes

1. `short_direct`: a short prompt without attachments is embedded directly
   after extractive goal selection.
2. `short_with_attachments`: attachment text is chunked and ranked across all
   files with cosine RAG Top-K; large irrelevant files are not averaged into
   the user goal.
3. `long_extractive`: a long payload is chunked with overlap; instruction-like
   evidence is selected into a bounded task passport. Nothing asks an
   embedding model to generate a summary.

Thresholds live in `configs/pipeline.yaml`.

### Attachments and security

TXT, Markdown, JSON, CSV, XLSX, DOCX and text-bearing PDF are supported.
Spreadsheets are opened read-only and formulas are not executed. PDF is
text-only. PNG/JPG/JPEG yield `unsupported_without_ocr` and a warning.

The ZIP loader rejects Zip Slip, absolute/drive paths, symlinks, reparse-point
flags, nested archives, duplicate paths, excess depth/count/size, suspicious
compression ratios and extraction outside the work root. Source archives are
never changed. Runtime inputs, extracted data, model cache and outputs are
ignored by Git.

### Embeddings are not a chat model

`Qwen/Qwen3-Embedding-0.6B` maps text to normalized numeric vectors. It does
not write summaries or cluster names. Cosine similarity measures vector
closeness; it is not a probability or accuracy score.

The model revision is pinned in `configs/pipeline.yaml`. Analysis defaults to
offline mode and never downloads missing weights. Only `download-model`
performs a Hugging Face download. Unit tests use a deterministic fake embedding
service.

### Categories, known use cases and discovery

`configs/categories.yaml` contains a small draft set of broad directions.
`configs/known_use_cases.yaml` contains 31 source scenarios mapped to one or
more broad categories. This is intentionally multi-label: the 31 workbook rows
are use-case examples, not 31 mutually exclusive categories.

The decision order is:

1. compare a task passport to known use cases;
2. mark a confident match `known`;
3. send weak matches to the residual pool;
4. run HDBSCAN only on residual run-level vectors;
5. mark stable clusters `emerging` and noise `unresolved`.

HDBSCAN groups nearby vectors; it does not understand text and does not name
clusters. A local frequency heuristic creates an explicitly non-final
provisional label. Representative examples are selected near the medoid, not
by input order.

## Dataset layout

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
```

`manifest.json` requires `schema_version`. Unknown major versions stop the
pipeline. `ground_truth.jsonl` is separate from the ZIP and can only be passed
to `evaluate`; `analyze` has no ground-truth option.

## Installation (Windows PowerShell)

Python 3.11 is the supported baseline.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[attachments,ml,dev]"
```

Dependency groups:

- base install / `core`: CLI, configuration, models and NumPy;
- `attachments`: XLSX, PDF, DOCX, pandas/Parquet and demo artifacts;
- `ml`: Qwen/Sentence Transformers, torch, HDBSCAN, UMAP and scikit-learn;
- `dev`: pytest and coverage.

`pyproject.toml` is the only dependency source; no independently maintained
`requirements.txt` is used.

## Commands

All commands below run from the repository root.

### Evidence-aware economics

```powershell
python -m prompt_radar.cli economics `
  --analysis outputs/<analysis_run> `
  --quality data/economics/quality_evaluations.jsonl `
  --cost-config data/economics/cost_config.json `
  --output outputs/<analysis_run>/economics
```

Known-use-case passports and successful cluster API enrichments are read
directly from the analysis artifacts. `--passports` is optional and is only
for reviewed overrides. A cluster override must contain the matching dataset,
analysis, configuration, membership and cluster-fingerprint hashes; stale
numeric HDBSCAN labels are rejected.

Economics does not take the first semantic match blindly. Multi-goal runs and
known-use-case matches whose confidence margin is below
`minimum_economic_classification_margin` are left without a baseline and
reported as insufficient evidence.

`--quality` is optional. Without it the command calculates potential
LOW/BASE/HIGH, platform break-even and required quality, but never claims
proven positive ROI.

Economics outputs include run JSONL/CSV/Parquet ledgers, cluster JSON/CSV,
platform totals, cost reconciliation, value leakage, warnings, reproducibility
metadata and `economics_report.md`. It also creates:

- `statistics_report.html` — a self-contained management dashboard with
  request types, statuses, processing modes and expandable per-person
  statistics down to every task;
- `statistics_summary.json` — the same reconciled aggregates in a
  machine-readable form.

Per-person statistics separate potential and actual savings, show passport
coverage, AI wall time, gross labor value, allocated platform cost and net
effect. Assumed prompt effort is explicitly marked and never presented as
measured actual savings. See
`docs/ECONOMICS_METHODOLOGY.md`.

### Download the pinned model explicitly

```powershell
python -m prompt_radar.cli download-model
```

Weights are stored under `.cache/huggingface/` and are not committed.

### Generate deterministic demo data

```powershell
python -m prompt_radar.cli generate-demo `
  --output data/sample/dataset.zip `
  --ground-truth data/sample/ground_truth.jsonl `
  --seed 42
```

The demo includes two users, one user with two chats, a chat with five
sequential user prompts, multiple runs in one chat, multiple messages in one
run, XLSX/PDF/two-attachment/image cases, a long OpenAI-compatible payload,
`<user_query>`, missing `run_id`, known/emerging/noise examples and tool
events. Ground truth is written outside the ZIP.

### Validate

```powershell
python -m prompt_radar.cli validate `
  --input data/sample/dataset.zip `
  --output data/sample/validation_report.json
```

### Analyze offline with Qwen

```powershell
python -m prompt_radar.cli analyze `
  --input data/sample/dataset.zip `
  --output outputs `
  --config configs/pipeline.yaml `
  --categories configs/categories.yaml `
  --use-cases configs/known_use_cases.yaml `
  --offline
```

For a no-model mechanical smoke run only:

```powershell
python -m prompt_radar.cli analyze `
  --input data/sample/dataset.zip `
  --embedding-backend fake `
  --offline
```

Fake embeddings validate mechanics, not semantic model quality.

### Evaluate separately

```powershell
$run = Get-ChildItem outputs -Directory |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1

python -m prompt_radar.cli evaluate `
  --predictions "$($run.FullName)\runs_analysis.jsonl" `
  --ground-truth data/sample/ground_truth.jsonl `
  --output "$($run.FullName)\evaluation.json"
```

Evaluation calculates available exact/normalized/semantic goal metrics,
multi-label micro/macro precision/recall/F1, Recall@K, discovery coverage,
noise, run reconstruction and ARI/NMI when corresponding labels exist.
Synthetic metrics are not real-data quality claims.

### Tests

```powershell
python -m pytest -m "not integration"
```

After an explicit model download:

```powershell
$env:RUN_QWEN_INTEGRATION = "1"
python -m pytest tests/test_integration_qwen.py -m integration
Remove-Item Env:RUN_QWEN_INTEGRATION
```

## Outputs

Each analysis creates `outputs/<dataset_id>_<UTC timestamp>/`:

- `validation_report.json`
- `runs_analysis.jsonl`, `.csv`, and (when available) `.parquet`
- `classification_results.jsonl`
- `known_use_case_passports.json`
- `clusters.json`
- `cluster_members.jsonl`
- `cluster_naming_payloads.json`
- `cluster_enrichments.json`
- `retrieved_chunks.jsonl`
- `embeddings.npz`
- `pipeline_metadata.json`
- `warnings.jsonl`
- `report.md`

`pipeline_metadata.json` records schema/configuration/model/tokenizer/
preprocessing revisions, dependency versions, device, effective parameters,
counts, ground-truth isolation and the exact number of external enrichment
attempts.

External Qwen/DeepSeek enrichment is disabled by default. In this mode
`cluster_naming_payloads.json` contains bounded request previews only and no
HTTP request is made. To opt in, configure an OpenAI-compatible endpoint:

```powershell
$env:CLUSTER_ENRICHMENT_API_BASE = "https://provider.example/v1"
$env:CLUSTER_ENRICHMENT_API_KEY = "<secret>"
$env:CLUSTER_ENRICHMENT_MODEL = "<qwen-or-deepseek-chat-model>"

python -m prompt_radar.cli analyze `
  --input data/sample/dataset.zip `
  --output outputs `
  --offline `
  --enrich-clusters
```

Only residual `emerging` clusters with at least five members are eligible by
default. Noise, single tasks, known scenarios and smaller clusters are never
sent. The threshold is configured by
`cluster_enrichment.min_cluster_members`. Responses are validated against a
strict JSON schema and written to `cluster_enrichments.json`. They are bound
to the current analysis with analysis, configuration, membership and cluster
fingerprint hashes plus model and prompt versions. The economics command reads
successful passports automatically. API failures are recorded as warnings and
do not discard the local analysis.

Representative text is bounded and direct email/phone/secret patterns are
redacted before transmission. Validated identical requests are served from
the local content-addressed cache in `.cache/cluster_enrichment`, so repeated
demo runs do not pay for the same enrichment again. `pipeline_metadata.json`
records real HTTP call count, cache-hit count and billed-call token usage.

For immutable demonstration datasets, `analyze` first checks
`configs/precomputed_cluster_enrichments.json`. A local decision is used only
when the dataset id, filename, archive SHA-256, analysis hash, cluster
fingerprint and member-run hash all match. A filename match alone is never
trusted. If no local decision matches, the normal API path is used only when
`--enrich-clusters` was explicitly supplied. A reviewed local decision may
also abstain from economics when a cluster is not coherent.

The registry can be disabled or replaced with:

```powershell
python -m prompt_radar.cli analyze `
  --input data/sample/dataset.zip `
  --precomputed-enrichments configs/no-precomputed-registry.json `
  --enrich-clusters
```

The external model estimates only a cluster name, manual steps and time
ranges. Labor values are calculated locally at the fixed rate
`employee_cost_per_hour: 1500`; the model never chooses a role or wage.
See `docs/CLUSTER_ENRICHMENT_API.md`.

## What to show in a 3-minute demo

Use the final fixed dataset:

- `data/generated_800/dataset.zip`

Use this canonical run from Saturday, July 25, 2026:

- analysis output: `outputs/prompt_radar_generated_800_20260725T112030Z`
- economics output: `outputs/prompt_radar_generated_800_20260725T112030Z/economics_final`

The shortest practical demo flow is:

1. Show that the fixed dataset validates:

```powershell
python -m prompt_radar.cli validate --input data/generated_800/dataset.zip
```

2. Show that the first task is already solved on the fixed dataset:

- `outputs/prompt_radar_generated_800_20260725T112030Z/report.md`
- `outputs/prompt_radar_generated_800_20260725T112030Z/pipeline_metadata.json`
- `outputs/prompt_radar_generated_800_20260725T112030Z/cluster_enrichments.json`

What to say:

- the pipeline reconstructed 800 runs from the archive;
- Qwen embeddings + HDBSCAN split the requests into known, emerging and
  unresolved groups;
- the fixed dataset matched the local precomputed registry exactly;
- external generative API calls for this demo run: `0`.

3. Show that the second task is also solved:

- `outputs/prompt_radar_generated_800_20260725T112030Z/economics_final/economics_report.md`
- `outputs/prompt_radar_generated_800_20260725T112030Z/economics_final/statistics_report.html`
- `outputs/prompt_radar_generated_800_20260725T112030Z/economics_final/platform_economics.json`

What to say:

- the project calculates potential time savings, cost, ROI and break-even;
- the model now also exposes token economics and FTE-based value;
- the statistics report shows totals, request types and per-person usage;
- these are sensitivity results unless prompt effort and quality are measured.

4. If asked about “what happens on another dataset”:

- the fixed demo dataset uses a strict local registry;
- a different dataset will not reuse those answers unless dataset id,
  archive hash, analysis hash, cluster fingerprint and member hash also match;
- otherwise the normal enrichment path is used only when
  `--enrich-clusters` is explicitly requested.

### Precomputed passports for the 31 known use cases

All 31 catalog use cases have a validated local draft passport in
`configs/known_use_case_passports.yaml`. A matched known run receives its
passport and local labor-value context without any network request. The
passports are explicitly marked as expert seeds without production telemetry;
they are inputs for validation, not claims of factual savings.

To prepare 31 auditable, unsent Qwen/DeepSeek request bodies for a later review:

```powershell
python -m prompt_radar.cli prepare-known-passport-requests `
  --use-cases configs/known_use_cases.yaml `
  --output outputs/known_use_case_passport_requests.json `
  --model "<qwen-or-deepseek-model>"
```

This command never reads an API key and never sends a request.

### Where to put a Qwen/DeepSeek key

Create the ignored local file `.env` from the example:

```powershell
Copy-Item .env.example .env
notepad .env
```

Fill only these values:

```text
CLUSTER_ENRICHMENT_API_BASE=https://provider.example/v1
CLUSTER_ENRICHMENT_API_KEY=<secret>
CLUSTER_ENRICHMENT_MODEL=<qwen-or-deepseek-model>
```

`.env` is ignored by Git. It is loaded only when `--enrich-clusters` is
explicitly passed. Existing process environment variables take precedence.

## First-version limitations

- no OCR for images or scanned PDFs;
- no Streamlit/dashboard polish;
- no external Jira/CRM/Email integrations;
- external cluster enrichment is optional and requires a deliberately
  configured OpenAI-compatible endpoint;
- manual-time estimates provide potential value inputs, not proven ROI;
- no Outcome Contracts or universal process mining;
- fallback run boundaries and thresholds need calibration on independent
  labeled data;
- category/use-case mapping is a draft requiring domain review;
- a residual cluster is a candidate for validation, not automatic proof of a
  new business scenario;
- JSONL is parsed line-by-line, but the first-version relationship validator
  keeps validated entity indexes in memory. Very large corpora should replace
  these indexes with a disk-backed store such as SQLite.

Source-derived assumptions and precedence are documented in `docs/context/`.
