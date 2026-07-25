"""Dataset schema and relationship validation."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from prompt_radar.errors import DatasetValidationError
from prompt_radar.ingestion.jsonl_loader import iter_jsonl, read_json
from prompt_radar.models import (
    Attachment,
    Conversation,
    DatasetBundle,
    Event,
    Manifest,
    Message,
    Run,
    User,
    ValidationIssue,
    ValidationReport,
)

_REQUIRED_FILES = (
    "manifest.json",
    "users.jsonl",
    "conversations.jsonl",
    "messages.jsonl",
    "runs.jsonl",
    "events.jsonl",
    "attachments.jsonl",
    "cost_config.json",
)
T = TypeVar("T", bound=BaseModel)


def _load_records(
    root: Path,
    filename: str,
    model: type[T],
    issues: list[ValidationIssue],
) -> tuple[list[T], int]:
    records: list[T] = []
    skipped = 0
    for line, raw in iter_jsonl(root / filename):
        try:
            records.append(model.model_validate(raw))
        except ValidationError as exc:
            skipped += 1
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="invalid_record",
                    file=filename,
                    line=line,
                    message=str(exc.errors(include_url=False)),
                )
            )
    return records, skipped


def _duplicates(records: list[Any], id_field: str) -> set[str]:
    counts = Counter(str(getattr(record, id_field)) for record in records)
    return {record_id for record_id, count in counts.items() if count > 1}


def validate_extracted(root: Path) -> tuple[DatasetBundle | None, ValidationReport]:
    """Validate schema, IDs and relationships in an extracted dataset."""
    root = root.resolve()
    issues: list[ValidationIssue] = []
    missing = [name for name in _REQUIRED_FILES if not (root / name).is_file()]
    if missing:
        for name in missing:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="missing_required_file",
                    file=name,
                    message=f"Required dataset file is missing: {name}",
                )
            )
        return None, ValidationReport(valid=False, issues=issues)

    try:
        manifest = Manifest.model_validate(read_json(root / "manifest.json"))
    except (DatasetValidationError, ValidationError) as exc:
        issues.append(
            ValidationIssue(
                severity="error",
                code="invalid_manifest",
                file="manifest.json",
                message=str(exc),
            )
        )
        return None, ValidationReport(valid=False, issues=issues)
    major = int(manifest.schema_version.split(".", 1)[0])
    if major != 1:
        issues.append(
            ValidationIssue(
                severity="error",
                code="unsupported_schema_major",
                file="manifest.json",
                message=(
                    f"Unsupported schema_version {manifest.schema_version}; "
                    "supported major version is 1"
                ),
            )
        )
        return None, ValidationReport(
            valid=False,
            dataset_id=manifest.dataset_id,
            schema_version=manifest.schema_version,
            issues=issues,
        )

    users, skipped_u = _load_records(root, "users.jsonl", User, issues)
    conversations, skipped_c = _load_records(
        root, "conversations.jsonl", Conversation, issues
    )
    messages, skipped_m = _load_records(root, "messages.jsonl", Message, issues)
    runs, skipped_r = _load_records(root, "runs.jsonl", Run, issues)
    events, skipped_e = _load_records(root, "events.jsonl", Event, issues)
    attachments, skipped_a = _load_records(
        root, "attachments.jsonl", Attachment, issues
    )
    try:
        cost_config = read_json(root / "cost_config.json")
        if not isinstance(cost_config, dict):
            raise DatasetValidationError(
                "cost_config.json must contain a JSON object"
            )
        if _contains_removed_worker_role(cost_config):
            raise DatasetValidationError(
                "role-specific labor rates are not supported; "
                "use the fixed employee_cost_per_hour=1500"
            )
        configured_rate = cost_config.get("employee_cost_per_hour", 1500)
        if configured_rate != 1500:
            raise DatasetValidationError(
                "employee_cost_per_hour is fixed at 1500"
            )
        cost_config["employee_cost_per_hour"] = 1500
    except DatasetValidationError as exc:
        issues.append(
            ValidationIssue(
                severity="error",
                code="invalid_cost_config",
                file="cost_config.json",
                message=str(exc),
            )
        )
        cost_config = {}

    entities: list[tuple[str, list[Any], str]] = [
        ("users.jsonl", users, "user_id"),
        ("conversations.jsonl", conversations, "conversation_id"),
        ("messages.jsonl", messages, "message_id"),
        ("runs.jsonl", runs, "run_id"),
        ("events.jsonl", events, "event_id"),
        ("attachments.jsonl", attachments, "attachment_id"),
    ]
    for filename, records, field in entities:
        for duplicate in sorted(_duplicates(records, field)):
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="duplicate_id",
                    file=filename,
                    message=f"Duplicate {field}: {duplicate}",
                )
            )

    user_ids = {item.user_id for item in users}
    conversation_by_id = {item.conversation_id: item for item in conversations}
    run_by_id = {item.run_id: item for item in runs}
    message_by_id = {item.message_id: item for item in messages}
    attachment_by_id = {item.attachment_id: item for item in attachments}

    def error(code: str, message: str, file: str) -> None:
        issues.append(
            ValidationIssue(
                severity="error", code=code, message=message, file=file
            )
        )

    for conversation in conversations:
        if conversation.user_id not in user_ids:
            error(
                "orphan_user",
                f"Conversation {conversation.conversation_id} references "
                f"missing user_id {conversation.user_id}",
                "conversations.jsonl",
            )
        if conversation.owner_user_id is not None:
            if conversation.owner_user_id not in user_ids:
                error(
                    "orphan_owner_user",
                    f"Conversation {conversation.conversation_id} references "
                    f"missing owner_user_id {conversation.owner_user_id}",
                    "conversations.jsonl",
                )
            if conversation.owner_user_id != conversation.user_id:
                error(
                    "owner_user_mismatch",
                    f"Conversation {conversation.conversation_id} has user_id "
                    f"{conversation.user_id} but owner_user_id "
                    f"{conversation.owner_user_id}",
                    "conversations.jsonl",
                )
    for run in runs:
        conversation = conversation_by_id.get(run.conversation_id)
        if conversation is None:
            error(
                "orphan_conversation",
                f"Run {run.run_id} references missing conversation_id "
                f"{run.conversation_id}",
                "runs.jsonl",
            )
        elif run.user_id is not None and run.user_id != conversation.user_id:
            error(
                "run_user_mismatch",
                f"Run {run.run_id} has user_id {run.user_id} but conversation "
                f"{run.conversation_id} belongs to {conversation.user_id}",
                "runs.jsonl",
            )
        if run.user_id is not None and run.user_id not in user_ids:
            error(
                "orphan_run_user",
                f"Run {run.run_id} references missing user_id {run.user_id}",
                "runs.jsonl",
            )
        _validate_ai_processing_minutes(run, error)
        if run.parent_run_id and run.parent_run_id not in run_by_id:
            error(
                "orphan_parent_run",
                f"Run {run.run_id} references missing parent_run_id "
                f"{run.parent_run_id}",
                "runs.jsonl",
            )
    for message in messages:
        conversation = conversation_by_id.get(message.conversation_id)
        if conversation is None:
            error(
                "orphan_conversation",
                f"Message {message.message_id} references missing "
                f"conversation_id {message.conversation_id}",
                "messages.jsonl",
            )
        if message.run_id:
            run = run_by_id.get(message.run_id)
            if run is None:
                error(
                    "orphan_run",
                    f"Message {message.message_id} references missing run_id "
                    f"{message.run_id}",
                    "messages.jsonl",
                )
            elif run.conversation_id != message.conversation_id:
                error(
                    "cross_conversation_run",
                    f"Message {message.message_id} and run {message.run_id} "
                    "belong to different conversations",
                    "messages.jsonl",
                )
            elif message.sender_user_id is not None and run.user_id is not None:
                if message.role == "user" and message.sender_user_id != run.user_id:
                    error(
                        "message_sender_mismatch",
                        f"Message {message.message_id} has sender_user_id "
                        f"{message.sender_user_id} but run {message.run_id} "
                        f"belongs to {run.user_id}",
                        "messages.jsonl",
                    )
        if message.sender_user_id is not None and message.sender_user_id not in user_ids:
            error(
                "orphan_sender_user",
                f"Message {message.message_id} references missing "
                f"sender_user_id {message.sender_user_id}",
                "messages.jsonl",
            )
        if (
            conversation is not None
            and message.role == "user"
            and message.sender_user_id is not None
            and message.sender_user_id != conversation.user_id
        ):
            error(
                "message_sender_mismatch",
                f"Message {message.message_id} has sender_user_id "
                f"{message.sender_user_id} but conversation "
                f"{message.conversation_id} belongs to {conversation.user_id}",
                "messages.jsonl",
            )
        for attachment_id in message.attachment_ids:
            if attachment_id not in attachment_by_id:
                error(
                    "orphan_attachment",
                    f"Message {message.message_id} references missing "
                    f"attachment_id {attachment_id}",
                    "messages.jsonl",
                )
    for event in events:
        if event.conversation_id not in conversation_by_id:
            error(
                "orphan_conversation",
                f"Event {event.event_id} references missing conversation_id "
                f"{event.conversation_id}",
                "events.jsonl",
            )
        if event.run_id and event.run_id not in run_by_id:
            error(
                "orphan_run",
                f"Event {event.event_id} references missing run_id {event.run_id}",
                "events.jsonl",
            )
        elif event.run_id:
            run = run_by_id[event.run_id]
            if run.conversation_id != event.conversation_id:
                error(
                    "cross_conversation_run",
                    f"Event {event.event_id} and run {event.run_id} belong "
                    "to different conversations",
                    "events.jsonl",
                )
            elif run.finished_at is not None:
                if event.created_at < run.started_at or event.created_at > run.finished_at:
                    error(
                        "event_outside_run_interval",
                        f"Event {event.event_id} timestamp is outside run "
                        f"{event.run_id} interval",
                        "events.jsonl",
                    )
        if event.message_id and event.message_id not in message_by_id:
            error(
                "orphan_message",
                f"Event {event.event_id} references missing message_id "
                f"{event.message_id}",
                "events.jsonl",
            )
    for attachment in attachments:
        message = message_by_id.get(attachment.message_id)
        if message is None:
            error(
                "orphan_message",
                f"Attachment {attachment.attachment_id} references missing "
                f"message_id {attachment.message_id}",
                "attachments.jsonl",
            )
        elif attachment.attachment_id not in message.attachment_ids:
            error(
                "undeclared_attachment",
                f"Message {attachment.message_id} does not list attachment "
                f"{attachment.attachment_id}",
                "attachments.jsonl",
            )
        relative = PurePosixPath(attachment.path.replace("\\", "/"))
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or not relative.parts
            or relative.parts[0] != "attachments"
        ):
            error(
                "unsafe_attachment_path",
                f"Unsafe attachment path: {attachment.path}",
                "attachments.jsonl",
            )
            continue
        file_path = root.joinpath(*relative.parts)
        if not file_path.is_file():
            error(
                "missing_attachment_file",
                f"Attachment file is missing: {attachment.path}",
                "attachments.jsonl",
            )

    skipped = skipped_u + skipped_c + skipped_m + skipped_r + skipped_e + skipped_a
    counts = {
        "users": len(users),
        "conversations": len(conversations),
        "messages": len(messages),
        "runs": len(runs),
        "events": len(events),
        "attachments": len(attachments),
    }
    valid = not any(issue.severity == "error" for issue in issues)
    report = ValidationReport(
        valid=valid,
        dataset_id=manifest.dataset_id,
        schema_version=manifest.schema_version,
        record_counts=counts,
        issues=issues,
        skipped_records=skipped,
    )
    if not valid:
        return None, report
    bundle = DatasetBundle(
        manifest=manifest,
        users=users,
        conversations=conversations,
        runs=runs,
        messages=messages,
        events=events,
        attachments=attachments,
        cost_config=cost_config,
        root=str(root),
    )
    return bundle, report


def _contains_removed_worker_role(value: Any) -> bool:
    """Reject the removed role-specific pricing field at any nesting depth."""
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).casefold().replace("-", "_")
            if normalized == "worker_role":
                return True
            if _contains_removed_worker_role(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_removed_worker_role(item) for item in value)
    return False


def _validate_ai_processing_minutes(run: Run, error: Any) -> None:
    metadata = run.metadata or {}
    has_metric = any(
        key in metadata
        for key in (
            "ai_processing_minutes",
            "ai_processing_minutes_source",
            "ai_processing_minutes_evidence_level",
        )
    )
    if not has_metric:
        return
    minutes = metadata.get("ai_processing_minutes")
    source = metadata.get("ai_processing_minutes_source")
    evidence = metadata.get("ai_processing_minutes_evidence_level")
    if not isinstance(minutes, int | float) or isinstance(minutes, bool):
        error(
            "invalid_ai_processing_minutes",
            f"Run {run.run_id} has non-numeric ai_processing_minutes",
            "runs.jsonl",
        )
        return
    if minutes < 0:
        error(
            "invalid_ai_processing_minutes",
            f"Run {run.run_id} has negative ai_processing_minutes",
            "runs.jsonl",
        )
        return
    if source != "synthetic_complexity_estimate":
        error(
            "invalid_ai_processing_minutes_source",
            f"Run {run.run_id} has invalid ai_processing_minutes_source",
            "runs.jsonl",
        )
    if evidence != "E0":
        error(
            "invalid_ai_processing_minutes_evidence_level",
            f"Run {run.run_id} has invalid ai_processing_minutes_evidence_level",
            "runs.jsonl",
        )
    if run.finished_at is None:
        error(
            "missing_finished_at",
            f"Run {run.run_id} with ai_processing_minutes must have finished_at",
            "runs.jsonl",
        )
        return
    actual = (run.finished_at - run.started_at).total_seconds() / 60
    if abs(actual - float(minutes)) > (1 / 60):
        error(
            "ai_processing_minutes_mismatch",
            f"Run {run.run_id} interval is {actual:.4f} minutes but "
            f"ai_processing_minutes is {minutes}",
            "runs.jsonl",
        )
