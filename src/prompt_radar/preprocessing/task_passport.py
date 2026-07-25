"""Extractive task-passport construction."""

from __future__ import annotations

import re

from prompt_radar.config import TextProcessingConfig
from prompt_radar.preprocessing.chunker import TextChunk, chunk_text
from prompt_radar.preprocessing.message_parser import ParsedGoal
from prompt_radar.preprocessing.tokenizer import Tokenizer

_INSTRUCTION = re.compile(
    r"\b(нужно|сделай|найди|создай|подготовь|сравни|проверь|"
    r"проанализируй|сформируй|покажи|выгрузи|ответь)\b",
    re.IGNORECASE,
)


def build_task_passport(
    prompt_text: str,
    goal: ParsedGoal,
    tokenizer: Tokenizer,
    config: TextProcessingConfig,
    *,
    tool_names: list[str],
    retrieved_texts: list[str] | None = None,
) -> tuple[str, list[TextChunk]]:
    """Build a bounded extractive passport and return its evidence chunks."""
    goal_text = goal.current_goal
    if (
        goal_text
        and tokenizer.count_tokens(goal_text) > config.goal_max_tokens
    ):
        half = max(1, config.goal_max_tokens // 2)
        goal_chunks = chunk_text(
            goal_text,
            tokenizer,
            chunk_size=half,
            overlap=0,
            prefix="goal",
        )
        selected = goal_chunks[:1]
        if len(goal_chunks) > 1:
            selected.append(goal_chunks[-1])
        goal_text = "\n[…]\n".join(chunk.text for chunk in selected)
    evidence_source = (
        goal.current_goal
        if "xml_user_query" in goal.method and goal.current_goal
        else prompt_text
    )
    chunks = chunk_text(
        evidence_source,
        tokenizer,
        chunk_size=config.chunk_size_tokens,
        overlap=config.chunk_overlap_tokens,
        prefix="prompt",
    )
    evidence: list[TextChunk] = []
    if chunks:
        candidates = (
            chunks[:2]
            + chunks[-2:]
            + [chunk for chunk in chunks if _INSTRUCTION.search(chunk.text)]
        )
        seen: set[str] = set()
        for candidate in candidates:
            normalized = " ".join(candidate.text.casefold().split())
            if normalized not in seen:
                seen.add(normalized)
                evidence.append(candidate)
            if len(evidence) >= config.instruction_candidate_limit:
                break
    parts = [f"Текущая цель: {goal_text or '[не определена]'}"]
    if tool_names:
        parts.append("Инструменты: " + ", ".join(tool_names))
    if (
        evidence
        and tokenizer.count_tokens(prompt_text) > config.direct_embedding_max_tokens
        and evidence_source != goal.current_goal
    ):
        parts.append(
            "Доказательные фрагменты:\n"
            + "\n".join(
                f"- [{chunk.chunk_id} {chunk.token_start}:{chunk.token_end}] "
                f"{chunk.text[:1200]}"
                for chunk in evidence[: config.representative_chunk_limit]
            )
        )
    if retrieved_texts:
        parts.append(
            "Релевантный контекст вложений:\n"
            + "\n".join(f"- {text[:1200]}" for text in retrieved_texts)
        )
    return "\n".join(parts), evidence
