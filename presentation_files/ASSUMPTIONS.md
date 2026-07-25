# Допущения первой версии

## Economics baseline additions

- `manual_minutes` is expected manual/organizational work without the agent
  platform.
- Baseline source is explicit: `MODEL_ESTIMATE`, `EXPERT_REVIEWED`,
  `PROCESS_OWNER_APPROVED`, or `MEASURED`.
- Proven ROI requires a measured or process-owner-approved baseline plus
  sufficient quality evidence.
- Repeated runs inside one `business_task_episode_id` count value once and
  cost every attempt.
- Unknown-value runs stay in platform cost and reduce conservative ROI.

1. Официальные материалы не задают готовую схему `dataset.zip`; версия `1.x`
   в `DATASET_SPEC.md` — проектный контракт для воспроизводимого прототипа.
2. Семь широких направлений и связь 31 сценария с ними являются черновой
   экспертной группировкой (`draft: true`), а не официальной таксономией КРОК.
3. При отсутствии `run_id` применяется отдельная детерминированная
   сегментация. Её результат содержит синтетический ID и не объявляется
   исходным идентификатором.
4. В unit-тестах и при явном `--embedding-backend fake` используется
   детерминированный hashing-embedding. Он проверяет механику, но не заменяет
   качество Qwen.
5. Пороговые значения являются начальными и требуют калибровки на независимой
   размеченной выборке.
6. HDBSCAN применяется только к residual pool. Кластер — кандидат на emerging
   use case, а не доказанный бизнес-сценарий.
7. Изображения сохраняют метаданные, но не распознаются: OCR вне scope.
8. ROI, Outcome Contracts, универсальный process mining и внешние интеграции
   сознательно не входят в первую часть.
9. Синтетические метрики демонстрируют корректность пайплайна и не описывают
   качество на реальных данных КРОК.
10. JSONL разбирается потоково, однако валидированные индексы сущностей первой
    версии материализуются в памяти для проверки связей. Для очень больших
    корпусов следующий шаг — disk-backed индексы (например, SQLite).

## Economics

- Единая ставка труда — 1500 RUB/hour; профессиональные ставки не
  используются.
- Локальные паспорта без подтверждения процесса являются E0/E1 hypothesis,
  а не фактической экономией.
- `analysis_period_months` определяет период fixed-cost allocation и должен
  соответствовать охвату входного analysis run.
- При отсутствии GPU time токены являются только proxy распределения.
- В финальном demo generated_800 GPU-доля считается как активный охват:
  `20 / 150`, а не через сравнение с обычными чат-пользователями.
- Неактивные лицензии не распределяются на активные задачи и остаются
  `unallocated_idle_license_cost`.
- Положительный potential ROI не является proven ROI.
