"""Legacy fail-closed provider retained for backwards compatibility."""

from __future__ import annotations

from prompt_radar.errors import ExternalApiDisabledError
from prompt_radar.naming.base import (
    ClusterNamingRequest,
    ClusterNamingResult,
)


class QwenApiClusterNamingProvider:
    """Old provider name that remains permanently fail-closed."""

    def __init__(self) -> None:
        self.enabled = False

    def name_cluster(
        self, request: ClusterNamingRequest
    ) -> ClusterNamingResult:
        """Direct callers to the explicit generic provider."""
        raise ExternalApiDisabledError(
            "Legacy Qwen stub is disabled; use the explicit OpenAI-compatible "
            "cluster enrichment provider."
        )
