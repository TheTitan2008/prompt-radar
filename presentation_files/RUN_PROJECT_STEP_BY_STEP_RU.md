# Prompt Radar: пошаговый запуск проекта и просмотр результатов

Эта инструкция описывает запуск проекта с нуля на новом ноутбуке: как скачать
репозиторий, установить зависимости, запустить анализ `dataset.zip`, посчитать
экономику и открыть итоговые отчёты.

## 1. Что должно быть установлено

На компьютере нужны:

- Windows;
- Git;
- Python 3.11 или Python 3.13;
- интернет для первого скачивания зависимостей и Qwen embedding model.

Проверка:

```powershell
python --version
git --version
```

Если команда `python` не работает, попробуйте:

```powershell
py --version
```

## 2. Скачать проект с GitHub

Откройте PowerShell:

```powershell
cd D:\
git clone https://github.com/TheTitan2008/prompt-radar.git
cd D:\prompt-radar
```

Если проект нужен в другой папке, можно выбрать другой путь. Главное — все
следующие команды выполнять из папки проекта.

## 3. Создать виртуальное окружение

```powershell
py -3.11 -m venv .venv
```

Если Python 3.11 не установлен:

```powershell
python -m venv .venv
```

Активировать окружение:

```powershell
.\.venv\Scripts\Activate.ps1
```

Если PowerShell запрещает запуск скриптов:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\.venv\Scripts\Activate.ps1
```

После активации слева в терминале появится `(.venv)`.

## 4. Установить зависимости

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".[attachments,ml,dev]"
```

Это установит библиотеки для:

- проверки ZIP/JSONL;
- чтения TXT, Markdown, CSV, JSON, XLSX, DOCX, PDF;
- Qwen embeddings;
- HDBSCAN-кластеризации;
- отчётов и тестов.

## 5. Скачать Qwen embedding model

Один раз:

```powershell
python -m prompt_radar.cli download-model
```

Эта модель нужна для определения похожести запросов, сопоставления с известными
сценариями и кластеризации.

## 6. Проверить, что CLI работает

```powershell
python -m prompt_radar.cli --help
```

Должны появиться команды:

```text
download-model
validate
analyze
evaluate
economics
```

Можно также запустить тесты:

```powershell
python -m pytest -m "not integration"
```

Ожидаемый результат в актуальной версии:

```text
79 passed, 1 deselected
```

## 7. Быстро посмотреть уже готовые результаты

В репозитории есть папка:

```text
presentation_files
```

Открыть главный HTML-отчёт:

```powershell
start presentation_files\statistics_report.html
```

Главные файлы в этой папке:

```text
statistics_report.html       красивый HTML-дашборд
economics_report.md          экономический отчёт
ROI_EXPLANATION_RU.md        объяснение ROI на русском
report.md                    отчёт первой части анализа
clusters.json                итоговые кластеры
runs_analysis.jsonl          анализ всех run
dataset.zip                  финальный demo dataset
```

## 8. Запуск на готовом demo dataset

Финальный датасет уже лежит в проекте:

```text
data\generated_800\dataset.zip
```

### 8.1. Проверить датасет

```powershell
python -m prompt_radar.cli validate --input data\generated_800\dataset.zip
```

Хороший результат:

```text
valid: True
issues: 0
```

### 8.2. Запустить анализ промптов и кластеризацию

```powershell
python -m prompt_radar.cli analyze `
  --input data\generated_800\dataset.zip `
  --output outputs `
  --offline
```

Команда делает первую часть проекта:

- безопасно читает датасет;
- восстанавливает пользовательские задачи на уровне `run_id`;
- извлекает цели запросов;
- обрабатывает вложения;
- считает Qwen embeddings;
- сопоставляет запросы с известными сценариями;
- остаточные запросы группирует через HDBSCAN;
- сохраняет отчёты и JSONL/JSON/Parquet артефакты.

После запуска появится новая папка внутри:

```text
outputs\
```

Например:

```text
outputs\prompt_radar_generated_800_20260725T150000Z
```

### 8.3. Найти имя созданной папки

```powershell
dir outputs
```

Дальше в командах ниже заменяйте `ИМЯ_ПАПКИ` на имя последней созданной папки.

### 8.4. Запустить экономику

```powershell
python -m prompt_radar.cli economics `
  --analysis outputs\ИМЯ_ПАПКИ `
  --cost-config data\generated_800\economics_cost_config.json `
  --output outputs\ИМЯ_ПАПКИ\economics_final
```

Команда делает вторую часть проекта:

- считает стоимость платформы;
- распределяет GPU и лицензии по run;
- считает стоимость токенов;
- считает потенциальную экономию времени;
- переводит минуты в рубли по ставке `1500 ₽/час`;
- считает ROI;
- считает break-even;
- считает FTE-месяцы;
- делает статистику по пользователям, категориям и кластерам;
- не выкидывает unknown-задачи из стоимости.

### 8.5. Открыть результаты

Главный красивый отчёт:

```powershell
start outputs\ИМЯ_ПАПКИ\economics_final\statistics_report.html
```

Текстовые отчёты:

```powershell
notepad outputs\ИМЯ_ПАПКИ\report.md
notepad outputs\ИМЯ_ПАПКИ\economics_final\economics_report.md
notepad outputs\ИМЯ_ПАПКИ\economics_final\platform_economics.json
```

