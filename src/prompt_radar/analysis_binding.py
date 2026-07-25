"""Stable hashes that bind cluster enrichment to one analyzed dataset."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable


CLUSTER_ENRICHMENT_PROMPT_VERSION = "1.0.0"


def _json_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def member_run_ids_hash(run_ids: Iterable[str]) -> str:
    """Hash the sorted unique membership of one cluster."""
    return _json_hash(sorted({str(run_id) for run_id in run_ids}))


def analysis_binding_hash(
    *,
    dataset_id: str,
    configuration_hash: str,
    model_id: str,
    model_revision: str,
    preprocessing_version: str,
    run_ids: Iterable[str],
) -> str:
    """Hash stable analysis inputs while excluding timestamps and output paths."""
    return _json_hash(
        {
            "dataset_id": dataset_id,
            "configuration_hash": configuration_hash,
            "model_id": model_id,
            "model_revision": model_revision,
            "preprocessing_version": preprocessing_version,
            "run_ids": sorted({str(run_id) for run_id in run_ids}),
        }
    )


def cluster_fingerprint(
    *,
    analysis_hash: str,
    member_ids_hash: str,
    task_passport_texts: Iterable[str],
) -> str:
    """Return a stable cluster identity independent of the numeric HDBSCAN label."""
    return _json_hash(
        {
            "analysis_hash": analysis_hash,
            "member_run_ids_hash": member_ids_hash,
            "task_passport_hashes": sorted(
                hashlib.sha256(str(text).encode("utf-8")).hexdigest()
                for text in task_passport_texts
            ),
        }
    )
