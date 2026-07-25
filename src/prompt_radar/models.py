"""Pydantic data-contract models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MessageRole = Literal["system", "user", "assistant", "tool"]
RunStatus = Literal[
    "pending", "running", "completed", "failed", "cancelled", "partial",
    "abandoned", "unknown"
]
EventStatus = Literal["pending", "running", "success", "failed", "cancelled", "unknown"]


class Record(BaseModel):
    """Base model that accepts forward-compatible optional fields."""

    model_config = ConfigDict(extra="allow")


class Manifest(Record):
    """Dataset manifest."""

    schema_version: str
    dataset_id: str = Field(min_length=1)
    created_at: datetime
    synthetic: bool = False
    seed: int | None = None

    @field_validator("schema_version")
    @classmethod
    def validate_version_format(cls, value: str) -> str:
        parts = value.split(".")
        if len(parts) != 2 or not all(part.isdigit() for part in parts):
            raise ValueError("schema_version must use MAJOR.MINOR")
        return value


class User(Record):
    """Corporate user record."""

    user_id: str = Field(min_length=1)
    display_name: str | None = None
    department: str | None = None
    role: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Conversation(Record):
    """Conversation owned by one user."""

    conversation_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    owner_user_id: str | None = None
    created_at: datetime
    title: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Run(Record):
    """Explicit business-task run."""

    run_id: str = Field(min_length=1)
    conversation_id: str = Field(min_length=1)
    user_id: str | None = None
    status: RunStatus
    started_at: datetime
    finished_at: datetime | None = None
    parent_run_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Message(Record):
    """OpenAI-style message linked to a conversation and optional run."""

    message_id: str = Field(min_length=1)
    conversation_id: str = Field(min_length=1)
    run_id: str | None = None
    sender_user_id: str | None = None
    role: MessageRole
    content: str
    sequence_number: int = Field(ge=0)
    created_at: datetime
    attachment_ids: list[str] = Field(default_factory=list)
    tool_call_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Event(Record):
    """Agent/tool event retained as run metadata."""

    event_id: str = Field(min_length=1)
    conversation_id: str = Field(min_length=1)
    run_id: str | None = None
    message_id: str | None = None
    event_type: str = Field(min_length=1)
    status: EventStatus
    sequence_number: int = Field(ge=0)
    created_at: datetime
    tool_name: str | None = None
    tool_call_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Attachment(Record):
    """Attachment metadata and safe relative location."""

    attachment_id: str = Field(min_length=1)
    message_id: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    path: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    sha256: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ValidationIssue(BaseModel):
    """One dataset validation issue."""

    severity: Literal["error", "warning"]
    code: str
    message: str
    file: str | None = None
    line: int | None = None


class ValidationReport(BaseModel):
    """Machine-readable dataset validation result."""

    valid: bool
    dataset_id: str | None = None
    schema_version: str | None = None
    record_counts: dict[str, int] = Field(default_factory=dict)
    issues: list[ValidationIssue] = Field(default_factory=list)
    skipped_records: int = 0


class DatasetBundle(BaseModel):
    """Validated in-memory relationship index for bounded metadata."""

    manifest: Manifest
    users: list[User]
    conversations: list[Conversation]
    runs: list[Run]
    messages: list[Message]
    events: list[Event]
    attachments: list[Attachment]
    cost_config: dict[str, Any]
    root: str
