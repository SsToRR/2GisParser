# -*- coding: utf-8 -*-
"""Пошаговый вывод прогресса парсера в консоль."""

from datetime import datetime
from typing import Callable, Optional


class ParseProgressLog:
    """Логирование этапов парсинга."""

    def __init__(self, printer: Optional[Callable[[str], None]] = None):
        self._print = printer or self._default_print

    @staticmethod
    def _default_print(message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {message}", flush=True)

    def step(self, message: str) -> None:
        """Основной этап."""
        self._print(f"> {message}")

    def detail(self, message: str) -> None:
        """Детализация внутри этапа."""
        self._print(f"  - {message}")

    def done(self, message: str) -> None:
        """Завершение этапа."""
        self._print(f"+ {message}")

    def warn(self, message: str) -> None:
        """Предупреждение."""
        self._print(f"! {message}")
