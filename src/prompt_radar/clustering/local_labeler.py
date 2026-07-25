"""Local provisional labels for numeric clusters."""

from __future__ import annotations

import re
from collections import Counter

_WORDS = re.compile(r"[A-Za-zА-Яа-яЁё]{3,}")
_STOPWORDS = {
    "для",
    "что",
    "как",
    "это",
    "или",
    "при",
    "пользователь",
    "текущая",
    "цель",
    "нужно",
    "сделай",
    "найди",
    "создай",
}


def provisional_label(
    texts: list[str], broad_category: str | None
) -> tuple[str, list[str]]:
    """Create an explicitly non-final label from local term frequencies."""
    counter = Counter(
        word.casefold()
        for text in texts
        for word in _WORDS.findall(text)
        if word.casefold() not in _STOPWORDS
    )
    keywords = [word for word, _ in counter.most_common(5)]
    category = broad_category or "Новый сценарий"
    suffix = " / ".join(keywords[:3]) if keywords else "без устойчивых терминов"
    return f"{category} — {suffix}", keywords

