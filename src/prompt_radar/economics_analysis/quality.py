"""Quality scoring and reproducible uncertainty intervals."""

from __future__ import annotations

import math

import numpy as np

from prompt_radar.economics_analysis.models import QualityEvaluation

EVIDENCE_RANK = {"E0": 0, "E1": 1, "E2": 2, "E3": 3}


def lowest_evidence(levels: list[str], default: str = "E0") -> str:
    if not levels:
        return default
    return min(levels, key=lambda item: EVIDENCE_RANK[item])


def highest_evidence(levels: list[str], default: str = "E0") -> str:
    if not levels:
        return default
    return max(levels, key=lambda item: EVIDENCE_RANK[item])


def wilson_interval(successes: int, total: int, z: float = 1.95996398454) -> tuple[float, float]:
    if total <= 0:
        raise ValueError("total must be positive")
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
        / denominator
    )
    return max(0.0, centre - margin), min(1.0, centre + margin)


def bootstrap_mean_interval(
    values: list[float], *, seed: int, iterations: int
) -> tuple[float, float]:
    if not values:
        raise ValueError("values cannot be empty")
    rng = np.random.default_rng(seed)
    source = np.asarray(values, dtype=np.float64)
    samples = rng.choice(source, size=(iterations, len(source)), replace=True)
    means = samples.mean(axis=1)
    low, high = np.percentile(means, [2.5, 97.5])
    return float(low), float(high)


def quality_summary(
    evaluations: list[QualityEvaluation], *, seed: int, iterations: int
) -> dict[str, float | int | str | None]:
    if not evaluations:
        return {
            "evaluated_run_count": 0,
            "mean_quality": None,
            "quality_ci_low": None,
            "quality_ci_high": None,
            "quality_interval_method": None,
            "evidence_level": "E0",
        }
    scores = [item.quality_score for item in evaluations]
    if all(score in {0.0, 1.0} for score in scores):
        low, high = wilson_interval(sum(score == 1.0 for score in scores), len(scores))
        method = "wilson_95"
    else:
        low, high = bootstrap_mean_interval(
            scores, seed=seed, iterations=iterations
        )
        method = "bootstrap_mean_95"
    return {
        "evaluated_run_count": len(scores),
        "mean_quality": sum(scores) / len(scores),
        "quality_ci_low": low,
        "quality_ci_high": high,
        "quality_interval_method": method,
        "evidence_level": lowest_evidence(
            [item.evidence_level for item in evaluations]
        ),
    }
