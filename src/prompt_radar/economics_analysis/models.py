"""Strict input models for economic passports, quality and cost configuration."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EvidenceLevel = Literal["E0", "E1", "E2", "E3"]
TargetType = Literal["cluster", "known_use_case", "category"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NumericRange(StrictModel):
    low: float = Field(ge=0)
    base: float = Field(ge=0)
    high: float = Field(ge=0)

    @model_validator(mode="after")
    def ordered(self) -> "NumericRange":
        if not self.low <= self.base <= self.high:
            raise ValueError("range must satisfy low <= base <= high")
        return self


class RatioRange(StrictModel):
    low: float = Field(ge=0, le=1)
    base: float = Field(ge=0, le=1)
    high: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def ordered(self) -> "RatioRange":
        if not self.low <= self.base <= self.high:
            raise ValueError("ratio must satisfy low <= base <= high")
        return self


class ManualStep(StrictModel):
    step: str = Field(min_length=3)
    minutes_low: float = Field(ge=0)
    minutes_base: float = Field(ge=0)
    minutes_high: float = Field(ge=0)

    @model_validator(mode="after")
    def ordered(self) -> "ManualStep":
        if not self.minutes_low <= self.minutes_base <= self.minutes_high:
            raise ValueError("step minutes must satisfy low <= base <= high")
        return self


class EconomicPassport(StrictModel):
    target_type: TargetType
    target_id: str = Field(min_length=1)
    is_coherent_cluster: bool = True
    abstain: bool = False
    abstention_reason: str | None = None
    cluster_name: str = Field(min_length=3)
    business_goal: str = Field(min_length=3)
    manual_steps: list[ManualStep] = Field(min_length=1)
    manual_minutes: NumericRange
    human_followup_minutes: NumericRange
    active_wait_ratio: RatioRange
    manual_time_confidence: float = Field(ge=0, le=1)
    assumptions: list[str] = Field(default_factory=list)
    uncertainty_drivers: list[str] = Field(default_factory=list)
    evidence_level: EvidenceLevel = "E0"
    requires_human_validation: bool = True
    owner: str | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    analysis_dataset_id: str | None = None
    analysis_hash: str | None = None
    analysis_configuration_hash: str | None = None
    cluster_fingerprint: str | None = None
    member_run_ids_hash: str | None = None
    source_model: str | None = None
    source_model_revision: str | None = None
    source_prompt_version: str | None = None

    @model_validator(mode="after")
    def validate_totals_and_abstention(self) -> "EconomicPassport":
        totals = (
            sum(step.minutes_low for step in self.manual_steps),
            sum(step.minutes_base for step in self.manual_steps),
            sum(step.minutes_high for step in self.manual_steps),
        )
        expected = (
            self.manual_minutes.low,
            self.manual_minutes.base,
            self.manual_minutes.high,
        )
        if any(abs(a - b) > 1e-6 for a, b in zip(totals, expected, strict=True)):
            raise ValueError("manual step totals must equal manual_minutes")
        if self.abstain and not self.abstention_reason:
            raise ValueError("abstention_reason is required when abstain=true")
        return self


class PassportFile(StrictModel):
    schema_version: Literal["1.0"]
    passports: list[EconomicPassport]

    @model_validator(mode="after")
    def unique_targets(self) -> "PassportFile":
        keys = [(p.target_type, p.target_id) for p in self.passports]
        if len(keys) != len(set(keys)):
            raise ValueError("passport target_type/target_id must be unique")
        return self


class QualityCriterion(StrictModel):
    criterion: str = Field(min_length=1)
    weight: float = Field(ge=0, le=1)
    score: float = Field(ge=0, le=1)


class QualityEvaluation(StrictModel):
    run_id: str = Field(min_length=1)
    evaluation_source: str = Field(min_length=1)
    evidence_level: EvidenceLevel
    criteria: list[QualityCriterion] = Field(default_factory=list)
    review_minutes: float = Field(default=0, ge=0)
    rework_minutes: float = Field(default=0, ge=0)
    prompt_minutes: float | None = Field(default=None, ge=0)
    active_wait_minutes: float | None = Field(default=None, ge=0)
    completed: bool | None = None
    reviewer_id: str | None = None
    evaluated_at: datetime | None = None
    human_minutes_web: float | None = Field(default=None, ge=0)
    web_cost: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_quality_source(self) -> "QualityEvaluation":
        if self.criteria:
            total = sum(item.weight for item in self.criteria)
            if abs(total - 1.0) > 1e-6:
                raise ValueError("quality criterion weights must sum to 1")
        elif self.completed is None:
            raise ValueError("criteria or binary completed is required")
        return self

    @property
    def quality_score(self) -> float:
        if self.criteria:
            return sum(item.weight * item.score for item in self.criteria)
        return 1.0 if self.completed else 0.0


class CostComponents(StrictModel):
    gpu_amortization: bool = True
    licenses: bool = True
    external_api: bool = True
    tools: bool = True
    electricity: bool = False
    support: bool = False
    development: bool = False


class FinancialConfig(StrictModel):
    schema_version: Literal["1.0"]
    currency: Literal["RUB"] = "RUB"
    employee_cost_per_hour: Literal[1500] = 1500
    gpu_purchase_cost: float = Field(ge=0)
    gpu_lifetime_years: float = Field(gt=0)
    license_cost_per_user_month: float = Field(ge=0)
    licensed_agent_users: int = Field(gt=0)
    web_users: int = Field(ge=0)
    agent_token_multiplier: float = Field(gt=0)
    working_days_per_month: int = Field(gt=0)
    working_hours_per_day: float = Field(default=8, gt=0)
    average_fte_month_cost_rub: float = Field(default=400000, ge=0)
    electricity_cost_per_month: float = Field(default=0, ge=0)
    support_cost_per_month: float = Field(default=0, ge=0)
    development_cost_per_month: float = Field(default=0, ge=0)
    shared_tools_cost_per_month: float = Field(default=0, ge=0)
    default_gpu_allocation_scenario: Literal[
        "conservative_full_gpu", "platform_token_ratio", "weighted_users"
    ] = "conservative_full_gpu"
    default_prompt_minutes: float | None = Field(default=None, ge=0)
    include_cost_components: CostComponents
    analysis_period_months: float = Field(default=1, gt=0)
    bootstrap_seed: int = 42
    bootstrap_iterations: int = Field(default=10000, ge=100)
    minimum_proven_evaluations: int = Field(default=5, ge=1)
    minimum_proven_coverage: float = Field(default=0.5, ge=0, le=1)
    minimum_economic_classification_margin: float = Field(
        default=0.05, ge=0, le=1
    )
    high_risk_threshold: float = Field(default=0.8, ge=0, le=1)
    simple_automation_manual_minutes: float = Field(default=15, ge=0)
    excessive_context_tokens: int = Field(default=50000, ge=1)
