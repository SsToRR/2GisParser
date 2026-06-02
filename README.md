# 2GIS Parser

Веб-приложение для парсинга филиалов из ссылок 2ГИС. Пользователь вставляет ссылку на поиск, рубрику или карточку 2ГИС, выбирает лимиты и нужные поля, запускает парсер и получает предпросмотр первых 10 филиалов и CSV-файл со всеми найденными данными.

## Возможности

- Парсинг ссылок 2ГИС: поиск, рубрика или карточка компании.
- Видимый Chrome через `undetected-chromedriver`.
- Настройка лимита страниц и лимита филиалов.
- Выбор колонок перед запуском.
- Сбор данных филиалов:
  - название;
  - оценка;
  - город;
  - адрес;
  - расписание;
  - телефоны;
  - почта;
  - сайт;
  - WhatsApp номера и ссылка;
  - Telegram ссылка и ник;
  - Instagram, Youtube, VK, OK;
  - другие соцсети;
  - информация;
  - URL карточки.
- Прогресс в реальном времени через WebSocket.
- Предпросмотр первых 10 филиалов в таблице.
- CSV-экспорт всех результатов.

## Важные детали

2ГИС часто блокирует скрытый headless-браузер, поэтому по умолчанию приложение открывает обычное окно Chrome:

```env
HEADLESS=False
```

Не закрывайте Chrome во время парсинга.

По умолчанию используется один воркер:

```env
PARSER_WORKERS=1
```

Это стабильнее для Windows и `undetected-chromedriver`. Поле "Воркеры" в интерфейсе оставлено, но фронтенд сейчас отправляет `workers: 1`.

## Требования

- Python 3.11+
- Google Chrome
- Windows, macOS или Linux

Chrome major version задается в `.env` или `app/config.py`:

```env
CHROME_VERSION_MAIN=148
```

Если Chrome обновился, поменяйте значение на текущую major-версию браузера.

## Установка

1. Клонируйте репозиторий:

```powershell
git clone https://github.com/SsToRR/2GisParser.git
cd 2GisParser
```

2. Создайте виртуальное окружение:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Установите зависимости:

```powershell
pip install -r requirements.txt
```

4. При необходимости создайте `.env` на основе `.env.example`:

```powershell
copy .env.example .env
```

## Запуск

Стандартный запуск:

```powershell
python run.py
```

Приложение будет доступно:

```text
http://127.0.0.1:8000
```

Если порт 8000 занят:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

## Использование

1. Откройте сайт в браузере.
2. Вставьте ссылку 2ГИС.
3. Укажите лимит страниц.
4. Укажите лимит филиалов.
5. Оставьте `Воркеры = 1`.
6. Выберите нужные колонки в выпадающем списке.
7. Нажмите `Начать`.
8. Дождитесь окончания парсинга.
9. Посмотрите предпросмотр первых 10 филиалов.
10. Скачайте CSV.

## API

### `POST /api/v1/parse-url`

Запускает парсинг по ссылке 2ГИС.

Пример тела запроса:

```json
{
  "url": "https://2gis.kz/aktau/search/coffee",
  "max_pages": 3,
  "max_filials": 100,
  "workers": 1,
  "columns": ["Название", "Оценка", "Город", "Адрес", "Телефоны", "Instagram"]
}
```

### `GET /api/v1/tasks/{task_id}`

Возвращает статус задачи и прогресс.

### `GET /api/v1/tasks/{task_id}/results`

Возвращает результаты с пагинацией.

Пример:

```text
/api/v1/tasks/abc123/results?page=1&per_page=10
```

### `GET /api/v1/tasks/{task_id}/download`

Скачивает CSV-файл с результатами.

### `DELETE /api/v1/tasks/{task_id}`

Отменяет задачу.

### `GET /api/v1/export/columns`

Возвращает список доступных колонок.

### `WebSocket /ws/tasks/{task_id}`

Отдает обновления прогресса в реальном времени.

## Настройки

Основные переменные:

```env
DEBUG=False
HEADLESS=False
CHROME_VERSION_MAIN=148
SELENIUM_URL=http://localhost:4444/wd/hub
PAGE_SIZE=12
REQUEST_DELAY_MIN=0.05
REQUEST_DELAY_MAX=0.15
PAGE_TIMEOUT=20
ELEMENT_TIMEOUT=12
PARSER_WORKERS=1
MAX_CONCURRENT_TASKS=3
TASK_TTL_HOURS=1
EXCEL_DIR=exports
```

## Структура проекта

```text
app/
  api/              FastAPI routes
  core/             Exceptions
  models/           Pydantic schemas and domain models
  services/         Parser, task manager, CSV export
  utils/            Helpers and resource utilities
static/
  css/              Styles
  js/               Frontend logic
templates/
  index.html        Web UI
exports/            Generated CSV files, ignored by git
run.py              Local launcher
requirements.txt    Python dependencies
```

## Проверка

Проверка Python-файлов:

```powershell
python -m compileall app
```

Проверка JavaScript:

```powershell
node --check static/js/app.js
```

## Примечания

- CSV-файлы в `exports/` не пушатся в git.
- `.env` не пушится в git.
- Если после изменений интерфейс выглядит старым, обновите страницу через `Ctrl + F5`.
