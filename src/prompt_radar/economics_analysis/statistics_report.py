"""Self-contained management statistics report."""

from __future__ import annotations

import html
from collections import Counter
from datetime import datetime, timezone
from typing import Any


def _number(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0


def _request_type(row: dict[str, Any], ledger: dict[str, Any]) -> str:
    if ledger.get("target_name"):
        return str(ledger["target_name"])
    matches = row.get("known_use_case_matches") or []
    accepted = [item for item in matches if item.get("accepted")]
    if accepted:
        return str(accepted[0].get("name") or accepted[0].get("id"))
    if row.get("cluster_name"):
        return str(row["cluster_name"])
    category = row.get("primary_category") or {}
    if category.get("name"):
        return f"Без паспорта · {category['name']}"
    return "Неразрешённые и шумовые запросы"


def _user_name(row: dict[str, Any]) -> str:
    return str(row.get("user_display_name") or row.get("user_id") or "Неизвестный")


def _counter_rows(counter: Counter[str]) -> list[dict[str, Any]]:
    return [
        {"name": name, "count": count}
        for name, count in sorted(
            counter.items(), key=lambda pair: (-pair[1], pair[0])
        )
    ]


def _token_total(item: dict[str, Any]) -> float:
    telemetry = item.get("telemetry") or {}
    total = telemetry.get("total_tokens")
    if isinstance(total, (int, float)):
        return float(total)
    return float(telemetry.get("input_tokens") or 0) + float(
        telemetry.get("output_tokens") or 0
    )


def build_statistics_summary(
    *,
    rows: list[dict[str, Any]],
    ledger: list[dict[str, Any]],
    platform: dict[str, Any],
) -> dict[str, Any]:
    """Aggregate exact platform and per-person statistics."""
    row_by_run = {str(row["run_id"]): row for row in rows}
    ledger_by_run = {str(item["run_id"]): item for item in ledger}
    request_types: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    modes: Counter[str] = Counter()
    discovery: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    fte_view = platform.get("fte_view") or {}
    fte_month_minutes = (
        _number(fte_view.get("working_days_per_month"))
        * _number(fte_view.get("working_hours_per_day"))
        * 60
    ) or (20 * 8 * 60)
    users: dict[str, dict[str, Any]] = {}

    for run_id, row in row_by_run.items():
        item = ledger_by_run[run_id]
        user_id = str(row.get("user_id") or item.get("user_id") or "unknown")
        user = users.setdefault(
            user_id,
            {
                "user_id": user_id,
                "display_name": _user_name(row),
                "department": row.get("user_department"),
                "role": row.get("user_role"),
                "run_count": 0,
                "conversation_ids": set(),
                "ai_processing_minutes": 0.0,
                "total_tokens": 0.0,
                "potential_saved_minutes": 0.0,
                "potential_gross_value": 0.0,
                "allocated_platform_cost": 0.0,
                "potential_covered_runs": 0,
                "actual_saved_minutes": 0.0,
                "actual_gross_value": 0.0,
                "actual_cost": 0.0,
                "actual_evaluated_runs": 0,
                "status_counts": Counter(),
                "request_types": Counter(),
                "tasks": [],
            },
        )
        request_type = _request_type(row, item)
        status = str(item.get("run_status") or "unknown")
        mode = str(row.get("processing_mode") or "unknown")
        discovery_status = str(row.get("discovery_status") or "unknown")
        primary_category = (row.get("primary_category") or {}).get("name")
        ai_minutes = _number(item.get("ai_wall_minutes"))
        total_tokens = _token_total(item)
        cost = _number(item.get("fully_loaded_cost"))
        potential = (item.get("potential") or {}).get("base")
        actual = item.get("actual")

        request_types[request_type] += 1
        statuses[status] += 1
        modes[mode] += 1
        discovery[discovery_status] += 1
        if primary_category:
            categories[str(primary_category)] += 1

        user["run_count"] += 1
        user["conversation_ids"].add(str(row.get("conversation_id") or ""))
        user["ai_processing_minutes"] += ai_minutes
        user["total_tokens"] += total_tokens
        user["allocated_platform_cost"] += cost
        user["status_counts"][status] += 1
        user["request_types"][request_type] += 1
        if potential:
            user["potential_covered_runs"] += 1
            user["potential_saved_minutes"] += _number(
                potential.get("saved_minutes")
            )
            user["potential_gross_value"] += _number(
                potential.get("labor_value")
            )
        if actual:
            user["actual_evaluated_runs"] += 1
            user["actual_saved_minutes"] += _number(
                actual.get("saved_minutes")
            )
            user["actual_gross_value"] += _number(actual.get("labor_value"))
            user["actual_cost"] += cost
        goal_preview = str(row.get("current_goal") or "")
        if len(goal_preview) > 500:
            goal_preview = goal_preview[:497] + "…"
        user["tasks"].append(
            {
                "run_id": run_id,
                "conversation_id": row.get("conversation_id"),
                "request_type": request_type,
                "status": status,
                "processing_mode": mode,
                "ai_processing_minutes": round(ai_minutes, 4),
                "total_tokens": int(total_tokens),
                "potential_saved_minutes": (
                    round(_number(potential.get("saved_minutes")), 4)
                    if potential
                    else None
                ),
                "actual_saved_minutes": (
                    round(_number(actual.get("saved_minutes")), 4)
                    if actual
                    else None
                ),
                "goal": goal_preview,
            }
        )

    people: list[dict[str, Any]] = []
    for user in users.values():
        run_count = int(user["run_count"])
        potential_gross = float(user["potential_gross_value"])
        allocated_cost = float(user["allocated_platform_cost"])
        actual_gross = float(user["actual_gross_value"])
        actual_cost = float(user["actual_cost"])
        total_tokens = float(user["total_tokens"])
        people.append(
            {
                "user_id": user["user_id"],
                "display_name": user["display_name"],
                "department": user["department"],
                "role": user["role"],
                "run_count": run_count,
                "conversation_count": len(user["conversation_ids"] - {""}),
                "ai_processing_minutes": round(
                    user["ai_processing_minutes"], 4
                ),
                "total_tokens": int(round(total_tokens)),
                "average_tokens_per_run": round(total_tokens / run_count, 2),
                "average_ai_processing_minutes": round(
                    user["ai_processing_minutes"] / run_count, 4
                ),
                "potential_covered_runs": user["potential_covered_runs"],
                "potential_coverage": round(
                    user["potential_covered_runs"] / run_count, 6
                ),
                "potential_saved_minutes": round(
                    user["potential_saved_minutes"], 4
                ),
                "saved_fte_months": round(
                    user["potential_saved_minutes"] / fte_month_minutes, 6
                ),
                "potential_gross_value": round(potential_gross, 2),
                "allocated_platform_cost": round(allocated_cost, 2),
                "allocated_cost_per_1k_tokens_rub": (
                    round(allocated_cost * 1000 / total_tokens, 6)
                    if total_tokens > 0
                    else None
                ),
                "potential_net_value": round(
                    potential_gross - allocated_cost, 2
                ),
                "actual_evaluated_runs": user["actual_evaluated_runs"],
                "actual_saved_minutes": round(
                    user["actual_saved_minutes"], 4
                ),
                "actual_gross_value": round(actual_gross, 2),
                "actual_cost": round(actual_cost, 2),
                "actual_net_value": (
                    round(actual_gross - actual_cost, 2)
                    if user["actual_evaluated_runs"]
                    else None
                ),
                "status_counts": dict(user["status_counts"]),
                "request_types": _counter_rows(user["request_types"]),
                "tasks": sorted(
                    user["tasks"], key=lambda task: str(task["run_id"])
                ),
            }
        )
    people.sort(key=lambda item: (-item["run_count"], item["display_name"]))

    potential_base = (platform.get("potential") or {}).get("base") or {}
    token_economics = platform.get("token_economics") or {}
    actual_people = sum(person["actual_evaluated_runs"] > 0 for person in people)
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "basis": {
            "potential_is_q1_scenario": True,
            "actual_quality_available": actual_people > 0,
            "prompt_effort_assumed_runs": sum(
                (item.get("provenance") or {}).get("prompt_minutes")
                == "cost_config.default_prompt_minutes"
                for item in ledger
            ),
            "gpu_allocation_method": platform.get("gpu_allocation_method"),
            "analysis_period_months": platform.get("analysis_period_months"),
        },
        "totals": {
            "runs": len(rows),
            "users": len(people),
            "conversations": len(
                {
                    str(row.get("conversation_id"))
                    for row in rows
                    if row.get("conversation_id")
                }
            ),
            "request_types": len(request_types),
            "ai_processing_minutes": round(
                sum(_number(item.get("ai_wall_minutes")) for item in ledger),
                4,
            ),
            "total_tokens": int(round(sum(_token_total(item) for item in ledger))),
            "full_cost_per_1k_tokens_rub": token_economics.get(
                "full_cost_per_1k_tokens_rub"
            ),
            "saved_fte_months": (platform.get("fte_view") or {}).get(
                "base_saved_fte_months"
            ),
            "saved_value_rub_by_fte_month": (platform.get("fte_view") or {}).get(
                "base_saved_value_rub_by_fte_month"
            ),
            "b_gt_a": (platform.get("fte_view") or {}).get("b_gt_a"),
            "potential_saved_minutes": potential_base.get("saved_minutes"),
            "potential_gross_value": potential_base.get("labor_value"),
            "fully_loaded_platform_period_cost": platform.get(
                "fully_loaded_platform_period_cost"
            ),
            "potential_net_value": potential_base.get("net_value"),
            "potential_roi": potential_base.get("roi"),
            "insufficient_evidence_runs": platform.get("insufficient_evidence_runs"),
            "insufficient_evidence_cost": platform.get("insufficient_evidence_cost"),
            "insufficient_evidence_share": platform.get("insufficient_evidence_share"),
            "actual_evaluated_runs": sum(
                person["actual_evaluated_runs"] for person in people
            ),
        },
        "request_types": _counter_rows(request_types),
        "statuses": _counter_rows(statuses),
        "processing_modes": _counter_rows(modes),
        "discovery_statuses": _counter_rows(discovery),
        "categories": _counter_rows(categories),
        "users": people,
    }


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _fmt(value: Any, digits: int = 1) -> str:
    if value is None:
        return "н/д"
    return f"{float(value):,.{digits}f}".replace(",", " ").replace(".", ",")


