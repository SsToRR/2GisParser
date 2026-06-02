# -*- coding: utf-8 -*-
"""Главный файл FastAPI приложения."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pathlib import Path

from app.config import settings
from app.api.routes import router
from app.core.exceptions import TaskNotFoundError, InvalidRequestError, ParseError
from app.services.task_manager import task_manager
from app.utils.resources import resource_path


# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения."""
    # Startup
    logger.info("Запуск приложения...")
    yield
    # Shutdown
    logger.info("Остановка приложения...")
    task_manager.stop()


# Создание приложения
app = FastAPI(
    title="2GIS Parser API",
    description="Веб-приложение для парсинга данных с 2GIS",
    version="1.0.0",
    lifespan=lifespan
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В production указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутера
app.include_router(router)

# Статические файлы
static_dir = resource_path("static")
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Templates
templates_dir = resource_path("templates")
templates = Jinja2Templates(directory=str(templates_dir))


# Exception handlers
@app.exception_handler(TaskNotFoundError)
async def task_not_found_handler(request: Request, exc: TaskNotFoundError):
    """Обработчик ошибки 'Задача не найдена'."""
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)}
    )


@app.exception_handler(InvalidRequestError)
async def invalid_request_handler(request: Request, exc: InvalidRequestError):
    """Обработчик ошибки 'Невалидный запрос'."""
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)}
    )


@app.exception_handler(ParseError)
async def parse_error_handler(request: Request, exc: ParseError):
    """Обработчик ошибки парсинга."""
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)}
    )


@app.get("/health")
async def health_check():
    """Проверка здоровья приложения."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
