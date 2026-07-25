"""Cluster naming and economic-passport provider contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


@dataclass
class ClusterNamingRequest:
    """Bounded facts for naming one stable emerging cluster."""

    cluster_id: int
    known_categories: list[str]
    representative_examples: list[str]
    local_keywords: list[str]
    member_count: int = 0
    analysis_dataset_id: str | None = None
    analysis_hash: str | None = None
    analysis_configuration_hash: str | None = None
    cluster_fingerprint: str | None = None
    member_run_ids_hash: str | None = None
    source_model: str | None = None
    source_model_revision: str | None = None
    source_prompt_version: str | None = None


class ManualStep(BaseModel):
    """One manual step in the no-AI counterfactual workflow."""

    model_config = ConfigDict(extra="forbid")

    step: str = Field(min_length=3, max_length=240)
    minutes_base: int = Field(gt=0, le=1440)


class MinuteRange(BaseModel):
    """Ordered non-negative duration range."""

    model_config = ConfigDict(extra="forbid")

    low: int = Field(ge=0, le=10080)
    base: int = Field(ge=0, le=10080)
    high: int = Field(ge=0, le=10080)

    @model_validator(mode="after")
    def validate_order(self) -> "MinuteRange":
        if not self.low <= self.base <= self.high:
            raise ValueError("duration must satisfy low <= base <= high")
        return self


class RatioRange(BaseModel):
    """Ordered ratio range bounded to [0, 1]."""

    model_config = ConfigDict(extra="forbid")

    low: float = Field(ge=0, le=1)
    base: float = Field(ge=0, le=1)
    high: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_order(self) -> "RatioRange":
        if not self.low <= self.base <= self.high:
            raise ValueError("ratio must satisfy low <= base <= high")
        return self


class ClusterNamingResult(BaseModel):
    """Strict economic passport returned by Qwen or DeepSeek."""

    model_config = ConfigDict(extra="forbid")

    cluster_name: str = Field(min_length=5, max_length=160)
    manual_steps: list[ManualStep] = Field(min_length=1, max_length=12)
    manual_minutes: MinuteRange
    human_followup_minutes: MinuteRange
    active_wait_ratio: RatioRange
    manual_time_confidence: float = Field(ge=0, le=1)
    assumptions: list[str] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def validate_manual_steps_total(self) -> "ClusterNamingResult":
        step_total = sum(step.minutes_base for step in self.manual_steps)
        if step_total != self.manual_minutes.base:
            raise ValueError(
                "sum(manual_steps.minutes_base) must equal manual_minutes.base"
            )
        return self


class ClusterNamingProvider(Protocol):
    """Provider interface for explicit external cluster enrichment."""

    def name_cluster(
        self, request: ClusterNamingRequest
    ) -> ClusterNamingResult:
        """Name one cluster and estimate its manual-work passport."""
