from __future__ import annotations

from prompt_radar.classification.catalogs import Category, KnownUseCase
from prompt_radar.classification.classifier import KnownMatcher
from prompt_radar.config import ClassificationConfig

from conftest import TinyEmbeddingService


def matcher() -> KnownMatcher:
    categories = [
        Category(id="email", name="Почта", description="Письма email"),
        Category(id="tasks", name="Задачи", description="Jira тикеты"),
    ]
    use_cases = [
        KnownUseCase(
            id="reply",
            name="Ответ по почте",
            description="Прочитать письмо и ответить",
            category_ids=["email"],
        ),
        KnownUseCase(
            id="jira",
            name="Создание Jira",
            description="Создать тикет задачу Jira",
            category_ids=["tasks"],
        ),
    ]
    return KnownMatcher(
        categories,
        use_cases,
        TinyEmbeddingService(),
        ClassificationConfig(
            known_use_case_threshold=0.65,
            additional_use_case_threshold=0.65,
            primary_category_threshold=0.6,
            additional_category_threshold=0.6,
        ),
    )


def test_multilabel_classification_is_supported() -> None:
    result = matcher().classify("Прочитай письмо и создай тикет Jira")
    assert {item.id for item in result.known_use_case_matches} == {"reply", "jira"}
    assert result.discovery_status == "known"


def test_weak_match_is_residual() -> None:
    result = matcher().classify("Стеклянный кит зелёный")
    assert result.classification_status == "residual"
    assert result.discovery_status == "unresolved"

