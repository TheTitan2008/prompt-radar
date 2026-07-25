"""Three-mode prompt routing."""

from __future__ import annotations

from enum import StrEnum

from prompt_radar.config import TextProcessingConfig
from prompt_radar.preprocessing.tokenizer import Tokenizer


class ProcessingMode(StrEnum):
    """Supported prompt-processing modes."""

    SHORT_DIRECT = "short_direct"
    SHORT_WITH_ATTACHMENTS = "short_with_attachments"
    LONG_EXTRACTIVE = "long_extractive"


def choose_mode(
    text: str,
    attachment_ids: list[str],
    tokenizer: Tokenizer,
    config: TextProcessingConfig,
) -> tuple[ProcessingMode, int]:
    """Choose a processing mode and return the raw token count."""
    count = tokenizer.count_tokens(text)
    if count > config.direct_embedding_max_tokens:
        return ProcessingMode.LONG_EXTRACTIVE, count
    if attachment_ids:
        return ProcessingMode.SHORT_WITH_ATTACHMENTS, count
    return ProcessingMode.SHORT_DIRECT, count

