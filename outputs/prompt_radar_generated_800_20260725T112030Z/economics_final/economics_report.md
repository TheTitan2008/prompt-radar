# Prompt Radar economics report

> Qwen/DeepSeek estimates are E0 hypotheses. They do not prove savings until the output is checked and the manual baseline is validated.

## Executive summary

- Runs: 800
- Analysis period: 0.203657407407407 months
- Selected cost scenario: `conservative_full_gpu`
- GPU allocation: `token_proxy` (proxy)
- Allocated fully loaded cost: 380160.41 RUB
- Idle license cost: 264754.71 RUB
- Potential BASE saved minutes: 10943.6067
- Potential BASE net value: -371324.8 RUB
- Potential BASE ROI: -0.575773
- Total tokens: 6893149
- Full cost per 1k tokens: 93.558854 RUB
- Saved FTE-months (BASE): 1.139959
- FTE-month value (BASE): 455983.61 RUB
- B > A by FTE view: False
- Confirmed wasted cost: 0.00 RUB
- Optimization opportunity: 308882.81 RUB

## Data completeness

| Evidence | Runs | Coverage |
|---|---:|---:|
| Prompt effort available (`prompt_minutes`) | 800/800 | 100.0% |
| Prompt effort measured | 0/800 | 0.0% |
| Prompt effort assumed by cost config | 800/800 | 100.0% |
| Manual baseline / economic passport | 481/800 | 60.1% |
| Potential calculation available | 481/800 | 60.1% |
| Quality evaluated | 0/800 | 0.0% |
| Actual calculation available | 0/800 | 0.0% |

> **Prompt effort is assumed for 800 runs, not measured.** Potential ROI is a sensitivity scenario and must not be presented as an observed result.

Most frequent missing evidence:
- `economic_passport`: 319 runs

## Cost scenarios

| Scenario | Annual cost | Monthly cost | Break-even min/user/day |
|---|---:|---:|---:|
| `conservative_full_gpu` | 38000000.00 | 3166666.67 | 42.22 |
| `platform_token_ratio` | 34666666.67 | 2888888.89 | 38.52 |
| `weighted_users` | 25317073.17 | 2109756.10 | 28.13 |

## Platform cost structure

- Annual GPU amortization: 20000000.0 RUB
- Annual licenses: 18000000.0 RUB
- Annual electricity: 0.0 RUB
- Annual support: 0.0 RUB
- Annual development: 0.0 RUB
- Annual shared tools: 0.0 RUB

## Use-case and cluster evidence

