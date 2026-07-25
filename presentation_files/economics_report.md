# Prompt Radar economics report

> Qwen/DeepSeek estimates are E0 hypotheses. They do not prove savings until the output is checked and the manual baseline is validated.

## Executive summary

- Runs: 800
- Analysis period: 0.203657407407407 months
- Selected cost scenario: `active_user_share`
- GPU allocation: `token_proxy` (proxy)
- Allocated fully loaded cost: 85988.60 RUB
- Idle license cost: 0.08 RUB
- Potential BASE saved minutes: 4087.9705
- Potential BASE net value: 16210.38 RUB
- Potential BASE ROI: 0.188518
- Insufficient evidence runs: 412
- Insufficient evidence cost: 67425.11 RUB
- Insufficient evidence share: 0.515
- Total tokens: 6893149
- Full cost per 1k tokens: 12.474513 RUB
- Saved FTE-months (BASE): 0.42583
- FTE-month value (BASE): 170332.1 RUB
- B > A by FTE view: True
- Confirmed wasted cost: 0.00 RUB
- Optimization opportunity: 55272.72 RUB

## Data completeness

| Evidence | Runs | Coverage |
|---|---:|---:|
| Prompt effort available (`prompt_minutes`) | 800/800 | 100.0% |
| Prompt effort measured | 0/800 | 0.0% |
| Prompt effort assumed by cost config | 800/800 | 100.0% |
| Manual baseline / economic passport | 388/800 | 48.5% |
| Potential calculation available | 388/800 | 48.5% |
| Quality evaluated | 0/800 | 0.0% |
| Actual calculation available | 0/800 | 0.0% |

> **Prompt effort is assumed for 800 runs, not measured.** Potential ROI is a sensitivity scenario and must not be presented as an observed result.

Most frequent missing evidence:
- `economic_passport`: 412 runs

Manual baseline evidence sources:
- `MODEL_ESTIMATE`: 388 runs

## Cost scenarios

| Scenario | Annual cost | Monthly cost | Break-even min/user/day |
|---|---:|---:|---:|
| `conservative_full_gpu` | 22400000.00 | 1866666.67 | 186.67 |
| `platform_token_ratio` | 19066666.67 | 1588888.89 | 158.89 |
| `weighted_users` | 3828571.43 | 319047.62 | 31.90 |
| `active_user_share` | 5066666.67 | 422222.22 | 42.22 |

## Platform cost structure

- Annual GPU amortization: 2666666.67 RUB
- Annual licenses: 2400000.0 RUB
- Annual electricity: 0.0 RUB
- Annual support: 0.0 RUB
- Annual development: 0.0 RUB
- Annual shared tools: 0.0 RUB

## Use-case and cluster evidence

