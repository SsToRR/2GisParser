# -*- coding: utf-8 -*-
"""Зависимости для API."""

from app.core.exceptions import TaskNotFoundError
from app.services.task_manager import task_manager


def get_task_or_404(task_id: str):
    """Получение задачи или 404."""
    task = task_manager.get_task(task_id)
    if not task:
        raise TaskNotFoundError(f"Задача {task_id} не найдена")
    return task

