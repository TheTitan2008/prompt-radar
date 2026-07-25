"""Strict local enrichment decisions for immutable demonstration datasets."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from prompt_radar.naming.base import ClusterNamingResult


class PrecomputedClusterDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cluster_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    member_run_ids_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    action: Literal["enrich", "abstain"]
    cluster_name: str = Field(min_length=5, max_length=160)
    abstention_reason: str | None = None
    source_model: str = Field(min_length=1)
    source_model_revision: str = Field(min_length=1)
    source_prompt_version: str = Field(min_length=1)
    result: ClusterNamingResult | None = None

    @model_validator(mode="after")
    def validate_action(self) -> "PrecomputedClusterDecision":
        if self.action == "enrich" and self.result is None:
            raise ValueError("enrich decision requires result")
        if self.action == "abstain" and not self.abstention_reason:
            raise ValueError("abstain decision requires abstention_reason")
        return self


class PrecomputedDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(min_length=1)
    dataset_filename: str = Field(min_length=1)
    archive_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    analysis_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    clusters: list[PrecomputedClusterDecision] = Field(default_factory=list)

    def cluster(
        self, fingerprint: str, members_hash: str
    ) -> PrecomputedClusterDecision | None:
        for decision in self.clusters:
            if (
                decision.cluster_fingerprint == fingerprint
                and decision.member_run_ids_hash == members_hash
            ):
                return decision
        return None


class PrecomputedEnrichmentRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"]
    datasets: list[PrecomputedDataset] = Field(default_factory=list)

    def dataset(
        self,
        *,
        dataset_id: str,
        dataset_filename: str,
        archive_sha256: str,
        analysis_hash: str,
    ) -> PrecomputedDataset | None:
        for dataset in self.datasets:
            if (
                dataset.dataset_id == dataset_id
                and dataset.dataset_filename == dataset_filename
                and dataset.archive_sha256 == archive_sha256
                and dataset.analysis_hash == analysis_hash
            ):
                return dataset
        return None


def load_precomputed_registry(
    path: Path | None,
) -> PrecomputedEnrichmentRegistry:
    if path is None or not path.is_file():
        return PrecomputedEnrichmentRegistry(schema_version="1.0")
    return PrecomputedEnrichmentRegistry.model_validate(
        json.loads(path.read_text(encoding="utf-8"))
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
