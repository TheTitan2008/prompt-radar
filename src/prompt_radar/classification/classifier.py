"""Cosine multi-label matching with abstention."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from prompt_radar.classification.catalogs import Category, KnownUseCase
from prompt_radar.config import ClassificationConfig
from prompt_radar.embeddings.base import EmbeddingService
from prompt_radar.retrieval.cosine import cosine_matrix


@dataclass
class SimilarityMatch:
    """One catalog match; similarity is not a probability."""

    id: str
    name: str
    similarity_score: float
    threshold_used: float
    accepted: bool = False

    def to_dict(self) -> dict[str, object]:
        """Serialize the match."""
        return asdict(self)


@dataclass
class ClassificationResult:
    """Known matching result with explicit abstention state."""

    primary_category: SimilarityMatch | None
    additional_categories: list[SimilarityMatch]
    category_candidates: list[SimilarityMatch]
    known_use_case_matches: list[SimilarityMatch]
    classification_status: str
    discovery_status: str
    explanation: str

    def to_dict(self) -> dict[str, object]:
        """Serialize nested match objects."""
        return {
            "primary_category": (
                self.primary_category.to_dict() if self.primary_category else None
            ),
            "additional_categories": [
                item.to_dict() for item in self.additional_categories
            ],
            "category_candidates": [
                item.to_dict() for item in self.category_candidates
            ],
            "known_use_case_matches": [
                item.to_dict() for item in self.known_use_case_matches
            ],
            "classification_status": self.classification_status,
            "discovery_status": self.discovery_status,
            "explanation": self.explanation,
        }


class KnownMatcher:
    """Pre-embed catalogs and classify task passports with configurable gates."""

    def __init__(
        self,
        categories: list[Category],
        use_cases: list[KnownUseCase],
        embeddings: EmbeddingService,
        config: ClassificationConfig,
    ) -> None:
        self.categories = categories
        self.use_cases = use_cases
        self.embeddings = embeddings
        self.config = config
        self._category_vectors = embeddings.encode(
            [f"{item.name}. {item.description}" for item in categories],
            mode="document",
        )
        self._use_case_vectors = embeddings.encode(
            [
                " ".join(
                    (
                        item.name,
                        item.description,
                        " ".join(item.examples),
                        " ".join(item.systems),
                        " ".join(item.actions),
                        item.expected_outcome,
                    )
                )
                for item in use_cases
            ],
            mode="document",
        )

    @staticmethod
    def _rank(
        items: list[Category] | list[KnownUseCase],
        scores: np.ndarray,
        *,
        threshold: float,
        limit: int,
    ) -> list[SimilarityMatch]:
        order = sorted(
            range(len(items)),
            key=lambda index: (-float(scores[index]), items[index].id),
        )
        return [
            SimilarityMatch(
                id=items[index].id,
                name=items[index].name,
                similarity_score=float(scores[index]),
                threshold_used=threshold,
            )
            for index in order[:limit]
        ]

    def classify(self, task_passport_text: str) -> ClassificationResult:
        """Match one passport, returning residual when the known gate fails."""
        vector = self.embeddings.encode([task_passport_text], mode="query")
        category_scores = cosine_matrix(vector, self._category_vectors)[0]
        use_case_scores = cosine_matrix(vector, self._use_case_vectors)[0]
        category_candidates = self._rank(
            self.categories,
            category_scores,
            threshold=self.config.primary_category_threshold,
            limit=self.config.max_categories,
        )
        use_case_candidates = self._rank(
            self.use_cases,
            use_case_scores,
            threshold=self.config.known_use_case_threshold,
            limit=self.config.max_use_cases,
        )
        for index, match in enumerate(use_case_candidates):
            match.threshold_used = (
                self.config.known_use_case_threshold
                if index == 0
                else self.config.additional_use_case_threshold
            )
        primary_use_case_passed = bool(
            use_case_candidates
            and use_case_candidates[0].similarity_score
            >= self.config.known_use_case_threshold
        )
        if primary_use_case_passed:
            use_case_candidates[0].accepted = True
            for match in use_case_candidates[1:]:
                match.accepted = (
                    match.similarity_score
                    >= self.config.additional_use_case_threshold
                )
        accepted_use_cases = [
            match for match in use_case_candidates if match.accepted
        ]
        primary_category = (
            category_candidates[0]
            if category_candidates
            and category_candidates[0].similarity_score
            >= self.config.primary_category_threshold
            else None
        )
        if primary_category:
            primary_category.accepted = True
        additional_categories = [
            match
            for match in category_candidates[1:]
            if match.similarity_score
            >= self.config.additional_category_threshold
        ]
        for match in additional_categories:
            match.accepted = True
        if accepted_use_cases:
            return ClassificationResult(
                primary_category=primary_category,
                additional_categories=additional_categories,
                category_candidates=category_candidates,
                known_use_case_matches=accepted_use_cases,
                classification_status="matched_known",
                discovery_status="known",
                explanation=(
                    "At least one known use-case cosine similarity passed the "
                    "configured threshold."
                ),
            )
        return ClassificationResult(
            primary_category=primary_category,
            additional_categories=additional_categories,
            category_candidates=category_candidates,
            known_use_case_matches=use_case_candidates,
            classification_status="residual",
            discovery_status="unresolved",
            explanation=(
                "No known use-case cosine similarity passed the configured "
                "threshold; task was sent to the residual pool."
            ),
        )