| Target | Runs | Evaluated | Coverage | Potential ROI BASE | ROI interval | q break-even BASE | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| Поиск контактных лиц клиента | 91 | 0 | 0.00% | 8.014717 | n/a … n/a | 0.451137 | `POTENTIALLY_EFFECTIVE` |
| Выгрузка выбранных данных в Excel | 36 | 0 | 0.00% | 4.79385 | n/a … n/a | 0.570211 | `POTENTIALLY_EFFECTIVE` |
| Создание и обновление тикета ИСУП | 29 | 0 | 0.00% | 3.891864 | n/a … n/a | 0.575543 | `POTENTIALLY_EFFECTIVE` |
| Подготовка ежедневной сводки почты | 26 | 0 | 0.00% | 13.925745 | n/a … n/a | 0.307159 | `POTENTIALLY_EFFECTIVE` |
| Формирование Excel-отчёта по клиенту | 22 | 0 | 0.00% | 24.997033 | n/a … n/a | 0.370488 | `POTENTIALLY_EFFECTIVE` |
| Поиск корпоративного процесса в Confluence | 21 | 0 | 0.00% | 2.526209 | n/a … n/a | 0.56341 | `POTENTIALLY_EFFECTIVE` |
| Ведение истории личных задач | 20 | 0 | 0.00% | 2.568232 | n/a … n/a | 0.628096 | `POTENTIALLY_EFFECTIVE` |
| Подготовка заметки о сотруднике | 20 | 0 | 0.00% | 3.309504 | n/a … n/a | 0.654337 | `POTENTIALLY_EFFECTIVE` |
| Подготовка ответа клиенту по переписке | 20 | 0 | 0.00% | 13.374309 | n/a … n/a | 0.416062 | `POTENTIALLY_EFFECTIVE` |
| Поиск слота руководителя и создание встречи | 20 | 0 | 0.00% | 6.829471 | n/a … n/a | 0.462258 | `POTENTIALLY_EFFECTIVE` |
| Анализ применения офисных IoT-датчиков | 16 | 0 | 0.00% | 4.953687 | n/a … n/a | 0.432993 | `POTENTIALLY_EFFECTIVE` |
| Онбординг внутренних AI-ассистентов | 16 | 0 | 0.00% | 1.284962 | n/a … n/a | 0.619532 | `POTENTIALLY_EFFECTIVE` |
| Сбор данных по группе компаний клиента | 16 | 0 | 0.00% | 49.168038 | n/a … n/a | 0.25661 | `POTENTIALLY_EFFECTIVE` |
| Обработка заявок в библиотеку промптов | 15 | 0 | 0.00% | 5.26241 | n/a … n/a | 0.424301 | `POTENTIALLY_EFFECTIVE` |
| Ответы студентам по сервисам НИЯУ МИФИ | 12 | 0 | 0.00% | 1.562896 | n/a … n/a | 0.602802 | `POTENTIALLY_EFFECTIVE` |
| Сверка витрин учебных материалов | 11 | 0 | 0.00% | 1.077369 | n/a … n/a | 0.635814 | `POTENTIALLY_EFFECTIVE` |
| Создание напоминаний по договорённостям | 11 | 0 | 0.00% | 2.627592 | n/a … n/a | 0.562503 | `POTENTIALLY_EFFECTIVE` |
| Подготовка черновиков внутренних объявлений | 10 | 0 | 0.00% | 0.192411 | n/a … n/a | 0.892508 | `HIGH_RISK` |
| Контроль локальных справочников оборудования | 8 | 0 | 0.00% | 0.379113 | n/a … n/a | 0.821414 | `HIGH_RISK` |
| Поиск общего календарного слота группы | 7 | 0 | 0.00% | 4.370458 | n/a … n/a | 0.497318 | `POTENTIALLY_EFFECTIVE` |
| Извлечение сведений из описания встречи | 6 | 0 | 0.00% | 0.057297 | n/a … n/a | 0.975068 | `HIGH_RISK` |
| Контроль изменений статусов проектов ИСУП | 6 | 0 | 0.00% | 2.465722 | n/a … n/a | 0.570484 | `POTENTIALLY_EFFECTIVE` |
| Проверка и подтверждение выполнения задач | 6 | 0 | 0.00% | 0.064725 | n/a … n/a | 0.970207 | `HIGH_RISK` |
| Создание проектного тикета из письма | 6 | 0 | 0.00% | 2.293157 | n/a … n/a | 0.624813 | `POTENTIALLY_EFFECTIVE` |
| Оформление итогов обсуждения | 5 | 0 | 0.00% | 7.315724 | n/a … n/a | 0.44976 | `POTENTIALLY_EFFECTIVE` |
| Проверка небольших списков закупок | 5 | 0 | 0.00% | -0.280905 | n/a … n/a | 1.227416 | `POTENTIALLY_INEFFECTIVE` |
| Фиксация наблюдений о сотруднике | 5 | 0 | 0.00% | 8.093793 | n/a … n/a | 0.510121 | `POTENTIALLY_EFFECTIVE` |
| Поиск публикаций о поставщике | 4 | 0 | 0.00% | 12.71958 | n/a … n/a | 0.383246 | `POTENTIALLY_EFFECTIVE` |
| Экспорт аналитических результатов в Excel | 4 | 0 | 0.00% | 6.591219 | n/a … n/a | 0.532794 | `POTENTIALLY_EFFECTIVE` |
| Поиск и бронирование переговорной | 2 | 0 | 0.00% | 4.291923 | n/a … n/a | 0.53982 | `POTENTIALLY_EFFECTIVE` |
| Поиск команды проекта и владельца вендора | 2 | 0 | 0.00% | 28.282163 | n/a … n/a | 0.31741 | `POTENTIALLY_EFFECTIVE` |
| Приоритизация назначенных задач Jira | 2 | 0 | 0.00% | 6.440925 | n/a … n/a | 0.49574 | `POTENTIALLY_EFFECTIVE` |
| Получение списка назначенных задач Jira | 1 | 0 | 0.00% | -0.997234 | n/a … n/a | 100.893258 | `IMPOSSIBLE_TO_BREAK_EVEN` |
| Смешанные известные и мусорные запросы | 24 | 0 | 0.00% | n/a | n/a … n/a | n/a | `INSUFFICIENT_EVIDENCE` |
| Смешанные проверки данных и микроопросы | 20 | 0 | 0.00% | n/a | n/a … n/a | n/a | `INSUFFICIENT_EVIDENCE` |
| Ошибочно нераспознанные известные задачи | 17 | 0 | 0.00% | n/a | n/a … n/a | n/a | `INSUFFICIENT_EVIDENCE` |
| Смешанные long-context и случайные запросы | 17 | 0 | 0.00% | n/a | n/a … n/a | n/a | `INSUFFICIENT_EVIDENCE` |
| Смешанные long-context запросы | 15 | 0 | 0.00% | n/a | n/a … n/a | n/a | `INSUFFICIENT_EVIDENCE` |
| Почти полностью известные сценарии с шумовым хвостом | 9 | 0 | 0.00% | n/a | n/a … n/a | n/a | `INSUFFICIENT_EVIDENCE` |
| Ошибочно нераспознанные известные сценарии | 8 | 0 | 0.00% | n/a | n/a … n/a | n/a | `INSUFFICIENT_EVIDENCE` |
| Небольшая группа ошибочно нераспознанных known-запросов | 6 | 0 | 0.00% | n/a | n/a … n/a | n/a | `INSUFFICIENT_EVIDENCE` |
| Проекты и задачи | 2 | 0 | 0.00% | n/a | n/a … n/a | n/a | `INSUFFICIENT_EVIDENCE` |

_Omitted 201 singleton targets with neither an economic calculation nor a quality evaluation. They remain available in `cluster_economics.json` and `.csv`._

## Evidence status counts

- `HIGH_RISK`: 4
- `IMPOSSIBLE_TO_BREAK_EVEN`: 1
- `INSUFFICIENT_EVIDENCE`: 210
- `POTENTIALLY_EFFECTIVE`: 27
- `POTENTIALLY_INEFFECTIVE`: 1

## Required next data actions

- Validate manual-time baselines for 319 runs or their stable use-case/cluster passports.
- Evaluate output quality for 800 runs; potential ROI alone is not a proven result.

## Interpretation limits

- Potential ROI uses q=1 and is not observed quality.
- Technical run completion is not business-result correctness.
- Tokens are only a GPU allocation proxy when stronger telemetry is absent.
- Negative saved time and negative value are retained.
- Aggregated ROI is calculated from aggregate value and cost, never from mean run ROI.
- Idle licensed users remain in unallocated cost reconciliation.
- A positive proven claim requires E2+, sufficient coverage and a positive lower ROI bound.
