"""Validated relationship indexes."""

from __future__ import annotations

from collections import defaultdict

from prompt_radar.models import DatasetBundle, Message


def messages_by_run(bundle: DatasetBundle) -> dict[str, list[Message]]:
    """Return explicit-run messages sorted by sequence, time and ID."""
    grouped: dict[str, list[Message]] = defaultdict(list)
    for message in bundle.messages:
        if message.run_id:
            grouped[message.run_id].append(message)
    for items in grouped.values():
        items.sort(
            key=lambda item: (
                item.sequence_number,
                item.created_at,
                item.message_id,
            )
        )
    return dict(grouped)