| Target | Runs | Evaluated | Coverage | Potential ROI BASE | ROI interval | q break-even BASE | Passport | Status |
|---|---:|---:|---:|---:|---:|---:|---|---|
| Поиск контактных лиц клиента | 91 | 0 | 0.00% | -3.300445 | n/a … n/a | 0.424796 | `accepted` | `POTENTIALLY_INEFFECTIVE` |
| Выгрузка выбранных данных в Excel | 36 | 0 | 0.00% | -2.921284 | n/a … n/a | 0.542728 | `accepted` | `POTENTIALLY_INEFFECTIVE` |
| Создание и обновление тикета ИСУП | 29 | 0 | 0.00% | 5.79017 | n/a … n/a | 0.524739 | `accepted` | `POTENTIALLY_EFFECTIVE` |
| Подготовка ежедневной сводки почты | 26 | 0 | 0.00% | 19.33779 | n/a … n/a | 0.286355 | `accepted` | `POTENTIALLY_EFFECTIVE` |
| Формирование Excel-отчёта по клиенту | 22 | 0 | 0.00% | 24.982726 | n/a … n/a | 0.363505 | `accepted` | `POTENTIALLY_EFFECTIVE` |
| Поиск корпоративного процесса в Confluence | 21 | 0 | 0.00% | 8.65663 | n/a … n/a | 0.440845 | `accepted` | `POTENTIALLY_EFFECTIVE` |
| Ведение истории личных задач | 20 | 0 | 0.00% | 3.438914 | n/a … n/a | 0.588428 | `accepted` | `POTENTIALLY_EFFECTIVE` |
| Подготовка заметки о сотруднике | 20 | 0 | 0.00% | 2.90743 | n/a … n/a | 0.613899 | `accepted` | `POTENTIALLY_EFFECTIVE` |
| Подготовка ответа клиенту по переписке | 20 | 0 | 0.00% | 1.352881 | n/a … n/a | 0.405381 | `accepted` | `POTENTIALLY_EFFECTIVE` |
| Поиск слота руководителя и создание встречи | 20 | 0 | 0.00% | 0.967992 | n/a … n/a | 0.442706 | `accepted` | `POTENTIALLY_EFFECTIVE` |
| Сбор данных по группе компаний клиента | 16 | 0 | 0.00% | 35.79703 | n/a … n/a | 0.251913 | `accepted` | `POTENTIALLY_EFFECTIVE` |
| Создание напоминаний по договорённостям | 11 | 0 | 0.00% | 13.08669 | n/a … n/a | 0.295811 | `accepted` | `POTENTIALLY_EFFECTIVE` |
| Поиск общего календарного слота группы | 7 | 0 | 0.00% | 8.296671 | n/a … n/a | 0.433377 | `accepted` | `POTENTIALLY_EFFECTIVE` |
| Извлечение сведений из описания встречи | 6 | 0 | 0.00% | 1.40011 | n/a … n/a | 0.731551 | `accepted` | `POTENTIALLY_EFFECTIVE` |
| Контроль изменений статусов проектов ИСУП | 6 | 0 | 0.00% | 6.166398 | n/a … n/a | 0.480531 | `accepted` | `POTENTIALLY_EFFECTIVE` |
| Проверка и подтверждение выполнения задач | 6 | 0 | 0.00% | 1.011557 | n/a … n/a | 0.577163 | `accepted` | `POTENTIALLY_EFFECTIVE` |
| Создание проектного тикета из письма | 6 | 0 | 0.00% | 5.68105 | n/a … n/a | 0.541847 | `accepted` | `POTENTIALLY_EFFECTIVE` |
| Оформление итогов обсуждения | 5 | 0 | 0.00% | 9.727452 | n/a … n/a | 0.432851 | `accepted` | `POTENTIALLY_EFFECTIVE` |
| Фиксация наблюдений о сотруднике | 5 | 0 | 0.00% | 11.946933 | n/a … n/a | 0.492108 | `accepted` | `POTENTIALLY_EFFECTIVE` |
| Поиск публикаций о поставщике | 4 | 0 | 0.00% | 17.853036 | n/a … n/a | 0.370043 | `accepted` | `POTENTIALLY_EFFECTIVE` |
| Экспорт аналитических результатов в Excel | 4 | 0 | 0.00% | 10.137015 | n/a … n/a | 0.510226 | `accepted` | `POTENTIALLY_EFFECTIVE` |
| Поиск и бронирование переговорной | 2 | 0 | 0.00% | 5.904356 | n/a … n/a | 0.51478 | `accepted` | `POTENTIALLY_EFFECTIVE` |
| Поиск команды проекта и владельца вендора | 2 | 0 | 0.00% | 34.576391 | n/a … n/a | 0.31314 | `accepted` | `POTENTIALLY_EFFECTIVE` |
| Приоритизация назначенных задач Jira | 2 | 0 | 0.00% | 9.888785 | n/a … n/a | 0.47095 | `accepted` | `POTENTIALLY_EFFECTIVE` |
| Получение списка назначенных задач Jira | 1 | 0 | 0.00% | -0.880148 | n/a … n/a | 6.219943 | `accepted` | `IMPOSSIBLE_TO_BREAK_EVEN` |
| Проекты и задачи — ctx / test / слишком | 24 | 0 | 0.00% | n/a | n/a … n/a | n/a | `insufficient_evidence` | `INSUFFICIENT_EVIDENCE` |
| Анализ данных и отчётность — материалы / теме / нужен | 20 | 0 | 0.00% | n/a | n/a … n/a | n/a | `insufficient_evidence` | `INSUFFICIENT_EVIDENCE` |
| Проекты и задачи — ctx | 17 | 0 | 0.00% | n/a | n/a … n/a | n/a | `insufficient_evidence` | `INSUFFICIENT_EVIDENCE` |
| Проекты и задачи — ctx / random / unique | 17 | 0 | 0.00% | n/a | n/a … n/a | n/a | `insufficient_evidence` | `INSUFFICIENT_EVIDENCE` |
| Общие и нерешённые задачи — материалы / теме / онбординг | 16 | 0 | 0.00% | n/a | n/a … n/a | n/a | `insufficient_evidence` | `INSUFFICIENT_EVIDENCE` |
| Общие и нерешённые задачи — материалы / теме / офисные | 16 | 0 | 0.00% | n/a | n/a … n/a | n/a | `insufficient_evidence` | `INSUFFICIENT_EVIDENCE` |
| Проекты и задачи — ctx / prompt / доказательные | 15 | 0 | 0.00% | n/a | n/a … n/a | n/a | `insufficient_evidence` | `INSUFFICIENT_EVIDENCE` |
| Проекты и задачи — материалы / теме / заявки | 15 | 0 | 0.00% | n/a | n/a … n/a | n/a | `insufficient_evidence` | `INSUFFICIENT_EVIDENCE` |
| Проекты и задачи — версия / запроса / мифи | 12 | 0 | 0.00% | n/a | n/a … n/a | n/a | `insufficient_evidence` | `INSUFFICIENT_EVIDENCE` |
| Проекты и задачи — материалы / теме / сверка | 11 | 0 | 0.00% | n/a | n/a … n/a | n/a | `insufficient_evidence` | `INSUFFICIENT_EVIDENCE` |
| Общие и нерешённые задачи — материалы / теме / черновики | 10 | 0 | 0.00% | n/a | n/a … n/a | n/a | `insufficient_evidence` | `INSUFFICIENT_EVIDENCE` |
| Проекты и задачи — ctx / клиент / active | 9 | 0 | 0.00% | n/a | n/a … n/a | n/a | `insufficient_evidence` | `INSUFFICIENT_EVIDENCE` |
| Проекты и задачи — ctx | 8 | 0 | 0.00% | n/a | n/a … n/a | n/a | `insufficient_evidence` | `INSUFFICIENT_EVIDENCE` |
| Проекты и задачи — материалы / теме / контроль | 8 | 0 | 0.00% | n/a | n/a … n/a | n/a | `insufficient_evidence` | `INSUFFICIENT_EVIDENCE` |
| Проекты и задачи — ctx | 6 | 0 | 0.00% | n/a | n/a … n/a | n/a | `insufficient_evidence` | `INSUFFICIENT_EVIDENCE` |
| Проекты и задачи — ctx / материалы / теме | 5 | 0 | 0.00% | n/a | n/a … n/a | n/a | `insufficient_evidence` | `INSUFFICIENT_EVIDENCE` |
| Проекты и задачи | 2 | 0 | 0.00% | n/a | n/a … n/a | n/a | `insufficient_evidence` | `INSUFFICIENT_EVIDENCE` |

