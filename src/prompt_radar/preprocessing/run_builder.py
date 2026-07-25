"""Run-level business task construction."""

from __future__ import annotations

from dataclasses import dataclass, field

from prompt_radar.config import PipelineConfig
from prompt_radar.embeddings.base import EmbeddingService
from prompt_radar.ingestion.relationship_builder import messages_by_run
from prompt_radar.models import DatasetBundle, Message
from prompt_radar.preprocessing.fallback_run_segmenter import segment_missing_runs

_ECONOMICS_EVENT_FIELDS = {
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "gpu_seconds",
    "gpu_time_seconds",
    "compute_seconds",
    "model_calls",
    "amount_rub",
    "cost_rub",
    "component",
    "retry_count",
    "retry_cost_rub",
    "tool_error_count",
    "tool_error_cost_rub",
}


@dataclass
class RunTask:
    """One unit of analysis constructed from one explicit or fallback run."""

    run_id: str
    conversation_id: str
    user_id: str
    messages: list[Message]
    user_prompt_text: str
    conversation_context: str
    attachment_ids: list[str]
    tool_names: list[str]
    run_metadata: dict[str, object] = field(default_factory=dict)
    is_fallback: bool = False


def _build_task(
    run_id: str,
    messages: list[Message],
    bundle: DatasetBundle,
    *,
    is_fallback: bool,
) -> RunTask:
    conversation_id = messages[0].conversation_id
    conversation = next(
        item
        for item in bundle.conversations
        if item.conversation_id == conversation_id
    )
    user_texts = [item.content for item in messages if item.role == "user"]
    context = [
        f"{item.role}: {item.content}"
        for item in messages
        if item.role in {"assistant", "tool"}
    ]
    attachment_ids = list(
        dict.fromkeys(
            attachment_id
            for message in messages
            for attachment_id in message.attachment_ids
        )
    )
    events = [event for event in bundle.events if event.run_id == run_id]
    tools = list(
        dict.fromkeys(event.tool_name for event in events if event.tool_name)
    )
    explicit_run = next((item for item in bundle.runs if item.run_id == run_id), None)
    metadata: dict[str, object] = {
        "is_fallback": is_fallback,
        "message_count": len(messages),
        "event_count": len(events),
        "event_usage": [
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "status": event.status,
                "tool_name": event.tool_name,
                "usage": {
                    key: value
                    for source in (event.payload, event.metadata)
                    for key, value in source.items()
                    if key in _ECONOMICS_EVENT_FIELDS
                    and isinstance(value, (int, float, str))
                    and not isinstance(value, bool)
                },
            }
            for event in events
        ],
    }
    if explicit_run:
        metadata.update(explicit_run.model_dump(mode="json"))
    return RunTask(
        run_id=run_id,
        conversation_id=conversation_id,
        user_id=conversation.user_id,
        messages=messages,
        user_prompt_text="\n\n".join(user_texts),
        conversation_context="\n".join(context),
        attachment_ids=attachment_ids,
        tool_names=tools,
        run_metadata=metadata,
        is_fallback=is_fallback,
    )


def build_run_tasks(
    bundle: DatasetBundle,
    config: PipelineConfig,
    embeddings: EmbeddingService,
) -> list[RunTask]:
    """Build explicit-run tasks, followed by separately segmented fallback tasks."""
    tasks = [
        _build_task(run_id, messages, bundle, is_fallback=False)
        for run_id, messages in messages_by_run(bundle).items()
    ]
    fallback = segment_missing_runs(
        bundle.messages, config.fallback_segmentation, embeddings
    )
    tasks.extend(
        _build_task(run_id, messages, bundle, is_fallback=True)
        for run_id, messages in fallback.items()
    )
    return sorted(tasks, key=lambda item: (item.conversation_id, item.run_id))
