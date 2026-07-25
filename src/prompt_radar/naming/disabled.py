"""Disabled naming provider used in the first pipeline."""

from __future__ import annotations

from prompt_radar.errors import ExternalApiDisabledError
from prompt_radar.naming.base import (
    ClusterNamingRequest,
    ClusterNamingResult,
)


class DisabledClusterNamingProvider:
    """Guarantee that no external generative request is performed."""

    def name_cluster(
        self, request: ClusterNamingRequest
    ) -> ClusterNamingResult:
        """Always fail explicitly without network access."""
        raise ExternalApiDisabledError(
            "Generative cluster naming is disabled; use the local provisional label."
        )

