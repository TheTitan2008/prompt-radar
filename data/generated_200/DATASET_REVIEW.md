# Review of `generated_200/dataset.zip`

Reviewed archive SHA-256:

```text
de9fdb1aeadf648e502eaae5ddebc998f0c588ecbf172cf651ec7fc8a1c0b703
```

## Structural result

The archive passes the project validator with no ingestion errors:

- 200 runs;
- 41 users;
- 97 conversations;
- 234 messages;
- 120 events;
- 15 attachments;
- 150 known-use-case runs;
- 5 MEPhI runs;
- 20 emerging runs in four intended groups;
- 25 noise runs.

All 31 known use cases are represented. There are exactly 15 runs with
attachments and two prompts marked as exactly 100000 tokens by the synthetic
`WhitespaceTokenizer`.

## Real Qwen/HDBSCAN result

Analysis:

```text
outputs/generated_200_real/prompt_radar_generated_200_20260725T021037Z
```

Key evaluation values:

- known top-1 correct: 81/150;
- known-use-case micro F1: 0.3014;
- category micro F1: 0.3599;
- discovery status accuracy: 0.82;
- clustering ARI: 0.1017;
- clustering NMI: 0.0880.

The residual pool produced one 20-member cluster that mixes:

- 3 MEPhI prompts;
- 11 prompts from the four intended emerging groups;
- 6 noise prompts.

The cluster is not coherent enough for one manual-time baseline. Its
precomputed decision therefore abstains instead of inventing ROI.

## Methodological limitations

1. Short known prompts expose catalog identifiers such as
   `daily_email_digest`.
2. Longer known prompts are generated directly from catalog names,
   descriptions and expected outcomes.
3. All attachments are assigned only to known-use-case runs.
4. All failed/partial/cancelled runs occur in the final noise block.
5. Styles and length buckets follow deterministic index blocks and can become
   proxy labels.
6. Long context consists mainly of unique `ctxNNNNN` filler. It tests resource
   handling, not retrieval of meaningful facts.
7. A prompt counted as 100000 whitespace tokens is about 600000 Qwen tokens,
   so the declared length is not the real model length.
8. The four intended emerging groups use one common sentence template, making
   their action vocabulary more prominent than their business meaning.
9. Ground truth contains no expected attachment chunk ids, so retrieval
   Recall@K is not evaluated.

## Recommended changes before freezing the demo dataset

1. Generate natural paraphrases without catalog ids or verbatim catalog
   descriptions.
2. Randomly distribute statuses, lengths, styles, users and attachments across
   all groups.
3. Replace `ctxNNNNN` filler with coherent documents containing planted facts
   and expected evidence spans.
4. Count long prompts using the pinned Qwen tokenizer; keep a separate stress
   archive if 100k+ processing must be demonstrated.
5. Give each emerging topic at least 8-12 semantically varied prompts.
6. Make noise mostly short and keep it outside coherent HDBSCAN groups.
7. Add expected retrieval chunks for attachment tasks.
8. Calibrate known-use-case thresholds on a train/calibration split and report
   metrics only on a separate test split.

## Precomputed enrichment rule

The immutable archive has a strict local decision in:

```text
configs/precomputed_cluster_enrichments.json
```

It is selected only when the filename, dataset id, archive hash, analysis hash,
cluster fingerprint and member-run hash all match. It never relies on a
numeric HDBSCAN cluster id.
