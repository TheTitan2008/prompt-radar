"""Synthetic/offline evaluation metrics."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from prompt_radar.embeddings.fake import HashingEmbeddingService
from prompt_radar.io_utils import write_json
from prompt_radar.retrieval.cosine import cosine_matrix

_SPACE = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected object")
            rows.append(value)
    return rows


def normalize_goal(text: str) -> str:
    """Normalize case, punctuation and whitespace for exact matching."""
    return _SPACE.sub(" ", _PUNCT.sub(" ", text.casefold())).strip()


def _prf(
    truth_sets: list[set[str]], prediction_sets: list[set[str]]
) -> dict[str, float]:
    labels = sorted(set().union(*truth_sets, *prediction_sets))
    true_positive = sum(
        len(truth & predicted)
        for truth, predicted in zip(truth_sets, prediction_sets, strict=True)
    )
    false_positive = sum(
        len(predicted - truth)
        for truth, predicted in zip(truth_sets, prediction_sets, strict=True)
    )
    false_negative = sum(
        len(truth - predicted)
        for truth, predicted in zip(truth_sets, prediction_sets, strict=True)
    )

    def safe(numerator: float, denominator: float) -> float:
        return numerator / denominator if denominator else 0.0

    micro_precision = safe(true_positive, true_positive + false_positive)
    micro_recall = safe(true_positive, true_positive + false_negative)
    micro_f1 = safe(
        2 * micro_precision * micro_recall, micro_precision + micro_recall
    )
    per_label: list[tuple[float, float, float]] = []
    for label in labels:
        tp = sum(label in truth and label in predicted for truth, predicted in zip(truth_sets, prediction_sets, strict=True))
        fp = sum(label not in truth and label in predicted for truth, predicted in zip(truth_sets, prediction_sets, strict=True))
        fn = sum(label in truth and label not in predicted for truth, predicted in zip(truth_sets, prediction_sets, strict=True))
        precision = safe(tp, tp + fp)
        recall = safe(tp, tp + fn)
        f1 = safe(2 * precision * recall, precision + recall)
        per_label.append((precision, recall, f1))
    return {
        "micro_precision": micro_precision,
        "micro_recall": micro_recall,
        "micro_f1": micro_f1,
        "macro_precision": float(np.mean([item[0] for item in per_label]))
        if per_label
        else 0.0,
        "macro_recall": float(np.mean([item[1] for item in per_label]))
        if per_label
        else 0.0,
        "macro_f1": float(np.mean([item[2] for item in per_label]))
        if per_label
        else 0.0,
    }


def evaluate_predictions(
    predictions_path: Path,
    ground_truth_path: Path,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Evaluate predictions without exposing ground truth to `analyze`."""
    predictions = _read_jsonl(predictions_path)
    truth = _read_jsonl(ground_truth_path)
    prediction_by_run = {str(item["run_id"]): item for item in predictions}
    truth_by_run = {str(item["run_id"]): item for item in truth}
    common = sorted(set(prediction_by_run) & set(truth_by_run))
    missing_predictions = sorted(set(truth_by_run) - set(prediction_by_run))

    exact: list[bool] = []
    normalized: list[bool] = []
    semantic_pairs: list[tuple[str, str]] = []
    truth_labels: list[set[str]] = []
    predicted_labels: list[set[str]] = []
    truth_categories: list[set[str]] = []
    predicted_categories: list[set[str]] = []
    reconstruction: list[bool] = []
    retrieval_hits: list[bool] = []
    discovery_truth: list[str] = []
    discovery_predictions: list[str] = []
    for run_id in common:
        expected = truth_by_run[run_id]
        predicted = prediction_by_run[run_id]
        expected_goal = str(expected.get("expected_goal", ""))
        actual_goal = str(predicted.get("current_goal", ""))
        exact.append(expected_goal == actual_goal)
        normalized.append(normalize_goal(expected_goal) == normalize_goal(actual_goal))
        semantic_pairs.append((expected_goal, actual_goal))
        truth_labels.append(set(expected.get("expected_use_case_ids", [])))
        predicted_labels.append(
            {
                str(item.get("id"))
                for item in predicted.get("known_use_case_matches", [])
                if bool(item.get("accepted", False))
            }
        )
        truth_categories.append(set(expected.get("expected_category_ids", [])))
        predicted_categories.append(
            {
                str(item.get("id"))
                for item in predicted.get("categories", [])
                if bool(item.get("accepted", False))
            }
        )
        expected_messages = expected.get("expected_message_ids")
        if expected_messages is not None:
            reconstruction.append(
                set(expected_messages) == set(predicted.get("message_ids", []))
            )
        expected_chunks = expected.get("expected_retrieved_chunk_ids")
        if expected_chunks is not None:
            retrieval_hits.append(
                set(expected_chunks).issubset(
                    set(predicted.get("retrieved_chunk_ids", []))
                )
            )
        if expected.get("expected_discovery_status"):
            discovery_truth.append(str(expected["expected_discovery_status"]))
            discovery_predictions.append(str(predicted.get("discovery_status")))

    semantic_similarity = 0.0
    if semantic_pairs:
        fake = HashingEmbeddingService()
        left = fake.encode([pair[0] for pair in semantic_pairs], mode="query")
        right = fake.encode([pair[1] for pair in semantic_pairs], mode="query")
        semantic_similarity = float(np.mean(np.diag(cosine_matrix(left, right))))
    discovery_counts = Counter(discovery_predictions)
    total_discovery = len(discovery_predictions)
    report: dict[str, Any] = {
        "scope": {
            "synthetic": all(bool(item.get("synthetic")) for item in truth),
            "matched_runs": len(common),
            "truth_runs": len(truth),
            "prediction_runs": len(predictions),
            "missing_prediction_run_ids": missing_predictions,
        },
        "goal_extraction": {
            "exact_match": float(np.mean(exact)) if exact else None,
            "normalized_match": float(np.mean(normalized)) if normalized else None,
            "semantic_similarity_hashing_baseline": semantic_similarity
            if semantic_pairs
            else None,
        },
        "known_use_case_multilabel": _prf(truth_labels, predicted_labels)
        if common
        else None,
        "known_category_multilabel": _prf(
            truth_categories, predicted_categories
        )
        if common
        else None,
        "retrieval": {
            "recall_at_k": float(np.mean(retrieval_hits))
            if retrieval_hits
            else None,
            "evaluated_runs": len(retrieval_hits),
        },
        "discovery": {
            "status_accuracy": float(
                np.mean(
                    [
                        expected == actual
                        for expected, actual in zip(
                            discovery_truth, discovery_predictions, strict=True
                        )
                    ]
                )
            )
            if discovery_truth
            else None,
            "coverage": {
                status: discovery_counts.get(status, 0) / total_discovery
                if total_discovery
                else 0.0
                for status in ("known", "emerging", "unresolved")
            },
            "noise_rate": discovery_counts.get("unresolved", 0) / total_discovery
            if total_discovery
            else None,
        },
        "run_reconstruction_accuracy": float(np.mean(reconstruction))
        if reconstruction
        else None,
        "clustering": {"ari": None, "nmi": None},
        "ingestion": _ingestion_metrics(predictions_path),
        "disclaimer": (
            "Metrics on this synthetic dataset validate pipeline mechanics and "
            "must not be presented as quality on real KROK data."
        ),
    }
    cluster_truth_pairs = [
        (
            truth_by_run[run_id].get("expected_cluster_id"),
            prediction_by_run[run_id].get("cluster_id"),
        )
        for run_id in common
        if truth_by_run[run_id].get("expected_cluster_id") is not None
    ]
    if cluster_truth_pairs:
        try:
            from sklearn.metrics import (
                adjusted_rand_score,
                normalized_mutual_info_score,
            )

            expected_clusters = [pair[0] for pair in cluster_truth_pairs]
            actual_clusters = [pair[1] for pair in cluster_truth_pairs]
            report["clustering"] = {
                "ari": float(adjusted_rand_score(expected_clusters, actual_clusters)),
                "nmi": float(
                    normalized_mutual_info_score(
                        expected_clusters, actual_clusters
                    )
                ),
            }
        except ImportError:
            report["clustering"]["note"] = "scikit-learn is not installed"
    if output_path:
        write_json(output_path, report)
    return report


def _ingestion_metrics(predictions_path: Path) -> dict[str, Any]:
    validation_path = predictions_path.parent / "validation_report.json"
    if not validation_path.is_file():
        return {
            "error_rate": None,
            "skipped_record_rate": None,
            "note": "Sibling validation_report.json was not found.",
        }
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    counts = validation.get("record_counts", {})
    processed = sum(int(value) for value in counts.values())
    skipped = int(validation.get("skipped_records", 0))
    errors = sum(
        1
        for issue in validation.get("issues", [])
        if issue.get("severity") == "error"
    )
    denominator = processed + skipped
    return {
        "error_rate": errors / denominator if denominator else 0.0,
        "skipped_record_rate": skipped / denominator if denominator else 0.0,
        "validated_records": processed,
        "error_count": errors,
        "skipped_records": skipped,
    }
