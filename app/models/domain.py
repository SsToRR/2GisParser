# -*- coding: utf-8 -*-
"""Доменные модели (адаптированные из оригинального парсера)."""

import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class TaskStatus(str, Enum):
    """Статусы задачи парсинга."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SocialNetwork(str, Enum):
    """Типы социальных сетей."""
    VK = "vk"
    YOUTUBE = "youtube"
    OK = "ok"
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    INSTAGRAM = "instagram"
    OTHER = "other"


@dataclass
class SocialLinks:
    """Ссылки на социальные сети."""
    vk: str = ""
    youtube: str = ""
    ok: str = ""
    telegram: str = ""
    whatsapp: str = ""
    instagram: str = ""
    
    def to_dict(self) -> Dict[str, str]:
        return {
            'VK': self.vk,
            'Youtube': self.youtube,
            'OK': self.ok,
            'Telegram': self.telegram,
            'Whatsapp': self.whatsapp,
            'Instagram': self.instagram,
        }


@dataclass
class FirmData:
    """Данные о фирме."""
    name: str = ""
    rating: str = ""
    city: str = ""
    address: str = ""
    schedule: str = ""
    phones: List[str] = field(default_factory=list)
    email: str = ""
    website: str = ""
    social: SocialLinks = field(default_factory=SocialLinks)
    whatsapp_numbers: List[str] = field(default_factory=list)
    telegram_username: str = ""
    other_social: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)
    source_url: str = ""

    @staticmethod
    def _phone_for_export(phone: str) -> str:
        return re.sub(r'[-‐‑‒–—―]+', '', phone or '').strip()

    @staticmethod
    def _city_from_address(address: str) -> str:
        parts = [part.strip() for part in (address or '').split(',')]
        return parts[1] if len(parts) > 1 else ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для экспорта (CSV / Excel)."""
        phones = [self._phone_for_export(phone) for phone in self.phones]
        whatsapp_1 = ""
        whatsapp_2 = ""
        if 1 <= len(self.whatsapp_numbers) <= 2:
            whatsapp_1 = self.whatsapp_numbers[0]
            if len(self.whatsapp_numbers) == 2:
                whatsapp_2 = self.whatsapp_numbers[1]

        return {
            'Название': self.name,
            'Оценка': self.rating,
            'Город': self.city or self._city_from_address(self.address),
            'Адрес': self.address,
            'Расписание': self.schedule,
            'Телефоны': ' | '.join(phones),
            'Почта': self.email,
            'Сайт': self.website,
            'Whatsapp номер 1': whatsapp_1,
            'Whatsapp номер 2': whatsapp_2,
            'Whatsapp ссылка': self.social.whatsapp,
            'Telegram ссылка': self.social.telegram,
            'Telegram ник': self.telegram_username,
            'Instagram': self.social.instagram,
            'Youtube': self.social.youtube,
            'VK': self.social.vk,
            'OK': self.social.ok,
            'Другие соцсети': ' | '.join(self.other_social),
            'Информация': ' | '.join(self.info),
            'URL': self.source_url,
        }


@dataclass
class ParseProgress:
    """Прогресс выполнения парсинга."""
    status: TaskStatus = TaskStatus.PENDING
    current_city: str = ""
    current_city_index: int = 0
    total_cities: int = 0
    current_page: int = 0
    total_pages: int = 0
    firms_processed: int = 0
    firms_total: int = 0
    message: str = ""
    errors: List[str] = field(default_factory=list)
    
    @property
    def progress_percent(self) -> int:
        """Процент выполнения."""
        if self.firms_total == 0:
            return 0
        return min(100, int(self.firms_processed / self.firms_total * 100))


@dataclass
class ParseRequest:
    """Запрос на парсинг."""
    query: str
    cities: List[str]
    export_columns: List[str] = field(default_factory=list)
    
    def validate(self) -> List[str]:
        """Валидация запроса. Возвращает список ошибок."""
        errors = []
        if not self.query or not self.query.strip():
            errors.append("Поисковый запрос не может быть пустым")
        if not self.cities:
            errors.append("Выберите хотя бы один город")
        if len(self.query) > 200:
            errors.append("Поисковый запрос слишком длинный (макс. 200 символов)")
        return errors


@dataclass
class ParseResult:
    """Результат парсинга."""
    task_id: str
    request: ParseRequest
    firms: List[FirmData] = field(default_factory=list)
    progress: ParseProgress = field(default_factory=ParseProgress)
    excel_path: Optional[str] = None
