# Методика доказательной оценки экономики Prompt Radar

## Что считает команда economics

Единица анализа — один `run_id`, то есть одна бизнес-задача. Сообщения,
LLM-вызовы и tool calls внутри run увеличивают стоимость, но не увеличивают
число полезных задач.

Команда отдельно рассчитывает:

- потенциальное замещение ручной работы;
- фактически наблюдаемую экономию для проверенных результатов;
- marginal и fully loaded cost;
- break-even quality;
- LOW/BASE/HIGH ROI;
- доверительный интервал качества и ROI;
- уровень доказательности;
- reconciliation затрат;
- подтверждённые потери и возможности оптимизации.

Failed, partial, cancelled и незавершённые run остаются в ledger и
знаменателях.

## Факт, вычисление и предположение

Фактом считаются только переданные наблюдения: время начала и окончания,
явные cost events, review/rework/prompt/active-wait measurements и результаты
проверки качества.

Вычисления — арифметические преобразования фактов и явно выбранных
конфигураций: стоимость минуты, амортизация, распределение затрат, saved time,
net value, break-even и ROI.

Экономический паспорт без подтверждения владельцем процесса — предположение.
Оценки Qwen/DeepSeek являются предварительными экспертными гипотезами уровня
E0 и не доказывают фактическую экономию без проверки результатов и ручного
baseline.

Технический статус `completed` не является доказательством правильности
бизнес-результата.

## Единая ставка

Для всех задач:

```text
employee_cost_per_hour = 1500 RUB
labor_cost_per_minute = 1500 / 60 = 25 RUB
```

Ролевых ставок нет. Денежные вычисления выполняются через `Decimal`,
денежные результаты округляются `ROUND_HALF_UP` до 0.01 RUB.

## Стоимость платформы

Годовая амортизация:

```text
annual_gpu_cost = gpu_purchase_cost / gpu_lifetime_years
annual_license_cost = license_cost_per_user_month × licensed_agent_users × 12
```

Поддерживаются три доли GPU:

1. `conservative_full_gpu`: 100% GPU.
2. `platform_token_ratio`: `multiplier / (multiplier + 1)`.
3. `weighted_users`:
   `(agent_users × multiplier) / (agent_users × multiplier + web_users)`.

Для 100 млн RUB, пяти лет и 150 лицензий по 10 000 RUB:

```text
GPU:       20 000 000 RUB/year
Licenses:  18 000 000 RUB/year
Total A:   38 000 000 RUB/year
Break-even: 42.22 minutes/user/workday
```

GPU распределяется по приоритету: фактическое GPU time, token proxy,
model calls/compute duration, затем run count. Token allocation всегда
помечается как proxy.

Лицензия активного пользователя распределяется между его run. Стоимость
лицензий пользователей без run сохраняется как
`unallocated_idle_license_cost`.

GPU и лицензии распределяются в целых копейках методом наибольших остатков:
сначала берутся нижние целые доли, затем оставшиеся копейки назначаются
запускам с наибольшей дробной частью. Поэтому сумма run-аллокаций точно
равна исходной стоимости и не накапливает ошибку округления на больших
датасетах.

## Время и экономия

```text
ai_wall_minutes = finished_at - started_at
```

Wall-clock не считается человеческим временем. Активное ожидание берётся из
quality evaluation, иначе:

```text
active_wait_minutes = active_wait_ratio × ai_wall_minutes
```

Prompt time берётся в порядке: quality evaluation, run metadata, default
configuration, иначе `null`. Неизвестное время не заменяется нулём.

Для проверенного run:

```text
saved_minutes =
    manual_minutes
    - prompt_minutes
    - active_wait_minutes
    - review_minutes
    - rework_minutes
```

Для потенциальной оценки:

```text
potential_saved_minutes(q) =
    q × manual_minutes
    - prompt_minutes
    - active_wait_minutes
    - human_followup_minutes
```

Потенциальные сценарии используют `q=1`, но это не наблюдаемое качество.
Отрицательная экономия сохраняется.

LOW неблагоприятен: manual LOW, follow-up HIGH, wait ratio HIGH и максимальная
стоимость. HIGH благоприятен: manual HIGH, follow-up LOW, wait ratio LOW и
минимальная стоимость.

## Ценность, ROI и break-even

```text
labor_value = saved_minutes × 25
net_value = labor_value - cost
roi = net_value / cost
```

При нулевой стоимости ROI остаётся `null`. ROI use-case, кластера и платформы
рассчитывается из агрегированных value и cost; индивидуальные ROI не
усредняются.

```text
q_break_even =
    (P + αA + H + k/25) / M
```

Для группы запусков break-even решается как одно агрегированное уравнение,
а не как среднее индивидуальных коэффициентов:

```text
q_break_even_group =
    Σ(P + αA + H + k/25) / ΣM
```

Поэтому большие ручные задачи получают вес пропорционально их baseline.

Если `q_break_even > 1`, сценарий не окупается даже при полном замещении.
Отрицательное значение сохраняется с warning как возможная ошибка данных.

```text
max_affordable_run_cost = 25 × (qM - P - αA - H)
max_affordable_ai_minutes = (qM - P - H - k/25) / α
```

При `α=0` максимальная wall-clock длительность не определяется, но compute
cost всё равно учитывается.

## Качество и уровни доказательности

- E0 — LLM-гипотеза.
- E1 — экспертная оценка или time study.
- E2 — парное сравнение с агентом и без него.
- E3 — контрольный или квазиэксперимент.

Уровень не повышается автоматически. Общий уровень ограничивается самым
слабым существенным источником.

Критериальная оценка:

```text
quality_score = Σ(weight × score)
```

Weights должны суммироваться до 1. Бинарные оценки используют Wilson 95%.
Частичные оценки используют воспроизводимый bootstrap среднего с seed и
числом итераций из конфигурации. Выборка меньше заданного минимума получает
warning.

## Potential и proven ROI

Без качества рассчитываются potential ROI и break-even, но положительный
эффект не объявляется доказанным.

`PROVEN_EFFECTIVE` требует E2+, достаточную выборку и coverage, а также
`roi_lower > 0`. `PROVEN_INEFFECTIVE` требует надёжные данные и
`roi_upper < 0`. Пересечение нуля означает `INCONCLUSIVE`.

Другие статусы показывают потенциальный эффект, высокий риск,
невозможность окупаемости, необходимость оптимизации стоимости либо
недостаток доказательств.

## Потери и ограничения

`confirmed_wasted_cost` используется только для наблюдаемых cost signals,
например failed/cancelled marginal cost или явно размеченный retry/tool-error
cost. Неоднозначные величины попадают в
`optimization_opportunity_cost`.

Методика не доказывает причинность без E2/E3, не создаёт отсутствующий web
baseline, не считает токены точной стоимостью GPU и не скрывает отрицательные
результаты. При изменении модели, процессов, цен или состава задач расчёт
необходимо повторить.
