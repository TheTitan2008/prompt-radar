from __future__ import annotations

import json
import os
from pathlib import Path

from prompt_radar.classification.catalogs import (
    load_use_case_passports,
    load_use_cases,
)
from prompt_radar.economics import build_local_economic_context
from prompt_radar.environment import load_api_env_file
from prompt_radar.naming.known_requests import build_known_passport_requests


def test_all_31_known_use_cases_have_valid_draft_passports() -> None:
    use_cases = load_use_cases(Path("configs/known_use_cases.yaml"))
    passports = load_use_case_passports(
        Path("configs/known_use_case_passports.yaml"), use_cases
    )
    assert len(use_cases) == len(passports) == 31
    for use_case in use_cases:
        passport = passports[use_case.id]
        assert passport.draft is True
        assert sum(
            step.minutes_base for step in passport.manual_steps
        ) == passport.manual_minutes.base
        economics = build_local_economic_context(passport)
        assert economics["employee_cost_per_hour"] == 1500


def test_prepare_31_unsent_known_passport_requests() -> None:
    use_cases = load_use_cases(Path("configs/known_use_cases.yaml"))
    requests = build_known_passport_requests(use_cases, model="qwen-test")
    assert len(requests) == 31
    assert len({item["use_case_id"] for item in requests}) == 31
    encoded = json.dumps(requests, ensure_ascii=False)
    assert '"api_called": false' in encoded
    assert "employee_cost_per_hour" not in encoded
    assert all(
        item["request"]["model"] == "qwen-test" for item in requests
    )


def test_api_env_file_is_allowlisted_and_does_not_override(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("CLUSTER_ENRICHMENT_MODEL", "already-set")
    monkeypatch.delenv("CLUSTER_ENRICHMENT_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CLUSTER_ENRICHMENT_API_KEY=secret-from-file\n"
        "CLUSTER_ENRICHMENT_MODEL=must-not-override\n"
        "UNRELATED_DANGEROUS_VALUE=ignored\n",
        encoding="utf-8",
    )
    load_api_env_file(env_file)
    assert os.environ["CLUSTER_ENRICHMENT_API_KEY"] == "secret-from-file"
    assert os.environ["CLUSTER_ENRICHMENT_MODEL"] == "already-set"
    assert "UNRELATED_DANGEROUS_VALUE" not in os.environ
