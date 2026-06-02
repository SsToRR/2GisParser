# -*- coding: utf-8 -*-
"""Менеджер задач парсинга."""

import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional
from dataclasses import asdict

from app.models.domain import ParseRequest, ParseResult, ParseProgress, TaskStatus
from app.core.exceptions import TaskNotFoundError


class TaskManager:
    """Менеджер задач (in-memory хранилище)."""
    
    def __init__(self, ttl_hours: int = 1):
        self.tasks: Dict[str, Dict] = {}
        self.lock = threading.Lock()
        self.ttl_hours = ttl_hours
        self._cleanup_thread = None
        self._running = True
        self._start_cleanup_thread()
    
    def create_task(self, request: ParseRequest) -> str:
        """Создание новой задачи."""
        from app.services.parser import Parser2GIS
        
        task_id = Parser2GIS._generate_task_id()
        progress = ParseProgress(
            status=TaskStatus.PENDING,
            total_cities=len(request.cities)
        )
        
        result = ParseResult(
            task_id=task_id,
            request=request,
            progress=progress
        )
        
        with self.lock:
            self.tasks[task_id] = {
                'result': result,
                'created_at': datetime.now(),
                'updated_at': datetime.now(),
                'parser': None  # Будет установлен при запуске
            }
        
        return task_id
    
    def get_task(self, task_id: str) -> Optional[ParseResult]:
        """Получение задачи."""
        with self.lock:
            task_data = self.tasks.get(task_id)
            if not task_data:
                return None
            return task_data['result']
    
    def get_task_dict(self, task_id: str) -> Optional[Dict]:
        """Получение задачи в виде словаря."""
        with self.lock:
            task_data = self.tasks.get(task_id)
            if not task_data:
                return None
            return {
                'task_id': task_data['result'].task_id,
                'status': task_data['result'].progress.status.value,
                'progress': task_data['result'].progress.progress_percent,
                'current_city': task_data['result'].progress.current_city,
                'current_city_index': task_data['result'].progress.current_city_index,
                'total_cities': task_data['result'].progress.total_cities,
                'current_page': task_data['result'].progress.current_page,
                'total_pages': task_data['result'].progress.total_pages,
                'firms_processed': task_data['result'].progress.firms_processed,
                'firms_total': task_data['result'].progress.firms_total,
                'message': task_data['result'].progress.message,
                'errors': task_data['result'].progress.errors,
                'created_at': task_data['created_at'],
                'updated_at': task_data['updated_at']
            }
    
    def update_progress(self, task_id: str, progress: ParseProgress) -> None:
        """Обновление прогресса задачи."""
        with self.lock:
            task_data = self.tasks.get(task_id)
            if task_data:
                task_data['result'].progress = progress
                task_data['updated_at'] = datetime.now()
    
    def set_result(self, task_id: str, result: ParseResult) -> None:
        """Установка результата задачи."""
        with self.lock:
            task_data = self.tasks.get(task_id)
            if task_data:
                task_data['result'] = result
                task_data['updated_at'] = datetime.now()
    
    def set_parser(self, task_id: str, parser) -> None:
        """Установка парсера для задачи (для отмены)."""
        with self.lock:
            task_data = self.tasks.get(task_id)
            if task_data:
                task_data['parser'] = parser
    
    def get_parser(self, task_id: str):
        """Получение парсера задачи."""
        with self.lock:
            task_data = self.tasks.get(task_id)
            if task_data:
                return task_data.get('parser')
            return None
    
    def cancel_task(self, task_id: str) -> bool:
        """Отмена задачи."""
        with self.lock:
            task_data = self.tasks.get(task_id)
            if not task_data:
                return False
            
            parser = task_data.get('parser')
            if parser:
                parser.cancel()
            
            task_data['result'].progress.status = TaskStatus.CANCELLED
            task_data['updated_at'] = datetime.now()
            return True
    
    def cleanup_old_tasks(self) -> int:
        """Очистка старых задач."""
        cutoff = datetime.now() - timedelta(hours=self.ttl_hours)
        removed = 0
        
        with self.lock:
            to_remove = []
            for task_id, task_data in self.tasks.items():
                if task_data['updated_at'] < cutoff:
                    # Закрываем парсер если есть
                    parser = task_data.get('parser')
                    if parser and parser.driver:
                        try:
                            parser.driver.quit()
                        except Exception:
                            pass
                    to_remove.append(task_id)
            
            for task_id in to_remove:
                del self.tasks[task_id]
                removed += 1
        
        return removed
    
    def _start_cleanup_thread(self) -> None:
        """Запуск фонового потока очистки."""
        def cleanup_loop():
            while self._running:
                time.sleep(300)  # Каждые 5 минут
                if self._running:
                    self.cleanup_old_tasks()
        
        self._cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        self._cleanup_thread.start()
    
    def stop(self) -> None:
        """Остановка менеджера."""
        self._running = False
        # Закрываем все парсеры
        with self.lock:
            for task_data in self.tasks.values():
                parser = task_data.get('parser')
                if parser and parser.driver:
                    try:
                        parser.driver.quit()
                    except Exception:
                        pass


# Глобальный экземпляр менеджера задач
task_manager = TaskManager(ttl_hours=1)

