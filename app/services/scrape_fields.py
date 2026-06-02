# -*- coding: utf-8 -*-
"""Какие поля карточки собирать — по выбранным колонкам экспорта."""

from typing import List, Optional, Sequence

from app.services.export import EXPORT_HEADERS, normalize_export_columns


class ScrapeFields:
    """Набор колонок CSV → какие шаги парсера выполнять."""

    def __init__(self, columns: Optional[Sequence[str]] = None):
        if columns:
            self.columns = normalize_export_columns(columns)
        else:
            self.columns = list(EXPORT_HEADERS)
        self._set = set(self.columns)

    @classmethod
    def all(cls) -> 'ScrapeFields':
        return cls(list(EXPORT_HEADERS))

    def wants(self, *names: str) -> bool:
        return any(name in self._set for name in names)

    @property
    def needs_phone_button(self) -> bool:
        return self.wants('Телефоны')

    @property
    def needs_name(self) -> bool:
        return self.wants('Название')

    @property
    def needs_rating(self) -> bool:
        return self.wants('Оценка')

    @property
    def needs_address(self) -> bool:
        return self.wants('Адрес')

    @property
    def needs_schedule(self) -> bool:
        return self.wants('Расписание')

    @property
    def needs_phones(self) -> bool:
        return self.wants('Телефоны')

    @property
    def needs_email(self) -> bool:
        return self.wants('Почта')

    @property
    def needs_website(self) -> bool:
        return self.wants('Сайт')

    @property
    def needs_social_links(self) -> bool:
        return self.wants(
            'Instagram',
            'Youtube',
            'VK',
            'OK',
            'Telegram ссылка',
            'Telegram ник',
            'Whatsapp ссылка',
            'Другие соцсети',
        )

    @property
    def needs_whatsapp_numbers(self) -> bool:
        return self.wants('Whatsapp номер 1', 'Whatsapp номер 2')

    @property
    def needs_telegram_username(self) -> bool:
        return self.wants('Telegram ник')

    @property
    def needs_info(self) -> bool:
        return self.wants('Информация')

    @property
    def needs_any_contact_step(self) -> bool:
        return (
            self.needs_email
            or self.needs_website
            or self.needs_social_links
            or self.needs_whatsapp_numbers
            or self.needs_info
        )

    def trim_social(self, social) -> None:
        """Оставить только выбранные поля соцсетей."""
        if not self.wants('VK'):
            social.vk = ''
        if not self.wants('Youtube'):
            social.youtube = ''
        if not self.wants('OK'):
            social.ok = ''
        if not self.wants('Telegram ссылка', 'Telegram ник'):
            social.telegram = ''
        if not self.wants(
            'Whatsapp ссылка', 'Whatsapp номер 1', 'Whatsapp номер 2'
        ):
            social.whatsapp = ''
        if not self.wants('Instagram'):
            social.instagram = ''
