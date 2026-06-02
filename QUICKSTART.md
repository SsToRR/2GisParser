# Быстрый старт

## Локальный запуск

1. **Установите зависимости:**
```bash
pip install -r requirements.txt
```

2. **Установите ChromeDriver:**
   - Автоматически через `webdriver-manager` (уже включен)
   - Или вручную: https://chromedriver.chromium.org/

3. **Создайте файл `.env` (опционально):**
```bash
cp .env.example .env
```

4. **Запустите приложение:**
```bash
python run.py
```

Или:
```bash
uvicorn app.main:app --reload
```

5. **Откройте в браузере:**
```
http://localhost:8000
```

## Docker запуск

1. **Соберите и запустите:**
```bash
docker-compose up -d
```

2. **Откройте в браузере:**
```
http://localhost:8000
```

3. **Остановка:**
```bash
docker-compose down
```

## Использование

1. Введите поисковый запрос (например: "Строительные материалы")
2. Выберите города из списка
3. Нажмите "Начать парсинг"
4. Отслеживайте прогресс в реальном времени
5. После завершения скачайте Excel файл

## API документация

После запуска доступна автоматическая документация:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Решение проблем

### ChromeDriver не найден
Установите ChromeDriver вручную или используйте Docker.

### Ошибка подключения к Selenium
Если используете remote WebDriver, убедитесь что Selenium запущен:
```bash
docker-compose up selenium
```

### Проблемы с путями
Убедитесь что вы запускаете из директории `project/`:
```bash
cd project
python run.py
```