## 9. Запуск на своём dataset.zip

Создайте папку для входных данных:

```powershell
mkdir data\input
```

Положите свой архив сюда:

```text
data\input\dataset.zip
```

Проверка:

```powershell
python -m prompt_radar.cli validate --input data\input\dataset.zip
```

Анализ:

```powershell
python -m prompt_radar.cli analyze `
  --input data\input\dataset.zip `
  --output outputs `
  --offline
```

Экономика:

```powershell
python -m prompt_radar.cli economics `
  --analysis outputs\ИМЯ_НОВОЙ_ПАПКИ `
  --cost-config data\generated_800\economics_cost_config.json `
  --output outputs\ИМЯ_НОВОЙ_ПАПКИ\economics_final
```

Открыть HTML:

```powershell
start outputs\ИМЯ_НОВОЙ_ПАПКИ\economics_final\statistics_report.html
```

## 10. Запуск с API для новых неизвестных кластеров

По умолчанию demo dataset может использовать заранее подготовленные ответы,
чтобы не тратить деньги на API. Для нового датасета можно включить API.

### 10.1. Создать `.env`

```powershell
copy .env.example .env
notepad .env
```

Пример для DeepSeek:

```env
PROMPT_RADAR_CHAT_API_BASE_URL=https://api.deepseek.com
PROMPT_RADAR_CHAT_API_KEY=ТВОЙ_КЛЮЧ
PROMPT_RADAR_CHAT_MODEL=deepseek-chat
```

Пример для Qwen:

```env
PROMPT_RADAR_CHAT_API_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
PROMPT_RADAR_CHAT_API_KEY=ТВОЙ_КЛЮЧ
PROMPT_RADAR_CHAT_MODEL=qwen-plus
```

### 10.2. Запустить анализ с API enrichment

```powershell
python -m prompt_radar.cli analyze `
  --input data\input\dataset.zip `
  --output outputs `
  --offline `
  --enrich-clusters `
  --api-env-file .env `
  --precomputed-enrichments ""
```

Что означают параметры:

```text
--enrich-clusters              включить API для названий неизвестных кластеров
--api-env-file .env            взять API-ключи из .env
--precomputed-enrichments ""   не брать заранее подготовленные ответы
```

API не получает все длинные тексты целиком. Отправляется compact payload:

- несколько коротких примеров из кластера;
- cluster fingerprint;
- top terms;
- статистика токенов;
- типы вложений;
- uncertainty flags;
- кандидаты известных сценариев.

## 11. Что появляется после `analyze`

В папке:

```text
outputs\ИМЯ_ПАПКИ\
```

Главные файлы:

```text
report.md                    Markdown-отчёт первой части
pipeline_metadata.json        метаданные запуска
runs_analysis.jsonl           анализ каждого run
clusters.json                 итоговые кластеры
cluster_members.jsonl         состав кластеров
embeddings.npz                embeddings
warnings.jsonl                предупреждения
```

Смотреть в первую очередь:

```powershell
notepad outputs\ИМЯ_ПАПКИ\report.md
notepad outputs\ИМЯ_ПАПКИ\clusters.json
```

## 12. Что появляется после `economics`

В папке:

```text
outputs\ИМЯ_ПАПКИ\economics_final\
```

Главные файлы:

```text
statistics_report.html        красивый HTML-дашборд
economics_report.md           экономический Markdown-отчёт
platform_economics.json       экономика всей платформы
cluster_economics.json        экономика по кластерам
run_economic_ledger.jsonl     экономика по каждому run
statistics_summary.json       данные для HTML-отчёта
cost_reconciliation.json      проверка распределения стоимости
value_leakage.json            потери и недоказанная ценность
```

Открывать:

```powershell
start outputs\ИМЯ_ПАПКИ\economics_final\statistics_report.html
```

## 13. Что показывать на презентации

Рекомендуемый порядок:

1. GitHub repo.
2. `README.md`.
3. `src/prompt_radar/cli.py`.
4. `src/prompt_radar/economics_analysis/`.
5. `presentation_files/statistics_report.html`.
6. `presentation_files/economics_report.md`.
7. `presentation_files/ROI_EXPLANATION_RU.md`.
8. `presentation_files/dataset.zip`.

Главный файл для красивого показа:

```powershell
start presentation_files\statistics_report.html
```

Короткая фраза:

> Prompt Radar принимает архив AI-чатов, безопасно валидирует его, извлекает
> задачи пользователей, сопоставляет их с известными сценариями или новыми
> кластерами через Qwen embeddings и HDBSCAN, а затем считает стоимость
> платформы, ROI, break-even, FTE и статистику по пользователям. Unknown-задачи
> не скрываются: их стоимость остаётся в расчёте.

## 14. Частые проблемы

### Не активируется `.venv`

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\.venv\Scripts\Activate.ps1
```

### Не находится Python 3.11

```powershell
python -m venv .venv
```

### Нет Qwen model

```powershell
python -m prompt_radar.cli download-model
```

### Economics пишет, что output уже существует

Укажите другое имя:

```powershell
--output outputs\ИМЯ_ПАПКИ\economics_final_2
```

### API не работает

Проверьте файл:

```powershell
notepad .env
```

Убедитесь, что URL, ключ и имя модели указаны правильно.