def _bars(
    items: list[dict[str, Any]], *, total: int, limit: int = 15
) -> str:
    maximum = max((int(item["count"]) for item in items), default=1)
    rows = []
    for item in items[:limit]:
        width = 100 * int(item["count"]) / maximum
        share = 100 * int(item["count"]) / total if total else 0
        rows.append(
            "<div class='bar-row'>"
            f"<div class='bar-label' title='{_esc(item['name'])}'>{_esc(item['name'])}</div>"
            "<div class='bar-track'>"
            f"<span style='width:{width:.2f}%'></span></div>"
            f"<div class='bar-value'>{item['count']} · {share:.1f}%</div>"
            "</div>"
        )
    return "".join(rows)


def build_statistics_html(summary: dict[str, Any]) -> str:
    """Render one portable HTML file with no external dependencies."""
    totals = summary["totals"]
    users = summary["users"]
    basis = summary["basis"]
    user_sections: list[str] = []
    for person in users:
        top_types = ", ".join(
            f"{item['name']} ({item['count']})"
            for item in person["request_types"][:5]
        )
        task_rows = []
        for task in person["tasks"]:
            goal = task["goal"]
            if len(goal) > 260:
                goal = goal[:257] + "…"
            task_rows.append(
                "<tr>"
                f"<td><code>{_esc(task['run_id'])}</code></td>"
                f"<td>{_esc(task['request_type'])}</td>"
                f"<td><span class='status'>{_esc(task['status'])}</span></td>"
                f"<td>{_esc(task['processing_mode'])}</td>"
                f"<td class='num'>{_fmt(task['ai_processing_minutes'])}</td>"
                f"<td class='num'>{_fmt(task.get('total_tokens'), 0)}</td>"
                f"<td class='num'>{_fmt(task['potential_saved_minutes'])}</td>"
                f"<td>{_esc(goal)}</td>"
                "</tr>"
            )
        net_class = (
            "positive" if person["potential_net_value"] >= 0 else "negative"
        )
        actual_text = (
            f"{_fmt(person['actual_net_value'], 2)} ₽"
            if person["actual_net_value"] is not None
            else "нет quality-разметки"
        )
        search = " ".join(
            [
                person["display_name"],
                person["user_id"],
                str(person.get("department") or ""),
                top_types,
            ]
        ).casefold()
        user_sections.append(
            f"""
            <details class="person" data-search="{_esc(search)}">
              <summary>
                <div>
                  <strong>{_esc(person['display_name'])}</strong>
                  <span>{_esc(person['department'] or 'Подразделение не указано')} ·
                    {person['run_count']} запросов · {person['conversation_count']} чатов</span>
                </div>
                <div class="summary-metrics">
                  <span>{_fmt(person['ai_processing_minutes'])} мин ИИ</span>
                  <span>{_fmt(person.get('total_tokens'),0)} tok</span>
                  <span>{_fmt(person['potential_saved_minutes'])} мин потенциально</span>
                  <span class="{net_class}">{_fmt(person['potential_net_value'], 2)} ₽ net</span>
                </div>
              </summary>
              <div class="person-body">
                <div class="mini-grid">
                  <div><small>Среднее время ИИ</small><b>{_fmt(person['average_ai_processing_minutes'])} мин</b></div>
                  <div><small>Токены</small><b>{_fmt(person.get('total_tokens'),0)}</b></div>
                  <div><small>Средние токены / run</small><b>{_fmt(person.get('average_tokens_per_run'),0)}</b></div>
                  <div><small>Покрытие паспортами</small><b>{person['potential_covered_runs']}/{person['run_count']} ({person['potential_coverage']:.1%})</b></div>
                  <div><small>Валовая ценность времени</small><b>{_fmt(person['potential_gross_value'], 2)} ₽</b></div>
                  <div><small>Выделенная стоимость</small><b>{_fmt(person['allocated_platform_cost'], 2)} ₽</b></div>
                  <div><small>Стоимость 1000 токенов</small><b>{_fmt(person.get('allocated_cost_per_1k_tokens_rub'), 4)} ₽</b></div>
                  <div><small>FTE-месяцы</small><b>{_fmt(person.get('saved_fte_months'), 3)}</b></div>
                  <div><small>Потенциальный чистый эффект</small><b class="{net_class}">{_fmt(person['potential_net_value'], 2)} ₽</b></div>
                  <div><small>Фактический чистый эффект</small><b>{actual_text}</b></div>
                </div>
                <p class="task-types"><b>Основные задачи:</b> {_esc(top_types or 'нет классификации')}</p>
                <div class="table-wrap">
                  <table>
                    <thead><tr><th>Run</th><th>Тип задачи</th><th>Статус</th><th>Режим</th><th>Минут ИИ</th><th>Токены</th><th>Потенц. экономия, мин</th><th>Цель</th></tr></thead>
                    <tbody>{''.join(task_rows)}</tbody>
                  </table>
                </div>
              </div>
            </details>
            """
        )

    warning = (
        f"Время написания промпта предположено для "
        f"{basis['prompt_effort_assumed_runs']} запусков. "
        "Potential — это сценарная оценка q=1, а не доказанная экономия."
    )
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Prompt Radar · статистика</title>
<style>
:root{{--bg:#07111f;--panel:#0e1b2d;--panel2:#13243a;--line:#243a55;--text:#edf5ff;--muted:#94a9c3;--cyan:#42d9e8;--blue:#5b8cff;--green:#56d68b;--red:#ff7085;--amber:#ffc766}}
*{{box-sizing:border-box}} body{{margin:0;background:radial-gradient(circle at 15% 0,#17345a 0,transparent 36%),var(--bg);color:var(--text);font:14px/1.45 Inter,Segoe UI,Arial,sans-serif}}
.shell{{max-width:1500px;margin:auto;padding:34px}} h1{{font-size:38px;margin:0 0 6px;letter-spacing:-1.2px}} h2{{margin:34px 0 14px;font-size:22px}} .subtitle,.muted{{color:var(--muted)}}
.badge{{display:inline-flex;padding:6px 10px;border:1px solid #2b5774;background:#0c2940;border-radius:999px;color:var(--cyan);font-weight:700;letter-spacing:.4px}}
.notice{{margin:22px 0;padding:15px 18px;border:1px solid #725a24;background:#2b2415;border-radius:14px;color:#ffe0a0}}
.cards{{display:grid;grid-template-columns:repeat(6,minmax(150px,1fr));gap:12px;margin-top:24px}} .card,.panel{{background:linear-gradient(145deg,var(--panel2),var(--panel));border:1px solid var(--line);box-shadow:0 12px 35px #0004;border-radius:17px}}
.card{{padding:18px}} .card small,.mini-grid small{{display:block;color:var(--muted);margin-bottom:7px}} .card b{{font-size:25px;letter-spacing:-.5px}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:16px}} .panel{{padding:20px;min-width:0}} .panel h3{{margin:0 0 16px}}
.bar-row{{display:grid;grid-template-columns:minmax(130px,2fr) 3fr 82px;gap:10px;align-items:center;margin:9px 0}} .bar-label{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#cfdef0}} .bar-track{{height:9px;background:#081321;border-radius:9px;overflow:hidden}} .bar-track span{{display:block;height:100%;background:linear-gradient(90deg,var(--blue),var(--cyan));border-radius:9px}} .bar-value{{text-align:right;color:var(--muted);font-variant-numeric:tabular-nums}}
.toolbar{{display:flex;gap:10px;margin:14px 0}} input,button{{background:#0b1727;color:var(--text);border:1px solid var(--line);border-radius:11px;padding:10px 13px}} input{{flex:1}} button{{cursor:pointer}} button:hover{{border-color:var(--cyan)}}
.person{{border:1px solid var(--line);background:#0d1929;border-radius:14px;margin:10px 0;overflow:hidden}} .person[open]{{border-color:#376081}} summary{{cursor:pointer;list-style:none;padding:16px 18px;display:flex;align-items:center;justify-content:space-between;gap:20px}} summary::-webkit-details-marker{{display:none}} summary strong{{font-size:17px}} summary span{{display:block;color:var(--muted);margin-top:3px}} .summary-metrics{{display:flex;gap:18px;text-align:right;white-space:nowrap}} .summary-metrics span{{color:#c9d8e9}}
.person-body{{padding:0 18px 18px;border-top:1px solid var(--line)}} .mini-grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin:16px 0}} .mini-grid>div{{padding:13px;background:#091422;border-radius:11px}} .mini-grid b{{font-size:16px}} .positive{{color:var(--green)!important}} .negative{{color:var(--red)!important}} .task-types{{color:#c9d8e9}}
.table-wrap{{overflow:auto;max-height:480px;border:1px solid var(--line);border-radius:10px}} table{{border-collapse:collapse;width:100%;min-width:1150px;background:#091422}} th{{position:sticky;top:0;background:#13243a;color:#a9bdd4;text-align:left;z-index:1}} th,td{{padding:10px 11px;border-bottom:1px solid #1d3047;vertical-align:top}} tr:hover td{{background:#102037}} td.num{{text-align:right;font-variant-numeric:tabular-nums}} code{{color:var(--cyan)}} .status{{padding:3px 7px;border-radius:7px;background:#172a41}}
.foot{{margin:32px 0;color:var(--muted);border-top:1px solid var(--line);padding-top:18px}}
@media(max-width:1100px){{.cards{{grid-template-columns:repeat(3,1fr)}}.grid2{{grid-template-columns:1fr}}.mini-grid{{grid-template-columns:repeat(2,1fr)}}.summary-metrics{{display:none}}}}
@media(max-width:650px){{.shell{{padding:20px}}h1{{font-size:30px}}.cards{{grid-template-columns:1fr 1fr}}.mini-grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body><main class="shell">
<span class="badge">PROMPT RADAR · OFFLINE REPORT</span>
<h1>Статистика использования ИИ</h1>
<p class="subtitle">Запросы, токены, время, типы задач и экономический эффект по каждому сотруднику.</p>
<div class="notice">{_esc(warning)}</div>
<section class="cards">
  <div class="card"><small>Всего запросов</small><b>{totals['runs']}</b></div>
  <div class="card"><small>Пользователей</small><b>{totals['users']}</b></div>
  <div class="card"><small>Чатов</small><b>{totals['conversations']}</b></div>
  <div class="card"><small>Время работы ИИ</small><b>{_fmt(totals['ai_processing_minutes']/60)} ч</b></div>
  <div class="card"><small>Потенциально сохранено</small><b>{_fmt(totals['potential_saved_minutes']/60 if totals['potential_saved_minutes'] is not None else None)} ч</b></div>
  <div class="card"><small>Potential ROI BASE</small><b class="{'positive' if _number(totals['potential_roi']) >= 0 else 'negative'}">{_fmt(totals['potential_roi'],3)}</b></div>
</section>
<section class="cards">
  <div class="card"><small>Всего токенов</small><b>{_fmt(totals.get('total_tokens'),0)}</b></div>
  <div class="card"><small>Полная стоимость 1000 токенов</small><b>{_fmt(totals.get('full_cost_per_1k_tokens_rub'),4)} ₽</b></div>
  <div class="card"><small>Сохранено FTE-месяцев</small><b>{_fmt(totals.get('saved_fte_months'),3)}</b></div>
  <div class="card"><small>Ценность по 400k/FTE-мес</small><b>{_fmt(totals.get('saved_value_rub_by_fte_month'),0)} ₽</b></div>
  <div class="card"><small>B &gt; A</small><b class="{'positive' if totals.get('b_gt_a') else 'negative'}">{'да' if totals.get('b_gt_a') else 'нет'}</b></div>
  <div class="card"><small>Типов запросов</small><b>{totals.get('request_types', len(summary.get('request_types', [])))}</b></div>
</section>
<h2>Общая структура</h2>
<section class="grid2">
  <div class="panel"><h3>Типы запросов</h3>{_bars(summary['request_types'], total=totals['runs'])}</div>
  <div class="panel"><h3>Статусы выполнения</h3>{_bars(summary['statuses'], total=totals['runs'])}</div>
  <div class="panel"><h3>Режим обработки</h3>{_bars(summary['processing_modes'], total=totals['runs'])}</div>
  <div class="panel"><h3>Категории</h3>{_bars(summary['categories'], total=totals['runs'])}</div>
</section>
<h2>Экономическая картина</h2>
<section class="cards">
  <div class="card"><small>Валовая ценность времени</small><b>{_fmt(totals['potential_gross_value'],0)} ₽</b></div>
  <div class="card"><small>Стоимость платформы за период</small><b>{_fmt(totals['fully_loaded_platform_period_cost'],0)} ₽</b></div>
  <div class="card"><small>Потенциальный net value</small><b class="{'positive' if _number(totals['potential_net_value']) >= 0 else 'negative'}">{_fmt(totals['potential_net_value'],0)} ₽</b></div>
  <div class="card"><small>Actual оценённых запусков</small><b>{totals['actual_evaluated_runs']}</b></div>
  <div class="card"><small>Недостаточно evidence</small><b>{_fmt(totals.get('insufficient_evidence_runs'),0)}</b></div>
  <div class="card"><small>Стоимость без evidence</small><b>{_fmt(totals.get('insufficient_evidence_cost'),0)} ₽</b></div>
</section>
<h2>Статистика сотрудников</h2>
<div class="toolbar"><input id="personSearch" placeholder="Найти сотрудника, подразделение или тип задачи…"><button id="openAll">Раскрыть всех</button><button id="closeAll">Свернуть</button></div>
<section id="people">{''.join(user_sections)}</section>
<p class="foot">Персональный potential net = валовая ценность потенциально сохранённого времени минус выделенная стоимость запусков сотрудника. Неактивные лицензии остаются на уровне платформы. Показатель B &gt; A сравнивает ценность сохранённых FTE-месяцев против полной стоимости платформы за период.</p>
</main>
<script>
const people=[...document.querySelectorAll('.person')];
document.getElementById('personSearch').addEventListener('input',e=>{{
 const q=e.target.value.toLocaleLowerCase('ru');
 people.forEach(p=>p.hidden=!p.dataset.search.includes(q));
}});
document.getElementById('openAll').onclick=()=>people.filter(p=>!p.hidden).forEach(p=>p.open=true);
document.getElementById('closeAll').onclick=()=>people.forEach(p=>p.open=false);
</script>
</body></html>"""
