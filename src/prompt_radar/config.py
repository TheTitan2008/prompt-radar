"""Typed configuration loader."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


class ResourceConfig(BaseModel):
    """Archive and embedding resource limits."""

    max_files: int = 5000
    max_single_file_mb: int = 100
    max_unpacked_mb: int = 2048
    max_compression_ratio: float = 100.0
    max_directory_depth: int = 10
    embedding_batch_size_cpu: int = 8
    embedding_batch_size_cuda: int = 32


class TextProcessingConfig(BaseModel):
    """Thresholds for direct, RAG and long-payload processing."""

    direct_embedding_max_tokens: int = 8000
    goal_max_tokens: int = Field(default=512, ge=32)
    chunk_size_tokens: int = 3000
    chunk_overlap_tokens: int = 256
    rag_top_k: int = 5
    instruction_candidate_limit: int = 8
    representative_chunk_limit: int = 6


class ModelConfig(BaseModel):
    """Pinned local embedding model settings."""

    id: str
    revision: str
    cache_dir: str = ".cache/huggingface"
    query_instruction: str = ""


class FallbackConfig(BaseModel):
    """Fallback run segmentation thresholds."""

    max_gap_minutes: int = 45
    adjacent_similarity_threshold: float = 0.42
    dependent_phrases: list[str] = Field(default_factory=list)
    topic_change_phrases: list[str] = Field(default_factory=list)


class ClassificationConfig(BaseModel):
    """Known-use-case and category matching thresholds."""

    known_use_case_threshold: float = 0.56
    additional_use_case_threshold: float = 0.50
    primary_category_threshold: float = 0.43
    additional_category_threshold: float = 0.38
    max_use_cases: int = 3
    max_categories: int = 3


class ClusteringConfig(BaseModel):
    """Residual-pool clustering parameters."""

    use_umap: bool = True
    umap_components: int = 10
    umap_neighbors: int = 15
    umap_min_dist: float = 0.0
    min_cluster_size: int = 3
    min_samples: int = 2
    cluster_selection_method: str = "eom"
    random_seed: int = 42
    representative_count: int = 5
    boundary_count: int = 2


class AttachmentConfig(BaseModel):
    """Bounded attachment extraction settings."""

    max_json_depth: int = 12
    max_json_value_chars: int = 4000
    max_cells_per_sheet: int = 20000


class ClusterEnrichmentConfig(BaseModel):
    """Explicit, bounded external enrichment for stable emerging clusters."""

    min_cluster_members: int = Field(default=5, ge=2)
    max_representative_examples: int = Field(default=5, ge=1, le=10)
    max_example_chars: int = Field(default=1500, ge=100, le=5000)
    timeout_seconds: float = Field(default=60.0, gt=0, le=180)
    max_tokens: int = Field(default=1400, ge=300, le=4000)
    max_response_bytes: int = Field(default=1_000_000, ge=1024, le=5_000_000)
    temperature: float = Field(default=0.1, ge=0, le=1)
    redact_external_text: bool = True
    cache_dir: str = ".cache/cluster_enrichment"


class EconomicsConfig(BaseModel):
    """Fixed business assumptions; the model is never allowed to choose them."""

    employee_cost_per_hour: Literal[1500] = 1500


class PipelineConfig(BaseModel):
    """Complete pipeline configuration."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    random_seed: int = 42
    preprocessing_version: str = "1.0.0"
    model: ModelConfig
    resources: ResourceConfig = Field(default_factory=ResourceConfig)
    text_processing: TextProcessingConfig = Field(default_factory=TextProcessingConfig)
    fallback_segmentation: FallbackConfig = Field(default_factory=FallbackConfig)
    classification: ClassificationConfig = Field(
        default_factory=ClassificationConfig
    )
    clustering: ClusteringConfig = Field(default_factory=ClusteringConfig)
    attachments: AttachmentConfig = Field(default_factory=AttachmentConfig)
    cluster_enrichment: ClusterEnrichmentConfig = Field(
        default_factory=ClusterEnrichmentConfig
    )
    economics: EconomicsConfig = Field(default_factory=EconomicsConfig)

    def stable_hash(self) -> str:
        """Return a deterministic SHA-256 hash of effective configuration."""
        encoded = json.dumps(
            self.model_dump(mode="json"), sort_keys=True, ensure_ascii=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a UTF-8 YAML mapping."""
    with path.open("r", encoding="utf-8") as stream:
        value = yaml.safe_load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return value


def load_config(path: Path) -> PipelineConfig:
    """Load and validate the pipeline configuration."""
    return PipelineConfig.model_validate(load_yaml(path))
