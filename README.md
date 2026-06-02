# 2GIS Parser - FastAPI веб-приложение

Веб-приложение для парсинга данных с 2GIS с использованием FastAPI, Selenium и современного фронтенда.

## Возможности

- 🔍 Парсинг данных по поисковому запросу
- 🏙️ Поддержка множества городов
- 📊 Отслеживание прогресса в реальном времени (WebSocket)
- 📥 Экспорт результатов в Excel
- 🎨 Современный и адаптивный UI
- ⚡ Асинхронная обработка задач

## Структура проекта

```
project/
├── app/
│   ├── __init__.py
│   ├── main.py              # Точка входа FastAPI
│   ├── config.py            # Конфигурация
│   ├── models/              # Модели данных
│   │   ├── schemas.py       # Pydantic схемы
│   │   └── domain.py        # Доменные модели
│   ├── api/                 # API endpoints
│   │   ├── routes.py
│   │   └── dependencies.py
│   ├── services/            # Бизнес-логика
│   │   ├── parser.py        # Парсер 2GIS
│   │   ├── task_manager.py  # Менеджер задач
│   │   └── export.py        # Экспорт в Excel
│   ├── core/                # Ядро приложения
│   │   └── exceptions.py
│   └── utils/               # Утилиты
│       └── helpers.py
├── static/                  # Статические файлы
│   ├── css/
│   └── js/
├── templates/               # HTML шаблоны
│   └── index.html
├── exports/                 # Экспортированные Excel файлы
├── requirements.txt
├── docker-compose.yml
└── README.md
```

## Установка

### Локальная установка

1. Клонируйте репозиторий или скопируйте файлы проекта

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Установите ChromeDriver:
   - Скачайте с https://chromedriver.chromium.org/
   - Или используйте `webdriver-manager` (автоматически)

4. Создайте файл `.env` (опционально):
```env
DEBUG=False
HEADLESS=True
REDIS_URL=redis://localhost:6379/0
MAX_CONCURRENT_TASKS=3
```

5. Запустите приложение:
```bash
cd project
uvicorn app.main:app --reload
```

Приложение будет доступно по адресу: http://localhost:8000

### Docker установка

1. Соберите и запустите контейнеры:
```bash
docker-compose up -d
```

2. Приложение будет доступно по адресу: http://localhost:8000

## Использование

1. Откройте веб-интерфейс в браузере
2. Введите поисковый запрос (например: "Строительные материалы")
3. Выберите один или несколько городов
4. Нажмите "Начать парсинг"
5. Отслеживайте прогресс в реальном времени
6. После завершения просмотрите результаты и скачайте Excel файл

## API Endpoints

### GET `/api/v1/cities`
Получение списка доступных городов.

**Query параметры:**
- `search` (опционально) - поиск по названию

**Пример:**
```bash
curl http://localhost:8000/api/v1/cities?search=казань
```

### POST `/api/v1/parse`
Запуск парсинга.

**Body:**
```json
{
  "query": "Строительные материалы",
  "cities": ["kazan", "moscow"]
}
```

**Ответ:**
```json
{
  "task_id": "abc12345",
  "status": "pending",
  "message": "Задача создана и поставлена в очередь"
}
```

### GET `/api/v1/tasks/{task_id}`
Получение статуса задачи.

**Ответ:**
```json
{
  "task_id": "abc12345",
  "status": "running",
  "progress": 45,
  "current_city": "Казань",
  "firms_processed": 25,
  "firms_total": 55
}
```

### GET `/api/v1/tasks/{task_id}/results`
Получение результатов парсинга.

**Query параметры:**
- `page` (по умолчанию: 1)
- `per_page` (по умолчанию: 20, максимум: 100)

### GET `/api/v1/tasks/{task_id}/download`
Скачать Excel файл с результатами.

### DELETE `/api/v1/tasks/{task_id}`
Отмена задачи.

### WebSocket `/ws/tasks/{task_id}`
Подключение для отслеживания прогресса в реальном времени.

## Конфигурация

Настройки можно изменить через переменные окружения или файл `.env`:

- `DEBUG` - режим отладки (по умолчанию: False)
- `HEADLESS` - запуск браузера в headless режиме (по умолчанию: True)
- `REDIS_URL` - URL Redis (для будущего использования)
- `MAX_CONCURRENT_TASKS` - максимальное количество одновременных задач
- `PAGE_SIZE` - количество результатов на странице 2GIS (по умолчанию: 12)
- `REQUEST_DELAY_MIN` - минимальная задержка между запросами (секунды)
- `REQUEST_DELAY_MAX` - максимальная задержка между запросами (секунды)

## Разработка

### Запуск в режиме разработки

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Тестирование

```bash
pytest tests/
```

## Docker

### docker-compose.yml

Включает:
- FastAPI приложение
- Redis (для будущего использования)
- Selenium standalone Chrome (опционально)

### Запуск

```bash
docker-compose up -d
```

### Остановка

```bash
docker-compose down
```

## Автор

2GIS Parser Team

