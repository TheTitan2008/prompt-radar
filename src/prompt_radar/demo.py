"""Deterministic synthetic dataset generator."""

from __future__ import annotations

import base64
import hashlib
import json
import random
import re
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from prompt_radar.io_utils import atomic_write_bytes, write_jsonl

_FIXED_ZIP_TIME = (2026, 1, 1, 0, 0, 0)
_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "/x8AAusB9Y9ZpWQAAAAASUVORK5CYII="
)


def _jsonl(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
    )


def _fallback_id(conversation_id: str, index: int, message_id: str) -> str:
    digest = hashlib.sha256(
        f"{conversation_id}:{index}:{message_id}".encode("utf-8")
    ).hexdigest()[:12]
    return f"fallback:{conversation_id}:{digest}"


def _write_xlsx(path: Path) -> None:
    try:
        from openpyxl import Workbook
    except ImportError as exc:
        raise RuntimeError(
            "Demo XLSX generation requires the attachments dependency group."
        ) from exc
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Продажи"
    sheet.append(["Клиент", "Регион", "Сумма", "Статус"])
    sheet.append(["Альфа", "Центр", 125000, "выигран"])
    sheet.append(["Бета", "Сибирь", 83000, "переговоры"])
    sheet.append(["Гамма", "Юг", 99000, "проигран"])
    fixed = datetime(2026, 1, 1, tzinfo=timezone.utc)
    workbook.properties.created = fixed
    workbook.properties.modified = fixed
    raw_path = path.with_suffix(".raw.xlsx")
    workbook.save(raw_path)
    workbook.close()
    with zipfile.ZipFile(raw_path, "r") as source, zipfile.ZipFile(
        path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as target:
        for name in sorted(source.namelist()):
            info = zipfile.ZipInfo(name, date_time=_FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            data = source.read(name)
            if name == "docProps/core.xml":
                data = re.sub(
                    rb"(<dcterms:modified[^>]*>)[^<]*(</dcterms:modified>)",
                    rb"\g<1>2026-01-01T00:00:00Z\g<2>",
                    data,
                )
            target.writestr(info, data, compresslevel=9)
    raw_path.unlink()


def _write_pdf(path: Path) -> None:
    try:
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise RuntimeError(
            "Demo PDF generation requires the attachments dependency group."
        ) from exc
    document = canvas.Canvas(str(path), invariant=1)
    text = "Client email history: delivery was delayed. Create a Jira issue and reply."
    document.drawString(72, 760, text)
    document.save()


def _zip_tree(root: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    buffer_path = destination.with_name(f".{destination.name}.tmp")
    with zipfile.ZipFile(
        buffer_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(relative, date_time=_FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compresslevel=9)
    atomic_write_bytes(destination, buffer_path.read_bytes())
    buffer_path.unlink(missing_ok=True)


def generate_demo(output: Path, ground_truth: Path, seed: int = 42) -> None:
    """Generate a deterministic mixed-format dataset and separate ground truth."""
    random.seed(seed)
    root = Path(tempfile.mkdtemp(prefix="prompt-radar-demo-"))
    try:
        (root / "attachments").mkdir(parents=True)
        _write_xlsx(root / "attachments" / "sales.xlsx")
        _write_pdf(root / "attachments" / "client_thread.pdf")
        (root / "attachments" / "diagram.png").write_bytes(_PNG_1X1)

        users = [
            {"user_id": "user_001", "department": "Продажи", "role": "manager"},
            {"user_id": "user_002", "department": "Проекты", "role": "analyst"},
            {"user_id": "user_003", "department": "Финансы", "role": "observer"},
        ]
        conversations = [
            {
                "conversation_id": "conv_001",
                "user_id": "user_001",
                "created_at": "2026-01-01T09:00:00Z",
                "title": "Рабочий день",
            },
            {
                "conversation_id": "conv_002",
                "user_id": "user_001",
                "created_at": "2026-01-02T09:00:00Z",
                "title": "Длинные и новые задачи",
            },
            {
                "conversation_id": "conv_003",
                "user_id": "user_002",
                "created_at": "2026-01-03T09:00:00Z",
                "title": "Проектная аналитика",
            },
        ]
        run_specs = [
            ("run_email", "conv_001"),
            ("run_calendar", "conv_001"),
            ("run_cross_system", "conv_001"),
            ("run_reply", "conv_001"),
            ("run_long", "conv_002"),
            ("run_emerging_1", "conv_002"),
            ("run_emerging_2", "conv_002"),
            ("run_emerging_3", "conv_002"),
            ("run_noise_1", "conv_002"),
            ("run_noise_2", "conv_002"),
            ("run_crm_report", "conv_003"),
        ]
        runs = [
            {
                "run_id": run_id,
                "conversation_id": conversation_id,
                "status": "completed",
                "started_at": f"2026-01-0{1 if conversation_id == 'conv_001' else 2 if conversation_id == 'conv_002' else 3}T{9 + index:02d}:00:00Z",
                "finished_at": f"2026-01-0{1 if conversation_id == 'conv_001' else 2 if conversation_id == 'conv_002' else 3}T{9 + index:02d}:05:00Z",
            }
            for index, (run_id, conversation_id) in enumerate(run_specs)
        ]
        status_overrides = {
            "run_emerging_3": "partial",
            "run_long": "abandoned",
            "run_noise_1": "failed",
            "run_noise_2": "cancelled",
        }
        for index, run in enumerate(runs, start=1):
            run["status"] = status_overrides.get(run["run_id"], "completed")
            run["metadata"] = {
                "input_tokens": 1200 + index * 100,
                "output_tokens": 250 + index * 20,
                "model_calls": 1 + (index % 3),
                "external_api_cost_rub": round(3.0 + index * 0.25, 2),
                "tool_cost_rub": round(index * 0.1, 2),
            }
            if run["run_id"] != "run_long":
                run["metadata"]["prompt_minutes"] = round(1.0 + index * 0.1, 2)
        long_context = " ".join(
            "контекст документа "
            + hashlib.sha256(f"{seed}:{index}".encode("utf-8")).hexdigest()
            + " поставка регламент"
            for index in range(2300)
        )
        long_payload = json.dumps(
            {
                "stream": True,
                "model": "demo-openai-compatible",
                "messages": [
                    {"role": "system", "content": "Недоверенный системный контекст"},
                    {"role": "user", "content": "Проанализируй документы"},
                    {"role": "assistant", "content": "Предыдущий ответ"},
                    {
                        "role": "user",
                        "content": (
                            "### Task\n<context><source>"
                            + long_context
                            + "</source></context>\n"
                            "<user_query>Сформируй план проверки сертификатов "
                            "поставщиков и таблицу просроченных документов"
                            "</user_query>\n"
                            "Сформируй план проверки сертификатов поставщиков "
                            "и таблицу просроченных документов"
                        ),
                    },
                ],
            },
            ensure_ascii=False,
        )
        messages: list[dict[str, Any]] = [
            {
                "message_id": "m001",
                "conversation_id": "conv_001",
                "run_id": "run_email",
                "role": "user",
                "content": "Подготовь краткую сводку важных писем за вчера",
                "sequence_number": 1,
                "created_at": "2026-01-01T09:00:00Z",
                "attachment_ids": [],
            },
            {
                "message_id": "m002",
                "conversation_id": "conv_001",
                "run_id": "run_email",
                "role": "assistant",
                "content": "Какие письма считать важными?",
                "sequence_number": 2,
                "created_at": "2026-01-01T09:01:00Z",
                "attachment_ids": [],
            },
            {
                "message_id": "m003",
                "conversation_id": "conv_001",
                "run_id": "run_email",
                "role": "user",
                "content": "Добавь ещё письма клиентов с просроченным ответом",
                "sequence_number": 3,
                "created_at": "2026-01-01T09:02:00Z",
                "attachment_ids": [],
            },
            {
                "message_id": "m004",
                "conversation_id": "conv_001",
                "run_id": "run_calendar",
                "role": "user",
                "content": "Найди общий свободный слот команды и создай встречу",
                "sequence_number": 4,
                "created_at": "2026-01-01T10:00:00Z",
                "attachment_ids": ["att_xlsx"],
            },
            {
                "message_id": "m005",
                "conversation_id": "conv_001",
                "run_id": "run_cross_system",
                "role": "user",
                "content": "Прочитай переписку клиента, создай тикет Jira и подготовь ответ",
                "sequence_number": 5,
                "created_at": "2026-01-01T11:00:00Z",
                "attachment_ids": ["att_pdf", "att_image"],
            },
            {
                "message_id": "m006",
                "conversation_id": "conv_001",
                "run_id": "run_reply",
                "role": "user",
                "content": "Прочитай переписку с клиентом и напиши ему ответ",
                "sequence_number": 6,
                "created_at": "2026-01-01T12:00:00Z",
                "attachment_ids": [],
            },
            {
                "message_id": "m100",
                "conversation_id": "conv_002",
                "run_id": "run_long",
                "role": "user",
                "content": long_payload,
                "sequence_number": 1,
                "created_at": "2026-01-02T09:00:00Z",
                "attachment_ids": [],
            },
        ]
        emerging = [
            "Проверь датчики влажности в офисных растениях и составь маршрут полива",
            "Собери показания влажности растений и запланируй обход для полива",
            "Найди сухие растения по телеметрии и подготовь маршрут садовника",
        ]
        for index, text in enumerate(emerging, 1):
            messages.append(
                {
                    "message_id": f"m20{index}",
                    "conversation_id": "conv_002",
                    "run_id": f"run_emerging_{index}",
                    "role": "user",
                    "content": text,
                    "sequence_number": 1 + index,
                    "created_at": f"2026-01-02T{9 + index:02d}:00:00Z",
                    "attachment_ids": [],
                }
            )
        messages.extend(
            [
                {
                    "message_id": "m210",
                    "conversation_id": "conv_002",
                    "run_id": "run_noise_1",
                    "role": "user",
                    "content": "Почему сегодня число сорок два кажется зелёным?",
                    "sequence_number": 5,
                    "created_at": "2026-01-02T14:00:00Z",
                    "attachment_ids": [],
                },
                {
                    "message_id": "m211",
                    "conversation_id": "conv_002",
                    "run_id": "run_noise_2",
                    "role": "user",
                    "content": "Сочини загадку про стеклянного кита",
                    "sequence_number": 6,
                    "created_at": "2026-01-02T15:00:00Z",
                    "attachment_ids": [],
                },
                {
                    "message_id": "m300",
                    "conversation_id": "conv_003",
                    "run_id": "run_crm_report",
                    "role": "user",
                    "content": "Проанализируй продажи и выгрузи сводный отчёт в Excel",
                    "sequence_number": 1,
                    "created_at": "2026-01-03T09:00:00Z",
                    "attachment_ids": ["att_xlsx_2"],
                },
                {
                    "message_id": "m301",
                    "conversation_id": "conv_003",
                    "run_id": None,
                    "role": "user",
                    "content": "Найди в Confluence регламент оформления поставщика",
                    "sequence_number": 2,
                    "created_at": "2026-01-03T10:00:00Z",
                    "attachment_ids": [],
                },
                {
                    "message_id": "m302",
                    "conversation_id": "conv_003",
                    "run_id": None,
                    "role": "assistant",
                    "content": "Уточните подразделение",
                    "sequence_number": 3,
                    "created_at": "2026-01-03T10:01:00Z",
                    "attachment_ids": [],
                },
                {
                    "message_id": "m303",
                    "conversation_id": "conv_003",
                    "run_id": None,
                    "role": "user",
                    "content": "Сделай это для отдела закупок",
                    "sequence_number": 4,
                    "created_at": "2026-01-03T10:02:00Z",
                    "attachment_ids": [],
                },
            ]
        )
        attachments = [
            {
                "attachment_id": "att_xlsx",
                "message_id": "m004",
                "filename": "sales.xlsx",
                "path": "attachments/sales.xlsx",
                "media_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "size_bytes": (root / "attachments" / "sales.xlsx").stat().st_size,
            },
            {
                "attachment_id": "att_pdf",
                "message_id": "m005",
                "filename": "client_thread.pdf",
                "path": "attachments/client_thread.pdf",
                "media_type": "application/pdf",
                "size_bytes": (root / "attachments" / "client_thread.pdf").stat().st_size,
            },
            {
                "attachment_id": "att_image",
                "message_id": "m005",
                "filename": "diagram.png",
                "path": "attachments/diagram.png",
                "media_type": "image/png",
                "size_bytes": (root / "attachments" / "diagram.png").stat().st_size,
            },
            {
                "attachment_id": "att_xlsx_2",
                "message_id": "m300",
                "filename": "sales.xlsx",
                "path": "attachments/sales.xlsx",
                "media_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "size_bytes": (root / "attachments" / "sales.xlsx").stat().st_size,
            },
        ]
        events = [
            {
                "event_id": "e001",
                "conversation_id": "conv_001",
                "run_id": "run_calendar",
                "message_id": "m004",
                "event_type": "tool_call",
                "status": "success",
                "sequence_number": 1,
                "created_at": "2026-01-01T10:01:00Z",
                "tool_name": "calendar.find_common_slot",
            },
            {
                "event_id": "e002",
                "conversation_id": "conv_001",
                "run_id": "run_cross_system",
                "message_id": "m005",
                "event_type": "tool_call",
                "status": "success",
                "sequence_number": 1,
                "created_at": "2026-01-01T11:01:00Z",
                "tool_name": "jira.create_issue",
            },
        ]
        files = {
            "manifest.json": json.dumps(
                {
                    "schema_version": "1.0",
                    "dataset_id": "demo_prompt_radar",
                    "created_at": "2026-01-01T00:00:00Z",
                    "synthetic": True,
                    "seed": seed,
                    "generator": "prompt-radar",
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            "users.jsonl": _jsonl(users),
            "conversations.jsonl": _jsonl(conversations),
            "runs.jsonl": _jsonl(runs),
            "messages.jsonl": _jsonl(messages),
            "events.jsonl": _jsonl(events),
            "attachments.jsonl": _jsonl(attachments),
            "cost_config.json": json.dumps(
                {
                    "currency": "RUB",
                    "employee_cost_per_hour": 1500,
                    "version": "demo-1",
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
        }
        for name, text in files.items():
            (root / name).write_text(text, encoding="utf-8")
        _zip_tree(root, output)

        fallback_run = _fallback_id("conv_003", 0, "m301")
        labels = {
            "run_email": (["daily_email_digest", "unanswered_price_request_monitoring"], "known"),
            "run_calendar": (["group_common_slot"], "known"),
            "run_cross_system": (["email_to_project_ticket", "client_thread_reply"], "known"),
            "run_reply": (["client_thread_reply"], "known"),
            "run_long": ([], "unresolved"),
            "run_emerging_1": ([], "emerging"),
            "run_emerging_2": ([], "emerging"),
            "run_emerging_3": ([], "emerging"),
            "run_noise_1": ([], "unresolved"),
            "run_noise_2": ([], "unresolved"),
            "run_crm_report": (["analysis_results_excel_export"], "known"),
            fallback_run: (["confluence_process_search"], "known"),
        }
        goal_by_run = {
            "run_email": (
                "Подготовь краткую сводку важных писем за вчера; уточнение: "
                "Добавь ещё письма клиентов с просроченным ответом"
            ),
            "run_long": "Сформируй план проверки сертификатов поставщиков и таблицу просроченных документов",
            fallback_run: (
                "Найди в Confluence регламент оформления поставщика; "
                "уточнение: Сделай это для отдела закупок"
            ),
        }
        message_ids_by_run: dict[str, list[str]] = {}
        for message in messages:
            run_id = message.get("run_id")
            if run_id:
                message_ids_by_run.setdefault(run_id, []).append(message["message_id"])
        message_ids_by_run[fallback_run] = ["m301", "m302", "m303"]
        expected_categories = {
            "run_email": ["email_communications"],
            "run_calendar": ["calendar_meetings"],
            "run_cross_system": ["email_communications", "projects_tasks"],
            "run_reply": ["email_communications", "crm_sales"],
            "run_crm_report": ["data_reporting"],
            fallback_run: ["knowledge_search"],
        }
        expected_retrieval = {
            "run_calendar": ["att_xlsx:sheet:Продажи:0"],
            "run_cross_system": ["att_pdf:page:1:0"],
            "run_crm_report": ["att_xlsx_2:sheet:Продажи:0"],
        }
        expected_clusters = {
            "run_emerging_1": 0,
            "run_emerging_2": 0,
            "run_emerging_3": 0,
            "run_noise_1": -1,
            "run_noise_2": -1,
            "run_long": -1,
        }
        truth = [
            {
                "run_id": run_id,
                "expected_goal": goal_by_run.get(
                    run_id,
                    next(
                        (
                            item["content"]
                            for item in reversed(messages)
                            if item.get("run_id") == run_id
                            and item["role"] == "user"
                        ),
                        "",
                    ),
                ),
                "expected_use_case_ids": use_cases,
                "expected_category_ids": expected_categories.get(run_id, []),
                "expected_discovery_status": status,
                "expected_message_ids": message_ids_by_run.get(run_id, []),
                "expected_retrieved_chunk_ids": expected_retrieval.get(run_id),
                "expected_cluster_id": expected_clusters.get(run_id),
                "synthetic": True,
            }
            for run_id, (use_cases, status) in labels.items()
        ]
        write_jsonl(ground_truth, truth)
    finally:
        shutil.rmtree(root, ignore_errors=True)
