"""Message-aware current-goal extraction."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from prompt_radar.models import Message

_USER_QUERY = re.compile(
    r"<user_query(?:\s[^>]*)?>(?P<goal>.*?)</user_query>",
    re.IGNORECASE | re.DOTALL,
)
_CONTEXT_BLOCK = re.compile(
    r"<(?:context|source)(?:\s[^>]*)?>.*?</(?:context|source)>",
    re.IGNORECASE | re.DOTALL,
)
_IMPERATIVE = re.compile(
    r"\b(нужно|сделай|найди|создай|подготовь|сравни|проверь|"
    r"проанализируй|сформируй|покажи|выгрузи|ответь|добавь)\b",
    re.IGNORECASE,
)
_DEPENDENT = re.compile(
    r"^\s*(сделай\s+это|продолжай|добавь\s+ещё|как\s+выше|"
    r"сделай\s+по\s+предыдущему\s+варианту)\b",
    re.IGNORECASE,
)


@dataclass
class ParsedGoal:
    """Extracted current goal with provenance and abstention metadata."""

    current_goal: str
    evidence_message_ids: list[str]
    evidence_spans: list[dict[str, int | str]]
    method: str
    confidence: float
    multiple_goals: bool = False
    ambiguity_reason: str | None = None
    parsed_roles: list[str] = field(default_factory=list)


def _normalized_unique(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = " ".join(value.split()).strip()
        key = clean.casefold().rstrip("?.!")
        if clean and key not in seen:
            seen.add(key)
            output.append(clean)
    return output


def _inner_messages(content: str) -> list[dict[str, Any]] | None:
    stripped = content.strip()
    if not stripped.startswith(("{", "[")):
        return None
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict) and isinstance(payload.get("messages"), list):
        return [item for item in payload["messages"] if isinstance(item, dict)]
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return payload
    return None


def _extract_from_content(content: str) -> tuple[list[str], str, list[tuple[int, int]]]:
    matches = list(_USER_QUERY.finditer(content))
    if matches:
        values = _normalized_unique([match.group("goal") for match in matches])
        return values, "xml_user_query", [
            (match.start("goal"), match.end("goal")) for match in matches
        ]
    without_context = _CONTEXT_BLOCK.sub(" ", content)
    lines = [line.strip() for line in without_context.splitlines() if line.strip()]
    candidates = [line for line in lines if _IMPERATIVE.search(line)]
    values = _normalized_unique(candidates[-3:] if candidates else lines[-1:])
    if values:
        chosen = values[-1]
        start = content.rfind(chosen)
        return [chosen], "last_user_message", [
            (max(start, 0), max(start, 0) + len(chosen))
        ]
    return [], "unresolved", []


def extract_current_goal(messages: list[Message]) -> ParsedGoal:
    """Extract the last active user goal, respecting nested payload roles."""
    ordered = sorted(
        messages,
        key=lambda item: (item.sequence_number, item.created_at, item.message_id),
    )
    user_messages = [message for message in ordered if message.role == "user"]
    if not user_messages:
        return ParsedGoal(
            current_goal="",
            evidence_message_ids=[],
            evidence_spans=[],
            method="unresolved",
            confidence=0.0,
            ambiguity_reason="no_user_message",
            parsed_roles=[message.role for message in ordered],
        )
    outer = user_messages[-1]
    if len(user_messages) >= 2 and _DEPENDENT.search(outer.content):
        previous = user_messages[-2]
        combined = (
            " ".join(previous.content.split())
            + "; уточнение: "
            + " ".join(outer.content.split())
        )
        return ParsedGoal(
            current_goal=combined,
            evidence_message_ids=[previous.message_id, outer.message_id],
            evidence_spans=[
                {
                    "message_id": previous.message_id,
                    "start": 0,
                    "end": len(previous.content),
                },
                {
                    "message_id": outer.message_id,
                    "start": 0,
                    "end": len(outer.content),
                },
            ],
            method="message_aware_extractive:dependent_user_context",
            confidence=0.88,
            parsed_roles=[message.role for message in ordered],
        )
    inner = _inner_messages(outer.content)
    roles = [message.role for message in ordered]
    content = outer.content
    if inner:
        roles.extend(str(item.get("role", "unknown")) for item in inner)
        nested_users = [
            str(item.get("content", ""))
            for item in inner
            if item.get("role") == "user"
        ]
        if nested_users:
            content = nested_users[-1]
    goals, method, spans = _extract_from_content(content)
    unique = _normalized_unique(goals)
    if not unique:
        return ParsedGoal(
            current_goal="",
            evidence_message_ids=[outer.message_id],
            evidence_spans=[],
            method="unresolved",
            confidence=0.0,
            ambiguity_reason="no_instruction_like_goal",
            parsed_roles=roles,
        )
    multiple = len(unique) > 1
    goal = unique[-1]
    return ParsedGoal(
        current_goal=goal,
        evidence_message_ids=[outer.message_id],
        evidence_spans=[
            {"message_id": outer.message_id, "start": start, "end": end}
            for start, end in spans[-1:]
        ],
        method="message_aware_extractive:" + method,
        confidence=0.98 if method == "xml_user_query" else (0.82 if not multiple else 0.55),
        multiple_goals=multiple,
        ambiguity_reason="multiple_distinct_goal_candidates" if multiple else None,
        parsed_roles=roles,
    )
