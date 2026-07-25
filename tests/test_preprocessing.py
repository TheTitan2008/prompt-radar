from __future__ import annotations

from datetime import datetime, timezone

from prompt_radar.config import TextProcessingConfig
from prompt_radar.models import Message
from prompt_radar.preprocessing.chunker import chunk_text
from prompt_radar.preprocessing.message_parser import extract_current_goal
from prompt_radar.preprocessing.prompt_router import ProcessingMode, choose_mode
from prompt_radar.preprocessing.task_passport import build_task_passport
from prompt_radar.preprocessing.tokenizer import WhitespaceTokenizer


def message(content: str) -> Message:
    return Message(
        message_id="m1",
        conversation_id="c1",
        run_id="r1",
        role="user",
        content=content,
        sequence_number=1,
        created_at=datetime.now(timezone.utc),
    )


def test_short_without_attachments_uses_mode_a() -> None:
    mode, _ = choose_mode(
        "Покажи задачи", [], WhitespaceTokenizer(), TextProcessingConfig()
    )
    assert mode == ProcessingMode.SHORT_DIRECT


def test_short_with_attachments_uses_mode_b() -> None:
    mode, _ = choose_mode(
        "Проверь файл", ["a1"], WhitespaceTokenizer(), TextProcessingConfig()
    )
    assert mode == ProcessingMode.SHORT_WITH_ATTACHMENTS


def test_long_prompt_uses_mode_c() -> None:
    config = TextProcessingConfig(direct_embedding_max_tokens=10)
    mode, count = choose_mode(
        " ".join(["длинный"] * 20), [], WhitespaceTokenizer(), config
    )
    assert mode == ProcessingMode.LONG_EXTRACTIVE
    assert count == 20


def test_user_query_is_extracted_from_large_payload() -> None:
    content = (
        "<context>" + "шум " * 1000 + "</context>"
        "<user_query>Создай встречу команды</user_query>"
        "Создай встречу команды"
    )
    parsed = extract_current_goal([message(content)])
    assert parsed.current_goal == "Создай встречу команды"
    assert "xml_user_query" in parsed.method
    assert not parsed.multiple_goals


def test_chunker_preserves_overlap() -> None:
    chunks = chunk_text(
        "one two three four five six seven",
        WhitespaceTokenizer(),
        chunk_size=4,
        overlap=2,
    )
    assert chunks[0].text.split()[-2:] == chunks[1].text.split()[:2]


def test_task_passport_bounds_a_huge_extracted_goal() -> None:
    tokenizer = WhitespaceTokenizer()
    config = TextProcessingConfig(goal_max_tokens=64)
    content = "черновик\n" + " ".join(f"ctx{i}" for i in range(10_000))
    parsed = extract_current_goal([message(content)])
    passport, _ = build_task_passport(
        content,
        parsed,
        tokenizer,
        config,
        tool_names=[],
    )
    assert tokenizer.count_tokens(passport) <= 1000
    assert tokenizer.count_tokens(passport) < tokenizer.count_tokens(content)