_Omitted 201 singleton targets with neither an economic calculation nor a quality evaluation. They remain available in `cluster_economics.json` and `.csv`._

## Evidence status counts

- `IMPOSSIBLE_TO_BREAK_EVEN`: 1
- `INSUFFICIENT_EVIDENCE`: 218
- `POTENTIALLY_EFFECTIVE`: 22
- `POTENTIALLY_INEFFECTIVE`: 2

## Required next data actions

- Validate manual-time baselines for 412 runs or their stable use-case/cluster passports.
- Evaluate output quality for 800 runs; potential ROI alone is not a proven result.

## Interpretation limits

- Potential ROI uses q=1 and is not observed quality.
- `manual_minutes` means expected manual/organizational work without the agent platform.
- `MODEL_ESTIMATE` baselines are potential-only; proven economics requires MEASURED or PROCESS_OWNER_APPROVED baseline evidence plus sufficient quality coverage.
- Repeated runs inside one business_task_episode count value once and cost every attempt.
- Unknown-value runs stay in platform cost and reduce conservative ROI.
- Technical run completion is not business-result correctness.
- Tokens are only a GPU allocation proxy when stronger telemetry is absent.
- Negative saved time and negative value are retained.
- Aggregated ROI is calculated from aggregate value and cost, never from mean run ROI.
- Idle licensed users remain in unallocated cost reconciliation.
- A positive proven claim requires E2+, sufficient coverage and a positive lower ROI bound.
