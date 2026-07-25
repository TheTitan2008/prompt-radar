"""Versioned YAML catalog models."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from prompt_radar.config import load_yaml
from prompt_radar.naming.base import ClusterNamingResult


class Category(BaseModel):
    """One broad business category."""

    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    description: str


class KnownUseCase(BaseModel):
    """One concrete known use case."""

    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    description: str
    examples: list[str] = Field(default_factory=list)
    systems: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    expected_outcome: str = ""
    category_ids: list[str] = Field(default_factory=list)
    source_reference: str = ""
    draft: bool = True


class KnownUseCasePassport(ClusterNamingResult):
    """Validated draft economic passport for one known use case."""

    use_case_id: str
    estimation_source: str
    draft: bool = True


def load_categories(path: Path) -> list[Category]:
    """Load broad categories from YAML."""
    raw = load_yaml(path)
    return [Category.model_validate(item) for item in raw.get("categories", [])]


def load_use_cases(path: Path) -> list[KnownUseCase]:
    """Load known use cases from YAML."""
    raw = load_yaml(path)
    return [KnownUseCase.model_validate(item) for item in raw.get("use_cases", [])]


def load_use_case_passports(
    path: Path,
    use_cases: list[KnownUseCase],
) -> dict[str, KnownUseCasePassport]:
    """Load passports and require exact one-to-one coverage of known use cases."""
    raw = load_yaml(path)
    if raw.get("employee_cost_per_hour") != 1500:
        raise ValueError(
            "known use-case passports must use employee_cost_per_hour=1500"
        )
    items = [
        KnownUseCasePassport.model_validate(item)
        for item in raw.get("passports", [])
    ]
    by_id: dict[str, KnownUseCasePassport] = {}
    for item in items:
        if item.use_case_id in by_id:
            raise ValueError(
                f"duplicate known use-case passport: {item.use_case_id}"
            )
        by_id[item.use_case_id] = item
    expected = {item.id for item in use_cases}
    actual = set(by_id)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing or unknown:
        raise ValueError(
            "known use-case passport coverage mismatch; "
            f"missing={missing}, unknown={unknown}"
        )
    return by_id
