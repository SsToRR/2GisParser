# -*- coding: utf-8 -*-
"""Кастомные исключения."""


class TaskNotFoundError(Exception):
    """Задача не найдена."""
    pass


class InvalidRequestError(Exception):
    """Невалидный запрос."""
    pass


class ParseError(Exception):
    """Ошибка парсинга."""
    pass

