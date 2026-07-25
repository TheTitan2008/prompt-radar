"""Domain exceptions with actionable user-facing messages."""

from __future__ import annotations


class PromptRadarError(Exception):
    """Base class for expected Prompt Radar failures."""


class ArchiveSecurityError(PromptRadarError):
    """Raised when an input archive violates a security constraint."""


class DatasetValidationError(PromptRadarError):
    """Raised when the dataset contract is not satisfied."""


class ModelUnavailableError(PromptRadarError):
    """Raised when an explicitly requested local model is not cached."""


class ExternalApiDisabledError(PromptRadarError):
    """Raised when the intentionally disabled naming API is requested."""


class ExternalApiError(PromptRadarError):
    """Raised when explicit cluster enrichment fails safely."""
