# Структура проекта

## Описание

Полноценное FastAPI веб-приложение для парсинга данных с 2GIS.

## Структура директорий

```
project/
├── app/                          # Основное приложение
│   ├── __init__.py
│   ├── main.py                   # Точка входа FastAPI
│   ├── config.py                 # Конфигурация (pydantic-settings)
│   │
│   ├── models/                   # Модели данных
│   │   ├── __init__.py
│   │   ├── schemas.py           # Pydantic схемы для API
│   │   └── domain.py            # Доменные модели (dataclasses)
│   │
│   ├── api/                      # API endpoints
│   │   ├── __init__.py
│   │   ├── routes.py            # Все API маршруты
│   │   └── dependencies.py      # Зависимости API
│   │
│   ├── services/                 # Бизнес-логика
│   │   ├── __init__.py
│   │   ├── parser.py            # Парсер 2GIS (адаптированный)
│   │   ├── task_manager.py      # Менеджер задач (in-memory)
│   │   └── export.py            # Экспорт в Excel
│   │
│   ├── core/                     # Ядро приложения
│   │   ├── __init__.py
│   │   └── exceptions.py        # Кастомные исключения
│   │
│   └── utils/                    # Утилиты
│       ├── __init__.py
│       └── helpers.py           # TextCleaner, UrlExtractor
│
├── static/                       # Статические файлы
│   ├── css/
│   │   └── styles.css           # Дополнительные стили
│   └── js/
│       └── app.js               # JavaScript логика
│
├── templates/                    # HTML шаблоны
│   └── index.html               # Главная страница
│
├── exports/                      # Экспортированные Excel файлы
│   └── (создается автоматически)
│
├── requirements.txt              # Python зависимости
├── Dockerfile                    # Docker образ
├── docker-compose.yml            # Docker Compose конфигурация
├── .env.example                  # Пример переменных окружения
├── .gitignore                    # Git ignore
├── README.md                     # Основная документация
├── QUICKSTART.md                 # Быстрый старт
└── run.py                        # Скрипт запуска

```

## Основные компоненты

### 1. API Endpoints (`app/api/routes.py`)

- `GET /` - Главная страница
- `GET /api/v1/cities` - Список городов
- `POST /api/v1/parse` - Запуск парсинга
- `GET /api/v1/tasks/{task_id}` - Статус задачи
- `GET /api/v1/tasks/{task_id}/results` - Результаты
- `GET /api/v1/tasks/{task_id}/download` - Скачать Excel
- `DELETE /api/v1/tasks/{task_id}` - Отмена задачи
- `WebSocket /ws/tasks/{task_id}` - Real-time прогресс

### 2. Парсер (`app/services/parser.py`)

Адаптированный код из оригинального парсера:
- `Parser2GIS` - основной класс парсера
- `FirmScraper` - скрапер данных фирмы
- `WebDriverFactory` - фабрика WebDriver

### 3. Менеджер задач (`app/services/task_manager.py`)

In-memory хранилище задач:
- Создание и управление задачами
- Обновление прогресса
- Автоматическая очистка старых задач

### 4. Экспорт (`app/services/export.py`)

Экспорт данных в Excel:
- Форматирование таблиц
- Автоматическая настройка столбцов

### 5. Фронтенд

- **HTML**: Современный интерфейс с Tailwind CSS
- **JavaScript**: 
  - Tom Select для мультиселекта городов
  - WebSocket для real-time прогресса
  - Polling как fallback
  - Пагинация результатов

## Технологии

- **Backend**: FastAPI, Pydantic, Selenium
- **Frontend**: HTML, Tailwind CSS, JavaScript, Tom Select
- **Storage**: In-memory (можно заменить на Redis)
- **Export**: openpyxl для Excel

## Особенности

✅ Полная адаптация оригинального парсера
✅ Real-time прогресс через WebSocket
✅ Красивый современный UI
✅ Экспорт в Excel
✅ Docker поддержка
✅ Rate limiting
✅ Валидация данных
✅ Обработка ошибок

## Следующие шаги (опционально)

- [ ] Интеграция с Redis для хранения задач
- [ ] Celery для фоновых задач
- [ ] База данных для истории парсинга
- [ ] Аутентификация пользователей
- [ ] Расширенная аналитика

